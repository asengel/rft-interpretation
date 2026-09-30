"""Command line interface: rftinterp DATA.csv GROUPS.json [-o OUTDIR]"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

from .interpret import interpret_group
from .io import load_data, load_groups
from .plotting import plot_result


def run(argv=None):
    """Parse arguments, interpret all groups and return the results."""
    p = argparse.ArgumentParser(description="RFT pressure-depth interpretation "
                                            "with fixed fluid gradients.")
    p.add_argument("data", help="RFT CSV file")
    p.add_argument("groups", help="JSON file with well groups and gradients")
    p.add_argument("-o", "--outdir", default="output", help="folder for plots")
    p.add_argument("--no-plots", action="store_true")
    args = p.parse_args(argv)

    df = load_data(args.data)
    outdir = Path(args.outdir)
    results = []
    for cfg in load_groups(args.groups):
        res = interpret_group(df, cfg)
        print("\n" + res.summary())
        if not args.no_plots and not res.data.empty:
            outdir.mkdir(parents=True, exist_ok=True)
            safe = "".join(ch if ch.isalnum() else "_" for ch in cfg.name).strip("_")
            path = outdir / f"rft_{safe}.png"
            plot_result(res, path)
            print(f"  Plot: {path}")
        results.append(res)
    return results


def main(argv=None) -> int:
    """Console entry point; returns an exit code."""
    run(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
