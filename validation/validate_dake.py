"""
Validate rftinterp against the worked examples in
L.P. Dake, The Practice of Reservoir Engineering (revised edition), section 2.7.

Run from the repository root:
    python validation/validate_dake.py

Writes plots and validation_report.md to validation/output/.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

from rftinterp import free_fit_contact, interpret_group, load_data, load_groups
from rftinterp.plotting import plot_result

HERE = Path(__file__).parent
OUT = HERE / "output"

# (quantity, Dake's value, tolerance, source)
REFERENCE = {
    "AB_owc":        (6235.0, 2.0,  "Fig. 2.20 / text p. 60: OWC at 6235 ft.ss"),
    "AB_oil_grad":   (0.28,   0.02, "p. 60: PVT oil gradient 0.28 psi/ft"),
    "AB_wat_grad":   (0.44,   0.01, "p. 60: water gradient 0.44 psi/ft"),
    "C_free_oil":    (0.355,  0.02, "Fig. 2.21a: forced oil gradient 0.355 psi/ft"),
    "C_free_wat":    (0.577,  0.03, "Fig. 2.21a: forced water gradient 0.577 psi/ft"),
    "C_layer_step":  (5.0,    3.0,  "p. 61: ~5 psi perturbations between layers"),
}
# Qualitative check: Dake's lines in Fig. 2.21 are hand-drawn, so only the
# direction and order of magnitude of the OWC shift is tested.
MIN_OWC_SHIFT = 30.0   # ft; Dake reports 90 ft (p. 62)


def check(name, value):
    ref, tol, src = REFERENCE[name]
    ok = abs(value - ref) <= tol
    return f"| {name} | {ref} | {value:.3f} | +/-{tol} | {'PASS' if ok else 'FAIL'} | {src} |", ok


def main():
    OUT.mkdir(exist_ok=True)
    df = load_data(HERE / "data" / "dake_rft.csv")
    groups = {g.wells[0] if len(g.wells) == 1 else "AB": g
              for g in load_groups(HERE / "groups_dake.json")}

    rows, results = [], []

    # ---- Fig. 2.20: wells A (water) + B (oil) ----
    res_ab = interpret_group(df, groups["AB"])
    plot_result(res_ab, OUT / "dake_fig2_20_AB.png")
    a = df[df.Well == "A"]; b = df[df.Well == "B"]
    go, gw, _ = free_fit_contact(b.Depth_TVDSS, b.P_res, a.Depth_TVDSS, a.P_res)
    for name, val in [("AB_owc", res_ab.owc), ("AB_oil_grad", go), ("AB_wat_grad", gw)]:
        r, ok = check(name, val); rows.append(r); results.append(ok)

    # ---- Fig. 2.21: well C, layered reservoir ----
    res_c = interpret_group(df, groups["C"])
    plot_result(res_c, OUT / "dake_fig2_21_C.png")
    c = df[df.Well == "C"]
    oil_pts = c.loc[[i for ln in res_c.oil_lines for i in ln.indices]]
    wat_pts = c.loc[[i for ln in res_c.water_lines for i in ln.indices]]
    fo, fw, free_owc = free_fit_contact(oil_pts.Depth_TVDSS, oil_pts.P_res,
                                        wat_pts.Depth_TVDSS, wat_pts.P_res)
    steps = [abs(l2.intercept - l1.intercept)
             for lines in (res_c.oil_lines, res_c.water_lines)
             for l1, l2 in zip(lines[:-1], lines[1:])]
    mean_step = sum(steps) / len(steps)
    for name, val in [("C_free_oil", fo), ("C_free_wat", fw),
                      ("C_layer_step", mean_step)]:
        r, ok = check(name, val); rows.append(r); results.append(ok)
    shift = free_owc - res_c.owc
    ok = shift > MIN_OWC_SHIFT
    rows.append(f"| C_owc_shift | 90 (deeper) | {shift:.1f} | > {MIN_OWC_SHIFT:.0f} ft deeper | "
                f"{'PASS' if ok else 'FAIL'} | p. 62: incorrect method gives optimistic (deeper) OWC |")
    results.append(ok)

    report = [
        "# Validation against Dake, The Practice of Reservoir Engineering, section 2.7", "",
        "| Check | Dake | rftinterp | Tolerance | Result | Source |",
        "|---|---|---|---|---|---|", *rows, "",
        f"**{sum(results)}/{len(results)} checks passed.**", "",
        "Fig. 2.21 data are digitised (+/-2-3 psi, +/-3 ft); tolerances reflect this.",
        "", "## Interpretation output", "", "```",
        res_ab.summary(), "", res_c.summary(),
        f"  Free-fit (incorrect) OWC = {free_owc:.1f} ft "
        f"(oil {fo:.3f}, water {fw:.3f} psi/ft)", "```", "",
        "![Fig 2.20](dake_fig2_20_AB.png)", "", "![Fig 2.21](dake_fig2_21_C.png)",
    ]
    (OUT / "validation_report.md").write_text("\n".join(report))
    print("\n".join(report[:len(rows) + 6]))
    return all(results)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
