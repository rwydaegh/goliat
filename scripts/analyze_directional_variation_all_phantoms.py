#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze Directional Variation for All Phantoms

Extracts min/max SAR values across directions for each phantom
to compare with Table 3 in the paper (currently shows only Duke).

Author: AI Assistant
Date: 2026-02-10
Purpose: Answer Bram #106 — verify data for Ella/Thelonious
"""

import csv
from pathlib import Path
import sys

# Force UTF-8 output
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def analyze_phantom(phantom_name):
    """Analyze directional variation for one phantom."""
    base_path = Path(f"plots/far_field/{phantom_name}/boxplot")

    # Metrics to analyze (matching Table 3 in paper)
    metrics = [
        ("SAR_eyes", "Eyes SAR"),
        ("SAR_genitals", "Genitals SAR"),
        ("SAR_brain", "Brain SAR"),
        ("SAR_skin", "Skin SAR"),
        ("SAR_whole_body", "Whole-body SAR"),
    ]

    results = []

    for csv_name, display_name in metrics:
        csv_file = base_path / f"boxplot_{csv_name}_environmental.csv"

        if not csv_file.exists():
            print(f"WARNING: {csv_file} not found")
            continue

        # Read CSV
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Extract column name (should be like 'SAR_eyes' or similar)
        value_col = [col for col in rows[0].keys() if "SAR" in col or "sar" in col]
        if not value_col:
            print(f"WARNING: No SAR column found in {csv_file}")
            continue
        value_col = value_col[0]

        # Get values
        values = [float(row[value_col]) for row in rows if row[value_col]]

        # Get min and max across all directions and frequencies
        min_val = min(values)
        max_val = max(values)
        ratio = max_val / min_val if min_val > 0 else float("inf")

        results.append({"metric": display_name, "max": max_val, "min": min_val, "ratio": ratio})

    return results


def main():
    """Main analysis."""
    phantoms = ["duke", "ella", "eartha", "thelonious"]

    print("=" * 100)
    print("DIRECTIONAL VARIATION ANALYSIS - ALL PHANTOMS")
    print("=" * 100)
    print()
    print("Purpose: Extend Table 3 in paper (currently Duke-only) to all phantoms")
    print()

    all_results = {}

    for phantom in phantoms:
        print(f"\nAnalyzing {phantom.upper()}...")
        results = analyze_phantom(phantom)
        all_results[phantom] = results

    # Print comparison table
    print("\n" + "=" * 100)
    print("COMPARISON TABLE (All Phantoms, All Frequencies)")
    print("=" * 100)
    print()

    # Get metrics from duke
    metrics = [r["metric"] for r in all_results["duke"]]

    for metric in metrics:
        print(f"\n{metric.upper()}")
        print("-" * 100)
        print(f"{'Phantom':<15} {'Max (mW/kg)':<15} {'Min (mW/kg)':<15} {'Max/Min Ratio':<15}")
        print("-" * 100)

        for phantom in phantoms:
            data = [r for r in all_results[phantom] if r["metric"] == metric][0]
            print(f"{phantom.capitalize():<15} {data['max']:<15.1f} {data['min']:<15.3f} {data['ratio']:<15.0f}x")

    # Create LaTeX-ready tables
    print("\n\n" + "=" * 100)
    print("LATEX TABLE FORMAT (For Supplementary Material)")
    print("=" * 100)
    print()

    for phantom in phantoms:
        print(f"\n% Table for {phantom.capitalize()}")
        print("\\begin{table}[!t]")
        print("\\centering")
        print(f"\\caption{{Directional Variation in SAR Metrics ({phantom.capitalize()}, All Frequencies)}}")
        print(f"\\label{{table:direction_var_{phantom}}}")
        print("\\renewcommand{\\arraystretch}{1.1}")
        print("\\scriptsize")
        print("\\begin{tabular}{@{}lccc@{}}")
        print("\\toprule")
        print("\\textbf{Metric} & \\textbf{Max} & \\textbf{Min} & \\textbf{Max/Min} \\\\")
        print(" & \\textbf{(mW/kg)} & \\textbf{(mW/kg)} & \\\\")
        print("\\midrule")

        for result in all_results[phantom]:
            metric_name = result["metric"]
            print(f"{metric_name} & {result['max']:.1f} & {result['min']:.1f} & {result['ratio']:.0f}$\\times$ \\\\")

        print("\\bottomrule")
        print("\\end{tabular}")
        print("\\end{table}")
        print()

    # Key observations
    print("\n" + "=" * 100)
    print("KEY OBSERVATIONS")
    print("=" * 100)
    print()

    print("1. EYES SAR:")
    for phantom in phantoms:
        data = [r for r in all_results[phantom] if r["metric"] == "Eyes SAR"][0]
        print(f"   - {phantom.capitalize()}: {data['ratio']:.0f}x variation (max={data['max']:.1f}, min={data['min']:.3f})")

    print("\n2. GENITALS SAR:")
    for phantom in phantoms:
        data = [r for r in all_results[phantom] if r["metric"] == "Genitals SAR"][0]
        print(f"   - {phantom.capitalize()}: {data['ratio']:.0f}x variation (max={data['max']:.1f}, min={data['min']:.3f})")

    print("\n3. WHOLE-BODY SAR:")
    for phantom in phantoms:
        data = [r for r in all_results[phantom] if r["metric"] == "Whole-body SAR"][0]
        print(f"   - {phantom.capitalize()}: {data['ratio']:.0f}x variation (max={data['max']:.1f}, min={data['min']:.2f})")

    print("\n" + "=" * 100)
    print("RECOMMENDATION FOR PAPER")
    print("=" * 100)
    print()
    print("Current text (line ~626-627):")
    print('  "Table 3 summarizes directional variation for each SAR metric (Duke, averaged over')
    print('   frequency). Similar patterns are observed for the other phantoms."')
    print()
    print("ISSUE: No data shown for other phantoms. Readers can't verify 'similar patterns'.")
    print()
    print("OPTIONS:")
    print("  1. Add all 4 tables to Supplementary Material")
    print("  2. Expand Table 3 to show all phantoms side-by-side (space permitting)")
    print("  3. Add a sentence with ranges: 'Eyes vary 28-47x across phantoms, genitals 57-1000x'")
    print()


if __name__ == "__main__":
    main()
