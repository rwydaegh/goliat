"""CLI entry point for the env-FF variance-component decomposition (sT1.5.4).

Usage (from the goliat/ directory):

    python -m scripts.run_far_field_uncertainty \
        --results-root results/far_field \
        --out-dir results/uncertainty/far_field

Produces:

* ``variance_components_summary.csv`` — one row per metric, with sigma_*
  and CV_dir / CV_pol / CV_resid columns plus a robustness verdict.
* ``variance_components_long.csv`` — tidy long form, one row per
  (metric, component).
* ``tidy_far_field.csv`` — the loaded long-format dataframe (handy for
  downstream plotting).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from goliat.uncertainty import (
    decompose_balanced,
    decompose_reml,
    load_far_field,
)
from goliat.uncertainty.report import (
    build_report,
    format_console_table,
    write_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--results-root",
        type=Path,
        default=Path("results") / "far_field",
        help="Root of the env-FF results tree (default: results/far_field).",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("results") / "uncertainty" / "far_field",
        help="Where to write the CSV outputs.",
    )
    p.add_argument(
        "--reml",
        action="store_true",
        help="Also fit REML via statsmodels as a cross-check on the balanced-MoM estimates.",
    )
    p.add_argument(
        "--metrics",
        nargs="*",
        default=None,
        help="Restrict to a subset of metric short names (e.g. WB_SAR psSAR10g). Defaults to all metrics found in the data.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args(argv)

    print(f"Loading env-FF results from {args.results_root}")
    df = load_far_field(args.results_root)
    print(
        f"  loaded {len(df)} rows across {df['metric'].nunique()} metrics, "
        f"{df['phantom'].nunique()} phantoms, {df['freq_mhz'].nunique()} freqs"
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_dir / "tidy_far_field.csv", index=False)

    requested = args.metrics or sorted(df["metric"].unique())
    available = set(df["metric"].unique())
    metrics = [m for m in requested if m in available]
    if not metrics:
        print(f"None of the requested metrics are present: {requested}", file=sys.stderr)
        return 2

    components = []
    for m in metrics:
        try:
            vc = decompose_balanced(df, m)
        except ValueError as e:
            print(f"  skipping {m}: {e}")
            continue
        components.append(vc)

    if args.reml:
        for m in metrics:
            try:
                vc = decompose_reml(df, m)
                components.append(vc)
            except Exception as e:
                print(f"  REML failed for {m}: {e}")

    if not components:
        print("No metrics decomposed. Exiting.", file=sys.stderr)
        return 1

    report = build_report(components)
    print()
    print(format_console_table(report[report["method"] == "balanced-MoM"]))
    print()

    write_outputs(report, components, args.out_dir)
    print(f"Wrote {args.out_dir / 'variance_components_summary.csv'}")
    print(f"Wrote {args.out_dir / 'variance_components_long.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
