"""
RFT pressure-depth interpretation with fixed (PVT) fluid gradients.

Workflow for one group of wells penetrating the same reservoir:

1. ``classify_fluids`` - split the depth-sorted points into oil (above) and
   water (below) by testing every possible split.
2. ``find_lines`` - within each fluid, divide the points into contiguous depth
   intervals (layers) of constant projected intercept, then remove outliers
   from each layer until its RMSE meets the limit.
3. ``interpret_group`` - intersect the deepest oil line with the shallowest
   water line to obtain the OWC and check it against ODT / WUT.

Fluid gradients are *honoured*, not fitted (Dake, The Practice of Reservoir
Engineering, section 2.7): with the gradient fixed, every point on a line has
the same projected intercept ``c = P - g * D``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------------
# Configuration and result containers
# ----------------------------------------------------------------------------
@dataclass
class GroupConfig:
    """Interpretation settings for one group of wells in the same reservoir."""
    name: str
    wells: List[str]
    oil_grad: float                 # psi/ft
    wat_grad: float                 # psi/ft
    rmse_limit: float = 1.0         # psi, max scatter of intercepts on a line
    min_points: int = 3             # minimum points to accept a line
    segment_penalty: float = 20.0   # psi^2, cost of starting a new layer


@dataclass
class Line:
    fluid: str                      # 'oil' or 'water'
    gradient: float                 # psi/ft
    intercept: float                # psi, P = gradient * D + intercept
    indices: List                   # DataFrame index labels of points on the line
    rmse: float
    top: float                      # ft
    base: float                     # ft

    @property
    def count(self) -> int:
        return len(self.indices)

    def pressure_at(self, depth):
        return self.gradient * np.asarray(depth) + self.intercept


@dataclass
class InterpretationResult:
    config: GroupConfig
    data: pd.DataFrame
    oil_lines: List[Line] = field(default_factory=list)
    water_lines: List[Line] = field(default_factory=list)
    owc: Optional[float] = None
    owc_uncertainty: Optional[float] = None
    odt: Optional[float] = None     # oil down to
    wut: Optional[float] = None     # water up to
    consistency: str = "no contact"

    @property
    def outliers(self) -> pd.DataFrame:
        used = [i for ln in self.oil_lines + self.water_lines for i in ln.indices]
        return self.data.drop(index=used)

    def summary(self) -> str:
        cfg = self.config
        out = [f"=== {cfg.name}: wells {cfg.wells}, {len(self.data)} points ===",
               f"  gradients: oil {cfg.oil_grad}, water {cfg.wat_grad} psi/ft; "
               f"RMSE limit {cfg.rmse_limit} psi"]
        for lines in (self.oil_lines, self.water_lines):
            for i, ln in enumerate(lines):
                shift = "" if i == 0 else \
                    f", step {ln.intercept - lines[i - 1].intercept:+.1f} psi"
                out.append(f"  {ln.fluid.capitalize()} line {i + 1}: "
                           f"{ln.top:.0f}-{ln.base:.0f} ft, n={ln.count}, "
                           f"intercept={ln.intercept:.2f}, RMSE={ln.rmse:.2f}{shift}")
        if not self.outliers.empty:
            out.append(f"  Outliers: depths {self.outliers['Depth_TVDSS'].round(1).tolist()}")
        if self.owc is not None:
            out.append(f"  ODT = {self.odt:.1f} ft, WUT = {self.wut:.1f} ft")
            out.append(f"  OWC = {self.owc:.1f} ft (+/- {self.owc_uncertainty:.0f} ft)")
            out.append(f"  Consistency: {self.consistency}")
        return "\n".join(out)


# ----------------------------------------------------------------------------
# Core algorithms
# ----------------------------------------------------------------------------
def projected_intercepts(depth, pressure, gradient) -> np.ndarray:
    """c = P - g * D for each point."""
    return np.asarray(pressure, float) - gradient * np.asarray(depth, float)


def optimize_cluster(indices: Sequence, intercepts: Sequence[float],
                     rmse_limit: float, min_points: int = 3):
    """
    Drop the point farthest from the mean intercept until the RMSE is within
    ``rmse_limit``. Returns (indices, intercepts, rmse) or (None, None, None)
    if fewer than ``min_points`` remain.
    """
    idx, vals = list(indices), list(intercepts)
    while len(idx) >= min_points:
        mean, rmse = np.mean(vals), np.std(vals)
        if rmse <= rmse_limit:
            return idx, vals, float(rmse)
        worst = int(np.argmax(np.abs(np.asarray(vals) - mean)))
        idx.pop(worst)
        vals.pop(worst)
    return None, None, None


def segment_depth(intercepts: Sequence[float], penalty: float
                  ) -> Tuple[float, List[Tuple[int, int]]]:
    """
    Optimal split of a depth-sorted intercept series into contiguous segments
    of constant value (dynamic programming).

    Cost = sum of squared deviations from each segment mean + ``penalty`` per
    segment. Returns (total cost, [(start, end), ...]) with ``end`` exclusive.
    """
    x = np.asarray(intercepts, float)
    n = len(x)
    if n == 0:
        return 0.0, []
    cs = np.concatenate([[0.0], np.cumsum(x)])
    cs2 = np.concatenate([[0.0], np.cumsum(x * x)])

    best = np.full(n + 1, np.inf)
    best[0] = 0.0
    prev = np.zeros(n + 1, dtype=int)
    for j in range(1, n + 1):
        for i in range(j):
            m = j - i
            s = cs[j] - cs[i]
            cost = best[i] + (cs2[j] - cs2[i]) - s * s / m + penalty
            if cost < best[j]:
                best[j], prev[j] = cost, i

    segs, j = [], n
    while j > 0:
        segs.append((int(prev[j]), j))
        j = prev[j]
    return float(best[n]), segs[::-1]


def classify_fluids(df: pd.DataFrame, cfg: GroupConfig
                    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Assign each point to oil or water. Every split in depth is tested (oil
    above, water below, including all-oil and all-water) and the split with
    the lowest total layered-fit cost is kept.
    """
    d = df.sort_values("Depth_TVDSS")
    D, P = d["Depth_TVDSS"].to_numpy(), d["P_res"].to_numpy()
    best_cost, best_k = np.inf, 0
    for k in range(len(d) + 1):
        c_oil, _ = segment_depth(projected_intercepts(D[:k], P[:k], cfg.oil_grad),
                                 cfg.segment_penalty)
        c_wat, _ = segment_depth(projected_intercepts(D[k:], P[k:], cfg.wat_grad),
                                 cfg.segment_penalty)
        if c_oil + c_wat < best_cost:
            best_cost, best_k = c_oil + c_wat, k
    return d.iloc[:best_k], d.iloc[best_k:]


def find_lines(df_fluid: pd.DataFrame, fluid: str, gradient: float,
               cfg: GroupConfig) -> List[Line]:
    """Find the gradient lines (layers) for the points of one fluid."""
    if df_fluid.empty:
        return []
    d = df_fluid.sort_values("Depth_TVDSS")
    ints = projected_intercepts(d["Depth_TVDSS"], d["P_res"], gradient)
    idx = d.index.to_numpy()
    _, segs = segment_depth(ints, cfg.segment_penalty)

    lines = []
    for a, b in segs:
        opt_idx, opt_vals, rmse = optimize_cluster(idx[a:b], ints[a:b],
                                                   cfg.rmse_limit, cfg.min_points)
        if opt_idx is None:
            continue
        depths = d.loc[opt_idx, "Depth_TVDSS"]
        lines.append(Line(fluid, gradient, float(np.mean(opt_vals)), list(opt_idx),
                          rmse, float(depths.min()), float(depths.max())))
    return lines


def contact_depth(upper: Line, lower: Line) -> float:
    """Depth where two lines of different gradient intersect."""
    return (lower.intercept - upper.intercept) / (upper.gradient - lower.gradient)


def interpret_group(df: pd.DataFrame, cfg: GroupConfig) -> InterpretationResult:
    """Full interpretation of one group of wells."""
    data = df[df["Well"].astype(str).isin([str(w) for w in cfg.wells])].copy()
    res = InterpretationResult(cfg, data)
    if data.empty:
        return res

    df_oil, df_wat = classify_fluids(data, cfg)
    res.oil_lines = find_lines(df_oil, "oil", cfg.oil_grad, cfg)
    res.water_lines = find_lines(df_wat, "water", cfg.wat_grad, cfg)

    if res.oil_lines and res.water_lines:
        res.owc = contact_depth(res.oil_lines[-1], res.water_lines[0])
        # +/- rmse_limit pressure error on each line
        res.owc_uncertainty = 2 * cfg.rmse_limit / (cfg.wat_grad - cfg.oil_grad)
        res.odt = float(df_oil["Depth_TVDSS"].max())
        res.wut = float(df_wat["Depth_TVDSS"].min())
        tol = res.owc_uncertainty
        if res.odt <= res.owc <= res.wut:
            res.consistency = "consistent (OWC between ODT and WUT)"
        elif res.odt - tol <= res.owc <= res.wut + tol:
            res.consistency = "consistent within uncertainty"
        else:
            res.consistency = ("INCONSISTENT: OWC well outside ODT-WUT; oil and water "
                               "points are probably in different compartments "
                               "(e.g. sealing fault)")
    return res


# ----------------------------------------------------------------------------
# Comparison method (not recommended for interpretation)
# ----------------------------------------------------------------------------
def free_fit_contact(depth_oil, p_oil, depth_wat, p_wat):
    """
    Least-squares gradients fitted freely through oil and water points and
    their intersection - the 'forced straight lines' approach Dake warns
    against (Fig. 2.21a). Returns (oil_grad, water_grad, contact_depth).
    """
    go, co = np.polyfit(depth_oil, p_oil, 1)
    gw, cw = np.polyfit(depth_wat, p_wat, 1)
    return float(go), float(gw), float((cw - co) / (go - gw))
