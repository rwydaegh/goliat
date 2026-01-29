#!/usr/bin/env python3
"""
Comprehensive visualization script for auto_induced_FR3 results.

This script creates multiple visualizations from the auto_induced_summary.json files:
1. Peak SAPD comparison across frequencies and phantoms
2. Hotspot score distributions
3. Distance to skin analysis
4. Candidate ranking comparisons
5. Worst-case analysis summary
6. Correlation between hotspot score and SAPD
"""

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Set style for all plots
plt.style.use("seaborn-v0_8-whitegrid")
sns.set_palette("husl")


def load_all_results(base_dir: Path) -> list[dict[str, Any]]:
    """Load all auto_induced_summary.json files from the results directory."""
    results = []

    # Find all frequency folders
    freq_folders = sorted([f for f in base_dir.iterdir() if f.is_dir() and f.name.endswith("GHz")])

    for freq_folder in freq_folders:
        freq_ghz = int(freq_folder.name.replace("GHz", ""))

        # Find all phantom folders
        phantom_folders = [f for f in freq_folder.iterdir() if f.is_dir()]

        for phantom_folder in phantom_folders:
            phantom_name = phantom_folder.name

            # Look for the summary JSON file
            summary_file = phantom_folder / "auto_induced" / "auto_induced_summary.json"

            if summary_file.exists():
                with open(summary_file) as f:
                    data = json.load(f)
                    data["freq_ghz"] = freq_ghz
                    data["phantom_name"] = phantom_name
                    results.append(data)
                    print(f"Loaded: {freq_ghz}GHz / {phantom_name}")
            else:
                print(f"Missing: {summary_file}")

    return results


def create_dataframes(results: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create pandas DataFrames from the results for easier analysis."""

    # Summary-level dataframe (one row per phantom/frequency combination)
    summary_records = []
    for r in results:
        worst = r.get("worst_case", {})
        summary_records.append(
            {
                "frequency_ghz": r["freq_ghz"],
                "phantom": r["phantom_name"],
                "frequency_mhz": r.get("frequency_mhz", r["freq_ghz"] * 1000),
                "num_candidates": len(r.get("candidates", [])),
                "worst_case_sapd_w_m2": worst.get("peak_sapd_w_m2"),
                "worst_case_candidate_idx": worst.get("candidate_idx"),
            }
        )

    summary_df = pd.DataFrame(summary_records)

    # Candidate-level dataframe (one row per candidate)
    candidate_records = []
    for r in results:
        candidates = r.get("candidates", [])
        sapd_results = r.get("sapd_results", [])

        # Create a lookup for SAPD results by candidate index
        sapd_lookup = {}
        for sapd in sapd_results:
            sapd_lookup[sapd["candidate_idx"]] = sapd.get("peak_sapd_w_m2")

        for i, cand in enumerate(candidates):
            candidate_idx = i + 1  # 1-indexed
            candidate_records.append(
                {
                    "frequency_ghz": r["freq_ghz"],
                    "phantom": r["phantom_name"],
                    "candidate_idx": candidate_idx,
                    "hotspot_score": cand.get("hotspot_score"),
                    "metric_sum": cand.get("metric_sum"),
                    "distance_to_skin_mm": cand.get("distance_to_skin_mm"),
                    "search_mode": cand.get("search_mode"),
                    "peak_sapd_w_m2": sapd_lookup.get(candidate_idx),
                }
            )

    candidate_df = pd.DataFrame(candidate_records)

    return summary_df, candidate_df


def plot_worst_case_sapd_heatmap(summary_df: pd.DataFrame, output_dir: Path) -> None:
    """Create a heatmap of worst-case SAPD values across frequencies and phantoms."""
    fig, ax = plt.subplots(figsize=(10, 6))

    # Pivot the data for heatmap
    pivot_data = summary_df.pivot(index="phantom", columns="frequency_ghz", values="worst_case_sapd_w_m2")

    # Convert to mW/m² for better readability
    pivot_data_mw = pivot_data * 1000

    sns.heatmap(pivot_data_mw, annot=True, fmt=".3f", cmap="YlOrRd", ax=ax, cbar_kws={"label": "Peak SAPD (mW/m²)"})

    ax.set_title("Worst-Case Peak SAPD Across Frequencies and Phantoms", fontsize=14, fontweight="bold")
    ax.set_xlabel("Frequency (GHz)", fontsize=12)
    ax.set_ylabel("Phantom", fontsize=12)

    plt.tight_layout()
    plt.savefig(output_dir / "worst_case_sapd_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: worst_case_sapd_heatmap.png")


def plot_sapd_by_frequency_boxplot(candidate_df: pd.DataFrame, output_dir: Path) -> None:
    """Create boxplots of SAPD distribution by frequency."""
    fig, ax = plt.subplots(figsize=(12, 6))

    # Convert to mW/m²
    df_plot = candidate_df.copy()
    df_plot["peak_sapd_mw_m2"] = df_plot["peak_sapd_w_m2"] * 1000

    sns.boxplot(data=df_plot, x="frequency_ghz", y="peak_sapd_mw_m2", hue="phantom", ax=ax)

    ax.set_title("Peak SAPD Distribution by Frequency and Phantom", fontsize=14, fontweight="bold")
    ax.set_xlabel("Frequency (GHz)", fontsize=12)
    ax.set_ylabel("Peak SAPD (mW/m²)", fontsize=12)
    ax.legend(title="Phantom", bbox_to_anchor=(1.02, 1), loc="upper left")

    plt.tight_layout()
    plt.savefig(output_dir / "sapd_by_frequency_boxplot.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: sapd_by_frequency_boxplot.png")


def plot_hotspot_score_distribution(candidate_df: pd.DataFrame, output_dir: Path) -> None:
    """Create violin plots of hotspot score distribution."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # By frequency
    sns.violinplot(data=candidate_df, x="frequency_ghz", y="hotspot_score", ax=axes[0], inner="box")
    axes[0].set_title("Hotspot Score Distribution by Frequency", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("Frequency (GHz)", fontsize=11)
    axes[0].set_ylabel("Hotspot Score", fontsize=11)

    # By phantom
    sns.violinplot(data=candidate_df, x="phantom", y="hotspot_score", ax=axes[1], inner="box")
    axes[1].set_title("Hotspot Score Distribution by Phantom", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("Phantom", fontsize=11)
    axes[1].set_ylabel("Hotspot Score", fontsize=11)

    plt.tight_layout()
    plt.savefig(output_dir / "hotspot_score_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: hotspot_score_distribution.png")


def plot_distance_to_skin_analysis(candidate_df: pd.DataFrame, output_dir: Path) -> None:
    """Analyze relationship between distance to skin and SAPD."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    # Convert SAPD to mW/m²
    df_plot = candidate_df.copy()
    df_plot["peak_sapd_mw_m2"] = df_plot["peak_sapd_w_m2"] * 1000

    # Scatter: Distance vs SAPD colored by frequency
    scatter = axes[0, 0].scatter(
        df_plot["distance_to_skin_mm"], df_plot["peak_sapd_mw_m2"], c=df_plot["frequency_ghz"], cmap="viridis", alpha=0.7, s=50
    )
    axes[0, 0].set_xlabel("Distance to Skin (mm)", fontsize=11)
    axes[0, 0].set_ylabel("Peak SAPD (mW/m²)", fontsize=11)
    axes[0, 0].set_title("Distance to Skin vs Peak SAPD", fontsize=12, fontweight="bold")
    plt.colorbar(scatter, ax=axes[0, 0], label="Frequency (GHz)")

    # Histogram of distances
    for freq in sorted(df_plot["frequency_ghz"].unique()):
        subset = df_plot[df_plot["frequency_ghz"] == freq]
        axes[0, 1].hist(subset["distance_to_skin_mm"], bins=20, alpha=0.5, label=f"{freq} GHz")
    axes[0, 1].set_xlabel("Distance to Skin (mm)", fontsize=11)
    axes[0, 1].set_ylabel("Count", fontsize=11)
    axes[0, 1].set_title("Distance to Skin Distribution", fontsize=12, fontweight="bold")
    axes[0, 1].legend()

    # Boxplot of distances by phantom
    sns.boxplot(data=df_plot, x="phantom", y="distance_to_skin_mm", hue="frequency_ghz", ax=axes[1, 0])
    axes[1, 0].set_xlabel("Phantom", fontsize=11)
    axes[1, 0].set_ylabel("Distance to Skin (mm)", fontsize=11)
    axes[1, 0].set_title("Distance to Skin by Phantom and Frequency", fontsize=12, fontweight="bold")
    axes[1, 0].legend(title="Freq (GHz)")

    # Scatter: Distance vs Hotspot Score
    scatter2 = axes[1, 1].scatter(
        df_plot["distance_to_skin_mm"], df_plot["hotspot_score"], c=df_plot["frequency_ghz"], cmap="viridis", alpha=0.7, s=50
    )
    axes[1, 1].set_xlabel("Distance to Skin (mm)", fontsize=11)
    axes[1, 1].set_ylabel("Hotspot Score", fontsize=11)
    axes[1, 1].set_title("Distance to Skin vs Hotspot Score", fontsize=12, fontweight="bold")
    plt.colorbar(scatter2, ax=axes[1, 1], label="Frequency (GHz)")

    plt.tight_layout()
    plt.savefig(output_dir / "distance_to_skin_analysis.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: distance_to_skin_analysis.png")


def plot_hotspot_vs_sapd_correlation(candidate_df: pd.DataFrame, output_dir: Path) -> None:
    """Plot correlation between hotspot score and actual SAPD."""
    df_plot = candidate_df.copy()
    df_plot["peak_sapd_mw_m2"] = df_plot["peak_sapd_w_m2"] * 1000

    frequencies = sorted(df_plot["frequency_ghz"].unique())
    n_freqs = len(frequencies)

    # Create subplots dynamically based on number of frequencies
    n_cols = min(n_freqs, 4)
    n_rows = (n_freqs + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 5 * n_rows), squeeze=False)
    axes = axes.flatten()

    colors = plt.cm.viridis(np.linspace(0, 1, len(frequencies)))

    for i, freq in enumerate(frequencies):
        subset = df_plot[df_plot["frequency_ghz"] == freq]

        axes[i].scatter(subset["hotspot_score"], subset["peak_sapd_mw_m2"], c=[colors[i]], alpha=0.6, s=60, label=f"{freq} GHz")

        # Add regression line
        valid = subset.dropna(subset=["hotspot_score", "peak_sapd_mw_m2"])
        if len(valid) > 2:
            z = np.polyfit(valid["hotspot_score"], valid["peak_sapd_mw_m2"], 1)
            p = np.poly1d(z)
            x_line = np.linspace(valid["hotspot_score"].min(), valid["hotspot_score"].max(), 100)
            axes[i].plot(x_line, p(x_line), "--", color="red", alpha=0.8, linewidth=2)

            # Calculate correlation
            corr = valid["hotspot_score"].corr(valid["peak_sapd_mw_m2"])
            axes[i].text(
                0.05,
                0.95,
                f"r = {corr:.3f}",
                transform=axes[i].transAxes,
                fontsize=11,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
            )

        axes[i].set_xlabel("Hotspot Score", fontsize=11)
        axes[i].set_ylabel("Peak SAPD (mW/m²)", fontsize=11)
        axes[i].set_title(f"{freq} GHz", fontsize=12, fontweight="bold")

    fig.suptitle("Correlation: Hotspot Score vs Peak SAPD", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / "hotspot_vs_sapd_correlation.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: hotspot_vs_sapd_correlation.png")


def plot_candidate_ranking(candidate_df: pd.DataFrame, output_dir: Path) -> None:
    """Plot SAPD values for each candidate ranked by hotspot score."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    axes = axes.flatten()

    df_plot = candidate_df.copy()
    df_plot["peak_sapd_mw_m2"] = df_plot["peak_sapd_w_m2"] * 1000

    phantoms = sorted(df_plot["phantom"].unique())

    for idx, phantom in enumerate(phantoms):
        if idx >= 4:
            break

        ax = axes[idx]
        phantom_data = df_plot[df_plot["phantom"] == phantom]

        for freq in sorted(phantom_data["frequency_ghz"].unique()):
            freq_data = (
                phantom_data[phantom_data["frequency_ghz"] == freq].sort_values("hotspot_score", ascending=False).reset_index(drop=True)
            )

            ax.plot(range(1, len(freq_data) + 1), freq_data["peak_sapd_mw_m2"], marker="o", label=f"{freq} GHz", linewidth=2, markersize=6)

        ax.set_xlabel("Candidate Rank (by Hotspot Score)", fontsize=11)
        ax.set_ylabel("Peak SAPD (mW/m²)", fontsize=11)
        ax.set_title(f"{phantom.capitalize()}", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)

    fig.suptitle("SAPD by Candidate Rank (Sorted by Hotspot Score)", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / "candidate_ranking.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: candidate_ranking.png")


def plot_summary_bar_chart(summary_df: pd.DataFrame, output_dir: Path) -> None:
    """Create a grouped bar chart of worst-case SAPD."""
    fig, ax = plt.subplots(figsize=(12, 6))

    df_plot = summary_df.copy()
    df_plot["worst_case_sapd_mw_m2"] = df_plot["worst_case_sapd_w_m2"] * 1000

    x = np.arange(len(df_plot["phantom"].unique()))
    width = 0.25
    frequencies = sorted(df_plot["frequency_ghz"].unique())

    for i, freq in enumerate(frequencies):
        freq_data = df_plot[df_plot["frequency_ghz"] == freq].sort_values("phantom")
        bars = ax.bar(x + i * width, freq_data["worst_case_sapd_mw_m2"], width, label=f"{freq} GHz")

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            if not np.isnan(height):
                ax.annotate(
                    f"{height:.2f}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

    ax.set_xlabel("Phantom", fontsize=12)
    ax.set_ylabel("Worst-Case Peak SAPD (mW/m²)", fontsize=12)
    ax.set_title("Worst-Case Peak SAPD Comparison", fontsize=14, fontweight="bold")
    ax.set_xticks(x + width)
    ax.set_xticklabels(sorted(df_plot["phantom"].unique()))
    ax.legend(title="Frequency")
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(output_dir / "summary_bar_chart.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: summary_bar_chart.png")


def plot_all_candidates_scatter(candidate_df: pd.DataFrame, output_dir: Path) -> None:
    """Create a comprehensive scatter plot of all candidates."""
    fig, ax = plt.subplots(figsize=(14, 8))

    df_plot = candidate_df.copy()
    df_plot["peak_sapd_mw_m2"] = df_plot["peak_sapd_w_m2"] * 1000

    # Create a combined label for coloring
    df_plot["freq_phantom"] = df_plot["frequency_ghz"].astype(str) + " GHz - " + df_plot["phantom"]

    sns.scatterplot(data=df_plot, x="hotspot_score", y="peak_sapd_mw_m2", hue="frequency_ghz", style="phantom", s=100, alpha=0.7, ax=ax)

    ax.set_xlabel("Hotspot Score", fontsize=12)
    ax.set_ylabel("Peak SAPD (mW/m²)", fontsize=12)
    ax.set_title("All Candidates: Hotspot Score vs Peak SAPD", fontsize=14, fontweight="bold")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", title="Frequency / Phantom")

    plt.tight_layout()
    plt.savefig(output_dir / "all_candidates_scatter.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: all_candidates_scatter.png")


def plot_frequency_comparison_lines(candidate_df: pd.DataFrame, output_dir: Path) -> None:
    """Create line plots comparing metrics across frequencies."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    df_plot = candidate_df.copy()
    df_plot["peak_sapd_mw_m2"] = df_plot["peak_sapd_w_m2"] * 1000

    # Group by frequency and phantom, calculate statistics
    stats = (
        df_plot.groupby(["frequency_ghz", "phantom"])
        .agg({"peak_sapd_mw_m2": ["mean", "std", "max"], "hotspot_score": ["mean", "std", "max"], "distance_to_skin_mm": ["mean", "std"]})
        .reset_index()
    )
    stats.columns = ["_".join(col).strip("_") for col in stats.columns.values]

    phantoms = sorted(df_plot["phantom"].unique())
    markers = ["o", "s", "^", "D"]

    # Mean SAPD
    for i, phantom in enumerate(phantoms):
        phantom_stats = stats[stats["phantom"] == phantom]
        axes[0, 0].errorbar(
            phantom_stats["frequency_ghz"],
            phantom_stats["peak_sapd_mw_m2_mean"],
            yerr=phantom_stats["peak_sapd_mw_m2_std"],
            marker=markers[i],
            label=phantom,
            capsize=5,
            linewidth=2,
            markersize=8,
        )
    axes[0, 0].set_xlabel("Frequency (GHz)", fontsize=11)
    axes[0, 0].set_ylabel("Mean Peak SAPD (mW/m²)", fontsize=11)
    axes[0, 0].set_title("Mean Peak SAPD by Frequency", fontsize=12, fontweight="bold")
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # Max SAPD
    for i, phantom in enumerate(phantoms):
        phantom_stats = stats[stats["phantom"] == phantom]
        axes[0, 1].plot(
            phantom_stats["frequency_ghz"],
            phantom_stats["peak_sapd_mw_m2_max"],
            marker=markers[i],
            label=phantom,
            linewidth=2,
            markersize=8,
        )
    axes[0, 1].set_xlabel("Frequency (GHz)", fontsize=11)
    axes[0, 1].set_ylabel("Max Peak SAPD (mW/m²)", fontsize=11)
    axes[0, 1].set_title("Maximum Peak SAPD by Frequency", fontsize=12, fontweight="bold")
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

    # Mean Hotspot Score
    for i, phantom in enumerate(phantoms):
        phantom_stats = stats[stats["phantom"] == phantom]
        axes[1, 0].errorbar(
            phantom_stats["frequency_ghz"],
            phantom_stats["hotspot_score_mean"],
            yerr=phantom_stats["hotspot_score_std"],
            marker=markers[i],
            label=phantom,
            capsize=5,
            linewidth=2,
            markersize=8,
        )
    axes[1, 0].set_xlabel("Frequency (GHz)", fontsize=11)
    axes[1, 0].set_ylabel("Mean Hotspot Score", fontsize=11)
    axes[1, 0].set_title("Mean Hotspot Score by Frequency", fontsize=12, fontweight="bold")
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

    # Mean Distance to Skin
    for i, phantom in enumerate(phantoms):
        phantom_stats = stats[stats["phantom"] == phantom]
        axes[1, 1].errorbar(
            phantom_stats["frequency_ghz"],
            phantom_stats["distance_to_skin_mm_mean"],
            yerr=phantom_stats["distance_to_skin_mm_std"],
            marker=markers[i],
            label=phantom,
            capsize=5,
            linewidth=2,
            markersize=8,
        )
    axes[1, 1].set_xlabel("Frequency (GHz)", fontsize=11)
    axes[1, 1].set_ylabel("Mean Distance to Skin (mm)", fontsize=11)
    axes[1, 1].set_title("Mean Distance to Skin by Frequency", fontsize=12, fontweight="bold")
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "frequency_comparison_lines.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: frequency_comparison_lines.png")


def create_summary_statistics_table(summary_df: pd.DataFrame, candidate_df: pd.DataFrame, output_dir: Path) -> None:
    """Create a summary statistics table and save as CSV."""

    # Overall statistics
    df_plot = candidate_df.copy()
    df_plot["peak_sapd_mw_m2"] = df_plot["peak_sapd_w_m2"] * 1000

    overall_stats = (
        df_plot.groupby(["frequency_ghz", "phantom"])
        .agg(
            {
                "peak_sapd_mw_m2": ["count", "mean", "std", "min", "max"],
                "hotspot_score": ["mean", "std", "min", "max"],
                "distance_to_skin_mm": ["mean", "std", "min", "max"],
            }
        )
        .round(4)
    )

    overall_stats.to_csv(output_dir / "summary_statistics.csv")
    print("Saved: summary_statistics.csv")

    # Also create a simple worst-case summary
    worst_case_summary = summary_df[["frequency_ghz", "phantom", "worst_case_sapd_w_m2", "worst_case_candidate_idx"]].copy()
    worst_case_summary["worst_case_sapd_mw_m2"] = worst_case_summary["worst_case_sapd_w_m2"] * 1000
    worst_case_summary = worst_case_summary.sort_values(["frequency_ghz", "phantom"])
    worst_case_summary.to_csv(output_dir / "worst_case_summary.csv", index=False)
    print("Saved: worst_case_summary.csv")


def plot_pairplot(candidate_df: pd.DataFrame, output_dir: Path) -> None:
    """Create a pairplot of key metrics."""
    df_plot = candidate_df[["frequency_ghz", "phantom", "hotspot_score", "distance_to_skin_mm", "peak_sapd_w_m2"]].copy()
    df_plot["peak_sapd_mw_m2"] = df_plot["peak_sapd_w_m2"] * 1000
    df_plot = df_plot.drop(columns=["peak_sapd_w_m2"])
    df_plot = df_plot.dropna()

    g = sns.pairplot(df_plot, hue="frequency_ghz", diag_kind="kde", plot_kws={"alpha": 0.6, "s": 40}, height=2.5)
    g.fig.suptitle("Pairplot of Key Metrics", y=1.02, fontsize=14, fontweight="bold")

    plt.savefig(output_dir / "pairplot.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: pairplot.png")


def plot_spatial_proxy_scores(base_dir: Path, output_dir: Path) -> None:
    """
    Create spatial visualizations of proxy scores with candidate locations overlaid.

    For each phantom, creates 2D projections (XY, XZ, YZ) showing:
    - All proxy scores as colored scatter points
    - Candidate locations as markers
    - Winning candidate (highest SAPD) highlighted
    """
    # Find all frequency folders
    freq_folders = sorted([f for f in base_dir.iterdir() if f.is_dir() and f.name.endswith("GHz")])

    # Get all phantoms
    all_phantoms = set()
    for freq_folder in freq_folders:
        phantom_folders = [f for f in freq_folder.iterdir() if f.is_dir()]
        for pf in phantom_folders:
            all_phantoms.add(pf.name)

    all_phantoms = sorted(all_phantoms)

    # Create a separate figure for each phantom
    for phantom in all_phantoms:
        print(f"  Creating spatial plot for {phantom}...")

        # Collect data across all frequencies for this phantom
        freq_data = []

        for freq_folder in freq_folders:
            freq_ghz = int(freq_folder.name.replace("GHz", ""))
            phantom_folder = freq_folder / phantom

            if not phantom_folder.exists():
                continue

            # Look for proxy scores CSV
            proxy_csv = phantom_folder / "auto_induced" / "all_proxy_scores.csv"
            summary_json = phantom_folder / "auto_induced" / "auto_induced_summary.json"

            if not proxy_csv.exists() or not summary_json.exists():
                continue

            # Load proxy scores
            proxy_df = pd.read_csv(proxy_csv)

            # Load summary for candidates
            with open(summary_json) as f:
                summary = json.load(f)

            freq_data.append({"freq_ghz": freq_ghz, "proxy_df": proxy_df, "summary": summary})

        if not freq_data:
            print(f"    No data found for {phantom}, skipping...")
            continue

        # Create figure with subplots: one row per frequency, 3 columns for XY, XZ, YZ projections
        n_freqs = len(freq_data)
        fig, axes = plt.subplots(n_freqs, 3, figsize=(18, 5 * n_freqs), squeeze=False)

        for row_idx, data in enumerate(freq_data):
            freq_ghz = data["freq_ghz"]
            proxy_df = data["proxy_df"]
            summary = data["summary"]

            # Get candidate info
            candidates = summary.get("candidates", [])
            sapd_results = summary.get("sapd_results", [])
            worst_case = summary.get("worst_case", {})
            worst_candidate_idx = worst_case.get("candidate_idx")

            # Create lookup for SAPD by candidate index
            sapd_lookup = {r["candidate_idx"]: r["peak_sapd_w_m2"] for r in sapd_results}

            # Get candidate positions from proxy_df using voxel indices
            candidate_positions = []
            for i, cand in enumerate(candidates):
                cand_idx = i + 1  # 1-indexed
                voxel_idx = cand.get("voxel_idx", [])
                if len(voxel_idx) >= 3:
                    # voxel_idx is stored as strings in JSON
                    vx, vy, vz = int(voxel_idx[0]), int(voxel_idx[1]), int(voxel_idx[2])

                    # Find matching row in proxy_df
                    match = proxy_df[(proxy_df["voxel_x"] == vx) & (proxy_df["voxel_y"] == vy) & (proxy_df["voxel_z"] == vz)]

                    if not match.empty:
                        row = match.iloc[0]
                        candidate_positions.append(
                            {
                                "idx": cand_idx,
                                "x_mm": row["x_mm"],
                                "y_mm": row["y_mm"],
                                "z_mm": row["z_mm"],
                                "hotspot_score": cand.get("hotspot_score", 0),
                                "sapd": sapd_lookup.get(cand_idx, 0),
                                "is_worst": cand_idx == worst_candidate_idx,
                            }
                        )

            # Subsample proxy_df for plotting (too many points otherwise)
            plot_df = proxy_df.sample(n=min(5000, len(proxy_df)), random_state=42)

            # Projections: XY (top view), XZ (front view), YZ (side view)
            projections = [
                ("x_mm", "y_mm", "XY Projection (Top View)"),
                ("x_mm", "z_mm", "XZ Projection (Front View)"),
                ("y_mm", "z_mm", "YZ Projection (Side View)"),
            ]

            for col_idx, (x_col, y_col, title) in enumerate(projections):
                ax = axes[row_idx, col_idx]

                # Plot proxy scores as background
                scatter = ax.scatter(
                    plot_df[x_col],
                    plot_df[y_col],
                    c=plot_df["proxy_score"],
                    cmap="viridis",
                    s=5,
                    alpha=0.4,
                    vmin=0,
                    vmax=plot_df["proxy_score"].quantile(0.95),
                )

                # Plot candidates
                for cand in candidate_positions:
                    if cand["is_worst"]:
                        # Winning candidate - large red star
                        ax.scatter(
                            cand[x_col],
                            cand[y_col],
                            c="red",
                            s=300,
                            marker="*",
                            edgecolors="white",
                            linewidths=2,
                            zorder=10,
                            label=f"Winner (#{cand['idx']})" if col_idx == 0 else "",
                        )
                    else:
                        # Other candidates - smaller circles
                        ax.scatter(
                            cand[x_col], cand[y_col], c="orange", s=80, marker="o", edgecolors="black", linewidths=1, zorder=5, alpha=0.8
                        )

                # Add colorbar only for first column
                if col_idx == 0:
                    cbar = plt.colorbar(scatter, ax=ax)
                    cbar.set_label("Proxy Score", fontsize=10)

                ax.set_xlabel(f"{x_col.replace('_mm', '')} (mm)", fontsize=10)
                ax.set_ylabel(f"{y_col.replace('_mm', '')} (mm)", fontsize=10)
                ax.set_title(f"{freq_ghz} GHz - {title}", fontsize=11, fontweight="bold")
                ax.set_aspect("equal", adjustable="box")

        # Add overall title and legend
        fig.suptitle(
            f"Spatial Proxy Score Distribution - {phantom.capitalize()}\n(* = Winning Candidate, o = Other Candidates)",
            fontsize=14,
            fontweight="bold",
            y=1.02,
        )

        plt.tight_layout()
        plt.savefig(output_dir / f"spatial_proxy_scores_{phantom}.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    Saved: spatial_proxy_scores_{phantom}.png")


def plot_spatial_3d_interactive(base_dir: Path, output_dir: Path) -> None:
    """
    Create 3D scatter plots of proxy scores with candidates for each phantom.
    Uses matplotlib 3D projection (static images).
    """
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    # Find all frequency folders
    freq_folders = sorted([f for f in base_dir.iterdir() if f.is_dir() and f.name.endswith("GHz")])

    # Get all phantoms
    all_phantoms = set()
    for freq_folder in freq_folders:
        phantom_folders = [f for f in freq_folder.iterdir() if f.is_dir()]
        for pf in phantom_folders:
            all_phantoms.add(pf.name)

    all_phantoms = sorted(all_phantoms)

    for phantom in all_phantoms:
        print(f"  Creating 3D spatial plot for {phantom}...")

        # Use the first available frequency for 3D visualization
        for freq_folder in freq_folders:
            freq_ghz = int(freq_folder.name.replace("GHz", ""))
            phantom_folder = freq_folder / phantom

            proxy_csv = phantom_folder / "auto_induced" / "all_proxy_scores.csv"
            summary_json = phantom_folder / "auto_induced" / "auto_induced_summary.json"

            if not proxy_csv.exists() or not summary_json.exists():
                continue

            # Load data
            proxy_df = pd.read_csv(proxy_csv)
            with open(summary_json) as f:
                summary = json.load(f)

            # Get candidate info
            candidates = summary.get("candidates", [])
            sapd_results = summary.get("sapd_results", [])
            worst_case = summary.get("worst_case", {})
            worst_candidate_idx = worst_case.get("candidate_idx")

            sapd_lookup = {r["candidate_idx"]: r["peak_sapd_w_m2"] for r in sapd_results}

            # Get candidate positions
            candidate_positions = []
            for i, cand in enumerate(candidates):
                cand_idx = i + 1
                voxel_idx = cand.get("voxel_idx", [])
                if len(voxel_idx) >= 3:
                    vx, vy, vz = int(voxel_idx[0]), int(voxel_idx[1]), int(voxel_idx[2])
                    match = proxy_df[(proxy_df["voxel_x"] == vx) & (proxy_df["voxel_y"] == vy) & (proxy_df["voxel_z"] == vz)]
                    if not match.empty:
                        row = match.iloc[0]
                        candidate_positions.append(
                            {
                                "idx": cand_idx,
                                "x_mm": row["x_mm"],
                                "y_mm": row["y_mm"],
                                "z_mm": row["z_mm"],
                                "hotspot_score": cand.get("hotspot_score", 0),
                                "sapd": sapd_lookup.get(cand_idx, 0),
                                "is_worst": cand_idx == worst_candidate_idx,
                            }
                        )

            # Subsample for 3D plot
            plot_df = proxy_df.sample(n=min(3000, len(proxy_df)), random_state=42)

            # Create 3D figure
            fig = plt.figure(figsize=(14, 10))
            ax = fig.add_subplot(111, projection="3d")

            # Plot proxy scores
            scatter = ax.scatter(
                plot_df["x_mm"],
                plot_df["y_mm"],
                plot_df["z_mm"],
                c=plot_df["proxy_score"],
                cmap="viridis",
                s=3,
                alpha=0.3,
                vmin=0,
                vmax=plot_df["proxy_score"].quantile(0.95),
            )

            # Plot candidates
            for cand in candidate_positions:
                if cand["is_worst"]:
                    ax.scatter(
                        cand["x_mm"],
                        cand["y_mm"],
                        cand["z_mm"],
                        c="red",
                        s=400,
                        marker="*",
                        edgecolors="white",
                        linewidths=2,
                        zorder=10,
                        label=f"Winner (#{cand['idx']}, SAPD={cand['sapd'] * 1000:.3f} mW/m²)",
                    )
                else:
                    ax.scatter(
                        cand["x_mm"],
                        cand["y_mm"],
                        cand["z_mm"],
                        c="orange",
                        s=100,
                        marker="o",
                        edgecolors="black",
                        linewidths=1,
                        zorder=5,
                        alpha=0.8,
                    )

            cbar = plt.colorbar(scatter, ax=ax, shrink=0.6, pad=0.1)
            cbar.set_label("Proxy Score", fontsize=11)

            ax.set_xlabel("X (mm)", fontsize=11)
            ax.set_ylabel("Y (mm)", fontsize=11)
            ax.set_zlabel("Z (mm)", fontsize=11)
            ax.set_title(
                f"3D Proxy Score Distribution - {phantom.capitalize()} @ {freq_ghz} GHz\n(* = Winning Candidate, o = Other Candidates)",
                fontsize=13,
                fontweight="bold",
            )
            ax.legend(loc="upper left")

            plt.tight_layout()
            plt.savefig(output_dir / f"spatial_3d_{phantom}_{freq_ghz}GHz.png", dpi=150, bbox_inches="tight")
            plt.close()
            print(f"    Saved: spatial_3d_{phantom}_{freq_ghz}GHz.png")

            break  # Only do first frequency for 3D


def main(base_dir: Path, output_dir: Path | None = None) -> None:
    """Main function to generate all visualizations."""

    if output_dir is None:
        output_dir = base_dir / "visualizations"

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Auto-Induced FR3 Results Visualization")
    print("=" * 60)
    print(f"\nBase directory: {base_dir}")
    print(f"Output directory: {output_dir}\n")

    # Load all results
    print("Loading results...")
    results = load_all_results(base_dir)

    if not results:
        print("No results found!")
        return

    print(f"\nLoaded {len(results)} result files.\n")

    # Create DataFrames
    print("Creating DataFrames...")
    summary_df, candidate_df = create_dataframes(results)

    print(f"Summary DataFrame: {len(summary_df)} rows")
    print(f"Candidate DataFrame: {len(candidate_df)} rows\n")

    # Generate all plots
    print("Generating visualizations...")
    print("-" * 40)

    plot_worst_case_sapd_heatmap(summary_df, output_dir)
    plot_sapd_by_frequency_boxplot(candidate_df, output_dir)
    plot_hotspot_score_distribution(candidate_df, output_dir)
    plot_distance_to_skin_analysis(candidate_df, output_dir)
    plot_hotspot_vs_sapd_correlation(candidate_df, output_dir)
    plot_candidate_ranking(candidate_df, output_dir)
    plot_summary_bar_chart(summary_df, output_dir)
    plot_all_candidates_scatter(candidate_df, output_dir)
    plot_frequency_comparison_lines(candidate_df, output_dir)
    plot_pairplot(candidate_df, output_dir)
    create_summary_statistics_table(summary_df, candidate_df, output_dir)

    # Spatial visualizations (per phantom)
    print("\nGenerating spatial visualizations...")
    print("-" * 40)
    plot_spatial_proxy_scores(base_dir, output_dir)
    plot_spatial_3d_interactive(base_dir, output_dir)

    print("-" * 40)
    print(f"\nAll visualizations saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Visualize auto_induced_FR3 results")
    parser.add_argument("--base-dir", type=Path, default=Path("results/auto_induced_FR3"), help="Base directory containing the results")
    parser.add_argument(
        "--output-dir", type=Path, default=None, help="Output directory for visualizations (default: base_dir/visualizations)"
    )

    args = parser.parse_args()

    main(args.base_dir, args.output_dir)
