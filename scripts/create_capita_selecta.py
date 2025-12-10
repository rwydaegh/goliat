"""
Script to create a 'Capita Selecta' of GOLIAT analysis plots.
Converts selected PDFs to PNGs - ONE per visualization type.

Run from anywhere: python scripts/create_capita_selecta.py
"""

import subprocess
from pathlib import Path

# Get project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).parent.parent
PLOTS_DIR = PROJECT_ROOT / "plots"
OUTPUT_DIR = PROJECT_ROOT / "docs/img/results_capita_selecta"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def convert_pdf_to_png(pdf_path: Path, output_path: Path, dpi: int = 200):
    """Convert a PDF to PNG using pdftoppm."""
    try:
        output_stem = output_path.with_suffix("")
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), "-singlefile", str(pdf_path), str(output_stem)], capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  ✓ {output_path.name}")
            return True
    except FileNotFoundError:
        pass
    print(f"  ✗ Failed: {pdf_path.name}")
    return False


def main():
    # One example per VISUALIZATION TYPE
    capita_selecta = [
        ("near_field/eartha/bar/average_sar_bar_by_belly.pdf", "01_bar_chart.png", "Bar Chart", "Average SAR by frequency"),
        ("near_field/eartha/boxplot/boxplot_SAR_whole_body_by_belly.pdf", "02_boxplot.png", "Boxplot", "SAR distribution across scenarios"),
        (
            "near_field/eartha/bubble/bubble_mass_vs_mass_avg_sar_by_belly_allMHz_log.pdf",
            "03_bubble.png",
            "Bubble Chart",
            "Tissue mass vs SAR relationship",
        ),
        ("near_field/eartha/cdf/cdf__whole_body_scenario_all_allMHz.pdf", "04_cdf.png", "CDF", "Cumulative distribution function"),
        (
            "near_field/eartha/correlation/correlation_matrix_tissue_groups_by_belly.pdf",
            "05_correlation.png",
            "Correlation Matrix",
            "Tissue group correlations",
        ),
        ("near_field/eartha/heatmap/heatmap_sar_avg.pdf", "06_heatmap.png", "Heatmap", "SAR overview across all conditions"),
        ("near_field/eartha/line/sar_line_by_belly.pdf", "07_line.png", "Line Plot", "SAR vs frequency trends"),
        ("near_field/eartha/outliers/outliers_iqr_all.pdf", "08_outliers.png", "Outliers", "Outlier detection summary"),
        (
            "near_field/eartha/penetration/penetration_ratio_SAR_vs_frequency_by_belly.pdf",
            "09_penetration.png",
            "Penetration",
            "Depth ratio analysis",
        ),
        ("near_field/eartha/power/power_balance_overview.pdf", "10_power_balance.png", "Power Balance", "Power distribution overview"),
        ("near_field/eartha/ranking/ranking_top20_mass_avg_sar_by_belly_allMHz.pdf", "11_ranking.png", "Ranking", "Top 20 tissues by SAR"),
        ("near_field/eartha/spatial/peak_location_2d_by_belly.pdf", "12_spatial.png", "Spatial", "Peak SAR 2D location"),
        (
            "near_field/eartha/tissue_analysis/scatter_MaxLocal_vs_psSAR10g_by_belly_allMHz.pdf",
            "13_scatter.png",
            "Scatter",
            "Max local vs peak spatial SAR",
        ),
        (
            "near_field/eartha/tissue_analysis/tissue_frequency_response_Skin_by_belly.pdf",
            "14_tissue_response.png",
            "Tissue Response",
            "Frequency response curve",
        ),
        (
            "near_field/eartha/tissue_analysis/distribution_mass_volume_by_belly.pdf",
            "15_mass_volume.png",
            "Distribution",
            "Tissue mass/volume distribution",
        ),
        ("comparison/compare_summary_SAR_wholebody_mW_kg.pdf", "16_comparison.png", "Comparison", "UGent vs CNR validation"),
    ]

    print(f"Creating capita selecta in {OUTPUT_DIR}")
    print("=" * 50)

    converted = []
    for src, out, title, desc in capita_selecta:
        src_path = PLOTS_DIR / src
        out_path = OUTPUT_DIR / out
        if src_path.exists() and convert_pdf_to_png(src_path, out_path):
            converted.append((out, title, desc))

    # Generate README snippet with collapsible sections
    readme_path = OUTPUT_DIR / "README_SNIPPET.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("## Analysis Results Gallery\n\n")
        f.write("GOLIAT generates comprehensive SAR analysis plots. Here's a selection of key visualizations:\n\n")

        # First image visible (hero)
        if converted:
            hero = converted[0]
            f.write(f"### {hero[1]}\n")
            f.write(f"*{hero[2]}*\n\n")
            f.write(f"![{hero[1]}](docs/img/results_capita_selecta/{hero[0]})\n\n")

        # Rest in collapsible sections
        f.write("<details>\n<summary><b>View all plot types (click to expand)</b></summary>\n\n")
        for out, title, desc in converted[1:]:
            f.write(f"### {title}\n")
            f.write(f"*{desc}*\n\n")
            f.write(f"![{title}](docs/img/results_capita_selecta/{out})\n\n")
        f.write("</details>\n")

    print("=" * 50)
    print(f"Done: {len(converted)}/{len(capita_selecta)} plots")
    print(f"README snippet: {readme_path}")


if __name__ == "__main__":
    main()
