# Validation data

Reference data from **L.P. Dake, *The Practice of Reservoir Engineering*
(revised edition), Elsevier, section 2.7 "Application of the repeat formation tester"**.

`data/dake_rft.csv` (depths in ft, pressures in psia):

| Well | Source | Points | Notes |
|---|---|---|---|
| A | Table on p. 59 (Fig. 2.20) | 5 | Water, measured values |
| B | Table on p. 59 (Fig. 2.20) | 6 | Oil, measured values |
| C | Fig. 2.21, **digitised** | 26 | Relative units - see below |

**Well C** is digitised from Fig. 2.21. The figure has no absolute scale: `Depth_TVDSS`
holds Dake's *thickness* (ft below top of section) and `P_res` his *Δp* (psi).
Gradients and contact positions are unaffected by the missing reference.

No data exist in 300-410 ft: the tight interval described by Dake.

`Depth_MD`, `Mobility` and `Temp` are not given in the book and are left blank.

## Gradients used (`groups_dake.json`)

| Group | Oil | Water | Source |
|---|---|---|---|
| A+B | 0.28 psi/ft | 0.44 psi/ft | PVT oil SG 0.646; water gradient from the data |
| C | 0.27 psi/ft | 0.45 psi/ft | Values used by Dake in Fig. 2.21b |

