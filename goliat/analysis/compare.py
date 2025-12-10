"""Compare UGent and CNR data from Excel files and create comparison plots.

This module provides functionality to compare SAR data between different
institutions (UGent and CNR) and create publication-quality comparison plots.
"""

import logging
import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Try to use scienceplots style if available
try:
    import scienceplots  # noqa: F401

    plt.style.use(["science", "ieee", "no-latex"])
except ImportError:
    pass

# Set IEEE-compliant font sizes and ensure white background/black text
plt.rcParams.update(
    {
        "font.size": 9,
        "axes.titlesize": 9,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "figure.titlesize": 10,
        "lines.markersize": 4,
        "lines.markeredgewidth": 0.5,
        # Ensure white background and black text (override any dark mode)
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "black",
        "axes.labelcolor": "black",
        "xtick.color": "black",
        "ytick.color": "black",
        "text.color": "black",
        "legend.facecolor": "white",
        "legend.edgecolor": "black",
        "grid.color": "gray",
    }
)

# Define metrics to plot
METRICS = [
    "SAR_wholebody (mW/kg)",
    "SAR_head (mW/kg)",
    "SAR_trunk (mW/kg)",
    "psSAR10g_eyes (mW/kg)",
    "psSAR10g_skin (mW/kg)",
    "psSAR10g_brain (mW/kg)",
]

# Define scenarios
SCENARIOS = ["fronteyes", "belly", "cheek"]

# Institution colors
INSTITUTION_COLORS = {"UGent": "black", "CNR": "red"}
PHANTOM_MARKERS = {"Thelonious": "o", "Eartha": "s", "Duke": "^"}


def _apply_comparison_style():
    """Apply white background style to matplotlib.

    This function resets matplotlib rcParams to ensure white background and black text,
    overriding any dark mode styles that may have been applied by other modules.
    Should be called before creating any plots.
    """
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "black",
            "axes.labelcolor": "black",
            "xtick.color": "black",
            "ytick.color": "black",
            "text.color": "black",
            "legend.facecolor": "white",
            "legend.edgecolor": "black",
            "grid.color": "gray",
            "savefig.facecolor": "white",
            "savefig.edgecolor": "white",
        }
    )


def load_comparison_data(
    ugent_file: str,
    cnr_file: str,
) -> pd.DataFrame:
    """Load all data from both Excel files.

    Args:
        ugent_file: Path to UGent Excel file
        cnr_file: Path to CNR Excel file

    Returns:
        Combined DataFrame with all data
    """
    all_data = []

    # Load UGent data
    if os.path.exists(ugent_file):
        logging.getLogger("progress").info(
            f"Loading UGent data from: {ugent_file}",
            extra={"log_type": "info"},
        )
        xl_ugent = pd.ExcelFile(ugent_file)
        for sheet_name in xl_ugent.sheet_names:
            df = pd.read_excel(ugent_file, sheet_name=sheet_name)
            parts = sheet_name.split("_")
            phantom = parts[0]
            scenario = "_".join(parts[1:])
            df["phantom"] = phantom
            df["institution"] = "UGent"
            df["scenario"] = scenario
            all_data.append(df)
    else:
        logging.getLogger("progress").warning(
            f"UGent file not found: {ugent_file}",
            extra={"log_type": "warning"},
        )

    # Load CNR data
    if os.path.exists(cnr_file):
        logging.getLogger("progress").info(
            f"Loading CNR data from: {cnr_file}",
            extra={"log_type": "info"},
        )
        xl_cnr = pd.ExcelFile(cnr_file)
        for sheet_name in xl_cnr.sheet_names:
            df = pd.read_excel(cnr_file, sheet_name=sheet_name)
            parts = sheet_name.split("_")
            phantom = parts[0]
            scenario = "_".join(parts[1:])
            df["phantom"] = phantom
            df["institution"] = "CNR"
            df["scenario"] = scenario
            all_data.append(df)
    else:
        logging.getLogger("progress").warning(
            f"CNR file not found: {cnr_file}",
            extra={"log_type": "warning"},
        )

    if not all_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)
    return combined_df


def create_comparison_plots(
    df: pd.DataFrame,
    output_dir: Path,
    plot_format: str = "pdf",
):
    """Create comparison plots for all metrics and scenarios.

    Args:
        df: Combined DataFrame with UGent and CNR data
        output_dir: Directory to save plots
        plot_format: Output format ('pdf' or 'png')
    """
    output_dir.mkdir(exist_ok=True, parents=True)

    for scenario in SCENARIOS:
        scenario_data = df[df["scenario"] == scenario].copy()

        if scenario_data.empty:
            logging.getLogger("progress").info(
                f"No data found for scenario: {scenario}",
                extra={"log_type": "warning"},
            )
            continue

        for metric in METRICS:
            if metric not in scenario_data.columns:
                continue

            metric_data = scenario_data[scenario_data[metric].notna()].copy()

            if metric_data.empty:
                continue

            fig, ax = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column

            phantoms = metric_data["phantom"].unique()

            for phantom in sorted(phantoms):
                phantom_data = metric_data[metric_data["phantom"] == phantom]
                institution = phantom_data["institution"].iloc[0]

                grouped = phantom_data.groupby("frequency_mhz")[metric].agg(["mean", "std"])

                x = grouped.index.values
                y_mean = grouped["mean"].values
                y_std = grouped["std"].values

                label = f"{phantom} ({institution})"
                color = INSTITUTION_COLORS.get(institution, "gray")
                marker = PHANTOM_MARKERS.get(phantom, "o")

                ax.errorbar(
                    x,
                    y_mean,
                    yerr=y_std,
                    marker=marker,
                    linestyle="-",
                    label=label,
                    color=color,
                    markersize=4,
                    capsize=2,
                    capthick=1,
                    linewidth=1.5,
                )

            ax.set_xlabel("Frequency (MHz)")
            ax.set_ylabel(metric)
            ax.legend(loc="best", fontsize=7)
            ax.grid(True, alpha=0.3)
            ax.set_ylim(bottom=0)

            plt.tight_layout()

            safe_metric = metric.replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
            filename = f"compare_{safe_metric}_{scenario}.{plot_format}"
            filepath = output_dir / filename

            if plot_format == "pdf":
                fig.savefig(filepath, bbox_inches="tight", format="pdf")
            else:
                fig.savefig(filepath, dpi=300, bbox_inches="tight")

            plt.close(fig)
            logging.getLogger("progress").info(
                f"  - Generated comparison plot: {filename}",
                extra={"log_type": "success"},
            )


def create_summary_comparison_plots(
    df: pd.DataFrame,
    output_dir: Path,
    plot_format: str = "pdf",
):
    """Create summary comparison plots across all scenarios.

    Args:
        df: Combined DataFrame with UGent and CNR data
        output_dir: Directory to save plots
        plot_format: Output format ('pdf' or 'png')
    """
    output_dir.mkdir(exist_ok=True, parents=True)

    for metric in METRICS:
        if metric not in df.columns:
            continue

        metric_data = df[df[metric].notna()].copy()

        if metric_data.empty:
            continue

        # Create figure with 3 subplots (one per scenario)
        fig, axes = plt.subplots(1, 3, figsize=(7, 2.5))

        for idx, scenario in enumerate(SCENARIOS):
            ax = axes[idx]
            scenario_data = metric_data[metric_data["scenario"] == scenario]

            if scenario_data.empty:
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
                ax.set_title(scenario.replace("_", " ").title())
                continue

            phantoms = scenario_data["phantom"].unique()
            for phantom in sorted(phantoms):
                phantom_data = scenario_data[scenario_data["phantom"] == phantom]
                institution = phantom_data["institution"].iloc[0]

                grouped = phantom_data.groupby("frequency_mhz")[metric].agg(["mean", "std"])

                x = grouped.index.values
                y_mean = grouped["mean"].values
                y_std = grouped["std"].values

                label = f"{phantom}"
                color = INSTITUTION_COLORS.get(institution, "gray")
                marker = PHANTOM_MARKERS.get(phantom, "o")
                linestyle = "-" if institution == "UGent" else "--"

                ax.errorbar(
                    x,
                    y_mean,
                    yerr=y_std,
                    marker=marker,
                    linestyle=linestyle,
                    label=label,
                    color=color,
                    markersize=3,
                    capsize=1,
                    capthick=0.5,
                    linewidth=1,
                )

            ax.set_xlabel("Frequency (MHz)")
            if idx == 0:
                ax.set_ylabel(metric.replace("_", " "))
            ax.set_title(scenario.replace("_", " ").title())
            ax.legend(loc="best", fontsize=6)
            ax.grid(True, alpha=0.3)
            ax.set_ylim(bottom=0)

        plt.tight_layout()

        safe_metric = metric.replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
        filename = f"compare_summary_{safe_metric}.{plot_format}"
        filepath = output_dir / filename

        if plot_format == "pdf":
            fig.savefig(filepath, bbox_inches="tight", format="pdf")
        else:
            fig.savefig(filepath, dpi=300, bbox_inches="tight")

        plt.close(fig)
        logging.getLogger("progress").info(
            f"  - Generated summary comparison plot: {filename}",
            extra={"log_type": "success"},
        )


def run_comparison(
    ugent_file: str,
    cnr_file: str,
    output_dir: str,
    plot_format: str = "pdf",
):
    """Run the full comparison analysis.

    Args:
        ugent_file: Path to UGent Excel file
        cnr_file: Path to CNR Excel file
        output_dir: Directory to save comparison plots
        plot_format: Output format ('pdf' or 'png')
    """
    # Apply white background style (overrides any dark mode from other modules)
    _apply_comparison_style()

    logging.getLogger("progress").info(
        "=" * 60,
        extra={"log_type": "header"},
    )
    logging.getLogger("progress").info(
        "   UGent vs CNR Data Comparison",
        extra={"log_type": "header"},
    )
    logging.getLogger("progress").info(
        "=" * 60,
        extra={"log_type": "header"},
    )

    # Load data
    df = load_comparison_data(ugent_file, cnr_file)

    if df.empty:
        logging.getLogger("progress").error(
            "No data loaded. Please check file paths.",
            extra={"log_type": "error"},
        )
        return

    logging.getLogger("progress").info(
        f"Loaded {len(df)} total data points",
        extra={"log_type": "success"},
    )
    logging.getLogger("progress").info(
        f"Phantoms: {list(df['phantom'].unique())}",
        extra={"log_type": "info"},
    )
    logging.getLogger("progress").info(
        f"Institutions: {list(df['institution'].unique())}",
        extra={"log_type": "info"},
    )
    logging.getLogger("progress").info(
        f"Scenarios: {list(df['scenario'].unique())}",
        extra={"log_type": "info"},
    )

    output_path = Path(output_dir)

    # Create individual comparison plots
    logging.getLogger("progress").info(
        "\nCreating individual comparison plots...",
        extra={"log_type": "info"},
    )
    create_comparison_plots(df, output_path, plot_format)

    # Create summary plots
    logging.getLogger("progress").info(
        "\nCreating summary comparison plots...",
        extra={"log_type": "info"},
    )
    create_summary_comparison_plots(df, output_path, plot_format)

    logging.getLogger("progress").info(
        f"\nAll comparison plots saved to: {output_dir}",
        extra={"log_type": "success"},
    )


def main():
    """Main entry point for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Compare UGent and CNR SAR data from Excel files")
    parser.add_argument(
        "--ugent-file",
        type=str,
        default="results/near_field/Final_Data_UGent.xlsx",
        help="Path to UGent Excel file",
    )
    parser.add_argument(
        "--cnr-file",
        type=str,
        default="results/near_field/Final_Data_CNR.xlsx",
        help="Path to CNR Excel file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="plots/comparison",
        help="Output directory for comparison plots",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["pdf", "png"],
        default="pdf",
        help="Output format for plots",
    )
    args = parser.parse_args()

    # Setup basic logging if not in goliat context
    from goliat.logging_manager import setup_loggers

    setup_loggers()

    run_comparison(
        args.ugent_file,
        args.cnr_file,
        args.output,
        args.format,
    )


if __name__ == "__main__":
    main()
