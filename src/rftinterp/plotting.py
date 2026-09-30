"""Pressure-depth plot of an interpretation result."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from .interpret import InterpretationResult


def plot_result(res: InterpretationResult, path=None, show: bool = False):
    """Plot points, fitted layer lines and OWC. Returns the matplotlib Figure."""
    df = res.data
    cfg = res.config
    has_mob = "Mobility" in df.columns and df["Mobility"].notna().any()
    if has_mob:
        fig, (ax, ax_mob) = plt.subplots(1, 2, figsize=(14, 8), sharey=True,
                                         gridspec_kw={"width_ratios": [3, 1]})
    else:
        fig, ax = plt.subplots(figsize=(10, 8))

    out = res.outliers
    if not out.empty:
        ax.plot(out["P_res"], out["Depth_TVDSS"], "x", color="gray", ms=8, label="Outlier")

    span = df["Depth_TVDSS"].max() - df["Depth_TVDSS"].min()
    ext = 0.04 * span if span > 0 else 10.0
    owc = res.owc

    for lines, cmap, marker in [(res.oil_lines, plt.cm.Greens, "o"),
                                (res.water_lines, plt.cm.Blues, "s")]:
        for i, ln in enumerate(lines):
            color = cmap(0.55 + 0.45 * (i + 1) / len(lines))
            pts = df.loc[ln.indices]
            ax.plot(pts["P_res"], pts["Depth_TVDSS"], marker, color=color, ms=8, alpha=0.85)
            top, base = ln.top - ext, ln.base + ext
            # extend the two lines that define the contact to the OWC
            if owc is not None and ln is res.oil_lines[-1]:
                base = max(base, owc + ext)
            if owc is not None and res.water_lines and ln is res.water_lines[0]:
                top = min(top, owc - ext)
            depths = np.linspace(top, base, 50)
            ax.plot(ln.pressure_at(depths), depths, color=color, lw=1.8,
                    label=f"{ln.fluid.capitalize()} #{i + 1}: P={ln.gradient}D"
                          f"{ln.intercept:+.1f} (n={ln.count}, RMSE={ln.rmse:.2f})")

    if owc is not None:
        ax.axhline(owc, color="orange", lw=2, ls=":", label=f"OWC: {owc:.0f} ft")

    if df["Well"].nunique() > 1:
        for w, g in df.groupby("Well"):
            ax.annotate(f"Well {w}", (g["P_res"].min(), g["Depth_TVDSS"].min()),
                        textcoords="offset points", xytext=(-40, -5), fontsize=10)

    ax.invert_yaxis()
    ax.set_xlabel("Pressure (psia)")
    ax.set_ylabel("TVDSS (ft)")
    ax.set_title(f"{cfg.name} - oil {cfg.oil_grad}, water {cfg.wat_grad} psi/ft, "
                 f"RMSE <= {cfg.rmse_limit} psi")
    ax.legend(loc="lower left", fontsize="small")
    ax.grid(True, ls="--", alpha=0.5)

    if has_mob:
        ax_mob.semilogx(df["Mobility"], df["Depth_TVDSS"], "o", color="purple", alpha=0.5)
        ax_mob.axvline(1.0, color="red", ls="--")
        ax_mob.set_xlabel("Mobility (mD/cP)")
        ax_mob.grid(True)

    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=130)
    if show:
        plt.show()
    return fig
