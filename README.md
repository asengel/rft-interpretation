# rftinterp

Automated interpretation of RFT / MDT data

![Layered reservoir interpretation](validation/output/dake_fig2_21_C.png)

## Why fixed gradients?

Forcing best-fit straight lines through pressure points can give physically
impossible gradients and a badly misplaced contact. Dake (*The Practice of Reservoir
Engineering*, section 2.7) shows an example where free fitting gives a water gradient
of 0.577 psi/ft and an OWC about 90 ft too deep. Honouring the PVT gradients instead
reveals separate layers offset by a few psi. This package implements the
fixed-gradient approach.

## Method

For each **group** of wells penetrating the same reservoir:

1. **Projected intercepts.** With the gradient `g` fixed, every point on a line has the
   same intercept `c = P − g·D`, so line finding becomes 1-D clustering.
2. **Fluid assignment.** Every oil-above / water-below split in depth is tested; the
   split with the lowest total fit cost is kept. Each point belongs to one fluid only.
3. **Layer detection.** Within each fluid, points are divided into contiguous depth
   intervals of constant intercept by dynamic programming (squared misfit + a penalty per
   layer). Each layer is then cleaned by removing the worst point until its RMSE meets
   the limit.
4. **Contact.** The OWC is the intersection of the deepest oil line and the shallowest
   water line. It is checked against ODT (oil down to) and WUT (water up to), with an
   uncertainty of `2 · RMSE_limit / (g_water − g_oil)`. An OWC far outside ODT-WUT means
   the oil and water points are probably in different compartments.

## Installation

```bash
git clone <repository-url>
cd rft-interpretation
pip install -e .
```

## Usage

### Command line

```bash
rftinterp validation/data/dake_rft.csv validation/groups_dake.json -o output
```

### Python

```python
from rftinterp import GroupConfig, interpret_group, load_data
from rftinterp.plotting import plot_result

df = load_data("validation/data/dake_rft.csv")
cfg = GroupConfig(name="Wells A+B", wells=["A", "B"],
                  oil_grad=0.28, wat_grad=0.44, rmse_limit=1.0)
res = interpret_group(df, cfg)
print(res.summary())            # OWC = 6235.1 ft
plot_result(res, "wells_AB.png")
```

### Input CSV

| Column | Unit | Required |
|---|---|---|
| `Well` | - | yes |
| `Depth_MD` | ft | no |
| `Depth_TVDSS` | ft | yes |
| `P_res` | psia | yes |
| `Mobility` | mD/cP | no (plotted if present) |
| `Temp` | °F | no |


### Group configuration (JSON)

| Key | Meaning | Default |
|---|---|---|
| `name` | Label for output | - |
| `wells` | Wells analysed together | - |
| `oil_grad`, `wat_grad` | Fixed gradients, psi/ft | - |
| `rmse_limit` | Max intercept scatter on a line, psi | 1.0 |
| `min_points` | Minimum points per line | 3 |
| `segment_penalty` | Cost of a new layer, psi²; higher gives fewer layers | 20 |

Use a larger `rmse_limit` for noisy or digitised data.

## Repository layout

```
src/rftinterp/        interpretation package
    interpret.py      algorithms (fluid split, layers, contact)
    io.py             CSV and JSON loading
    plotting.py       pressure-depth plots
    cli.py            command line interface
validation/           reference data, validation script and report
```

## Validation

```bash
python validation/validate_dake.py  # comparison with Dake, writes validation/output/
```

The validation reproduces Dake's worked examples; see
[`validation/output/validation_report.md`](validation/output/validation_report.md).
Highlights: the OWC for Fig. 2.20 is 6235 ft.ss, exactly Dake's value, and Fig. 2.21 is
resolved into 4 oil and 3 water layers with steps of a few psi, as Dake describes.

## Limitations

- One contact per group (OWC). Gas gradients and GOC are not yet handled.
- Oil must lie above water within a group; inverted or interleaved fluids are not supported.
- The OWC assumes the deepest oil layer and shallowest water layer are in pressure
  communication. In layered reservoirs this cannot be verified from the pressures alone.
- Gradients are inputs. Derive them from PVT data and formation water salinity.

## Reference

Dake, L.P. *The Practice of Reservoir Engineering* (revised edition). Elsevier.
Section 2.7, Application of the repeat formation tester.
