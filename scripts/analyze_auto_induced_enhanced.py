#!/usr/bin/env python3
"""
Enhanced statistical analysis of auto-induced exposure FR3 results.

This script creates:
1. Enhanced violin plots with dual SAPD axis and max SAPD markers
2. Improved distribution spread with exponential/polynomial fits
3. Pairplot using only top 20 candidates (not all proxy scores)

Author: Generated for GOLIAT project
Date: 2026-02-01
"""

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.optimize import curve_fit

# Set style for all plots
plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams["font.size"] = 11
plt.rcParams["axes.labelsize"] = 12
plt.rcParams["axes.titlesize"] = 13
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["figure.dpi"] = 150

# Phantom display names and colors
PHANTOM_COLORS = {
    "duke": "#1f77b4",  # Blue
    "ella": "#ff7f0e",  # Orange
    "eartha": "#2ca02c",  # Green
    "thelonious": "#d62728",  # Red
}

PHANTOM_LABELS = {
    "duke": "Duke (34y M)",
    "ella": "Ella (26y F)",
    "eartha": "Eartha (8y F)",
    "thelonious": "Thelonious (6y M)",
}


def load_all_results(base_dir: Path) -> list[dict[str, Any]]:
    """Load all auto_induced_summary.json files from the results directory."""
    results = []
    freq_folders = sorted([f for f in base_dir.iterdir() if f.is_dir() and f.name.endswith("GHz")])

    for freq_folder in freq_folders:
        freq_ghz = int(freq_folder.name.replace("GHz", ""))
        phantom_folders = [f for f in freq_folder.iterdir() if f.is_dir()]

        for phantom_folder in phantom_folders:
            phantom_name = phantom_folder.name
            summary_file = phantom_folder / "auto_induced" / "auto_induced_summary.json"

            if summary_file.exists():
                with open(summary_file) as f:
                    data = json.load(f)
                    data["freq_ghz"] = freq_ghz
                    data["phantom_name"] = phantom_name
                    results.append(data)

    return results


def create_candidate_dataframe(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Create DataFrame with all candidate data (hotspot score + SAPD)."""
    records = []
    for r in results:
        candidates = r.get("candidates", [])
        sapd_results = r.get("sapd_results", [])
        sapd_lookup = {s["candidate_idx"]: s.get("peak_sapd_w_m2") for s in sapd_results}

        for i, cand in enumerate(candidates):
            candidate_idx = i + 1
            records.append(
                {
                    "freq_ghz": r["freq_ghz"],
                    "phantom": r["phantom_name"],
                    "candidate_idx": candidate_idx,
                    "hotspot_score": cand.get("hotspot_score"),
                    "distance_to_skin_mm": cand.get("distance_to_skin_mm"),
                    "peak_sapd_w_m2": sapd_lookup.get(candidate_idx),
                }
            )

    df = pd.DataFrame(records)
    df["peak_sapd_mw_m2"] = df["peak_sapd_w_m2"] * 1000
    return df


def load_model_parameters(stats_dir: Path) -> dict:
    """Load the linear model parameters."""
    model_file = stats_dir / "linear_model_parameters.json"
    if model_file.exists():
        with open(model_file) as f:
            return json.load(f)
    return {"slope_alpha": 5.03, "intercept_beta": 0.21, "r_squared": 0.79}


# =============================================================================
# ENHANCED VIOLIN PLOT WITH DUAL AXIS + MAX SAPD MARKERS
# =============================================================================


def create_enhanced_violin_distribution(candidate_df: pd.DataFrame, model: dict, output_dir: Path):
    """
    Create enhanced violin plots with:
    - Secondary y-axis for predicted SAPD
    - Max SAPD markers per phantom (colored dots)
    - Lines connecting same phantom across frequencies
    """
    alpha = model["slope_alpha"]
    beta = model["intercept_beta"]

    frequencies = sorted(candidate_df["freq_ghz"].unique())
    phantoms = sorted(candidate_df["phantom"].unique())

    # Calculate max SAPD per frequency/phantom
    max_sapd = candidate_df.groupby(["freq_ghz", "phantom"])["peak_sapd_mw_m2"].max().reset_index()
    max_hs = candidate_df.groupby(["freq_ghz", "phantom"])["hotspot_score"].max().reset_index()

    # Figure 1: By Frequency with phantom markers
    fig, ax1 = plt.subplots(figsize=(12, 7))

    # Violin plot
    sns.violinplot(
        data=candidate_df,
        x="freq_ghz",
        y="hotspot_score",
        ax=ax1,
        inner="box",
        color="lightcoral",
        alpha=0.7,
    )

    # Add max SAPD dots for each phantom
    freq_positions = {f: i for i, f in enumerate(frequencies)}

    for phantom in phantoms:
        phantom_data = max_sapd[max_sapd["phantom"] == phantom].sort_values("freq_ghz")
        phantom_hs = max_hs[max_hs["phantom"] == phantom].sort_values("freq_ghz")

        x_positions = [freq_positions[f] for f in phantom_data["freq_ghz"]]

        # Plot max hotspot scores as dots
        ax1.scatter(
            x_positions,
            phantom_hs["hotspot_score"],
            c=PHANTOM_COLORS[phantom],
            s=100,
            zorder=5,
            label=PHANTOM_LABELS[phantom],
            edgecolors="black",
            linewidth=1,
            marker="o",
        )

        # Connect with lines
        ax1.plot(
            x_positions,
            phantom_hs["hotspot_score"],
            c=PHANTOM_COLORS[phantom],
            linewidth=2,
            alpha=0.7,
            zorder=4,
        )

    ax1.set_xlabel("Frequency (GHz)", fontsize=12)
    ax1.set_ylabel("Hotspot Score (mean |E|²)", fontsize=12, color="darkred")
    ax1.tick_params(axis="y", labelcolor="darkred")
    ax1.set_title("Hotspot Score Distribution by Frequency\n(Markers = Max per Phantom)", fontsize=13, fontweight="bold")

    # Secondary y-axis for predicted SAPD
    ax2 = ax1.twinx()
    hs_min, hs_max = ax1.get_ylim()
    sapd_min = alpha * hs_min + beta
    sapd_max = alpha * hs_max + beta
    ax2.set_ylim(sapd_min, sapd_max)
    ax2.set_ylabel("Predicted SAPD (mW/m²)", fontsize=12, color="darkgreen")
    ax2.tick_params(axis="y", labelcolor="darkgreen")

    ax1.legend(loc="upper right", fontsize=9)

    plt.tight_layout()
    plt.savefig(output_dir / "violin_by_frequency_enhanced.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("Saved: violin_by_frequency_enhanced.png")

    # Figure 2: By Phantom with frequency markers
    fig, ax1 = plt.subplots(figsize=(12, 7))

    # Violin plot
    phantom_order = ["duke", "ella", "eartha", "thelonious"]
    sns.violinplot(
        data=candidate_df,
        x="phantom",
        y="hotspot_score",
        order=phantom_order,
        ax=ax1,
        inner="box",
        color="lightcoral",
        alpha=0.7,
    )

    # Add max SAPD dots for each frequency
    phantom_positions = {p: i for i, p in enumerate(phantom_order)}
    freq_colors = plt.cm.viridis(np.linspace(0.1, 0.9, len(frequencies)))
    freq_color_map = dict(zip(frequencies, freq_colors))

    for freq in frequencies:
        freq_data = max_sapd[max_sapd["freq_ghz"] == freq]
        freq_hs = max_hs[max_hs["freq_ghz"] == freq]

        x_positions = [phantom_positions[p] for p in freq_data["phantom"]]

        # Plot max hotspot scores as dots
        ax1.scatter(
            x_positions,
            freq_hs["hotspot_score"],
            c=[freq_color_map[freq]],
            s=100,
            zorder=5,
            label=f"{freq} GHz",
            edgecolors="black",
            linewidth=1,
            marker="o",
        )

        # Connect with lines across phantoms for same frequency
        sorted_data = freq_hs.copy()
        sorted_data["x_pos"] = sorted_data["phantom"].map(phantom_positions)
        sorted_data = sorted_data.sort_values("x_pos")

        ax1.plot(
            sorted_data["x_pos"],
            sorted_data["hotspot_score"],
            c=freq_color_map[freq],
            linewidth=2,
            alpha=0.7,
            zorder=4,
        )

    ax1.set_xlabel("Phantom", fontsize=12)
    ax1.set_ylabel("Hotspot Score (mean |E|²)", fontsize=12, color="darkred")
    ax1.tick_params(axis="y", labelcolor="darkred")
    ax1.set_xticklabels([PHANTOM_LABELS.get(p, p) for p in phantom_order], rotation=15)
    ax1.set_title("Hotspot Score Distribution by Phantom\n(Markers = Max per Frequency)", fontsize=13, fontweight="bold")

    # Secondary y-axis for predicted SAPD
    ax2 = ax1.twinx()
    hs_min, hs_max = ax1.get_ylim()
    sapd_min = alpha * hs_min + beta
    sapd_max = alpha * hs_max + beta
    ax2.set_ylim(sapd_min, sapd_max)
    ax2.set_ylabel("Predicted SAPD (mW/m²)", fontsize=12, color="darkgreen")
    ax2.tick_params(axis="y", labelcolor="darkgreen")

    ax1.legend(loc="upper right", fontsize=9, ncol=2)

    plt.tight_layout()
    plt.savefig(output_dir / "violin_by_phantom_enhanced.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("Saved: violin_by_phantom_enhanced.png")


# =============================================================================
# DISTRIBUTION SPREAD WITH EXPONENTIAL FIT
# =============================================================================


def create_distribution_spread_analysis(proxy_df: pd.DataFrame, output_dir: Path):
    """
    Analyze distribution spread (std dev) with exponential/polynomial fits.
    """
    if proxy_df.empty:
        print("No proxy data for spread analysis")
        return

    # Calculate statistics by frequency
    stats_by_freq = proxy_df.groupby("freq_ghz")["proxy_score"].agg(["mean", "std", "max"])
    stats_by_freq = stats_by_freq.reset_index()

    x = stats_by_freq["freq_ghz"].values
    y = stats_by_freq["std"].values

    # Fit different models
    # 1. Exponential decay: y = a * exp(-b * x) + c
    def exp_decay(x, a, b, c):
        return a * np.exp(-b * x) + c

    # 2. Polynomial (quadratic)
    poly_coeffs = np.polyfit(x, y, 2)
    poly_func = np.poly1d(poly_coeffs)

    # 3. Power law: y = a * x^b
    def power_law(x, a, b):
        return a * np.power(x, b)

    # Try exponential fit
    try:
        popt_exp, _ = curve_fit(exp_decay, x, y, p0=[0.1, 0.1, 0.01], maxfev=5000)
        y_exp = exp_decay(x, *popt_exp)
        r2_exp = 1 - np.sum((y - y_exp) ** 2) / np.sum((y - np.mean(y)) ** 2)
    except Exception:
        popt_exp = None
        r2_exp = 0

    # Polynomial R²
    y_poly = poly_func(x)
    r2_poly = 1 - np.sum((y - y_poly) ** 2) / np.sum((y - np.mean(y)) ** 2)

    # Try power law fit
    try:
        popt_pow, _ = curve_fit(power_law, x, y, p0=[1, -1], maxfev=5000)
        y_pow = power_law(x, *popt_pow)
        r2_pow = 1 - np.sum((y - y_pow) ** 2) / np.sum((y - np.mean(y)) ** 2)
    except Exception:
        popt_pow = None
        r2_pow = 0

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 7))

    # Bar plot of std dev
    ax.bar(x, y, color="steelblue", alpha=0.7, width=1.5, label="Std Dev", edgecolor="navy")

    # X values for smooth curves
    x_smooth = np.linspace(x.min() - 0.5, x.max() + 0.5, 100)

    # Plot fits
    if popt_exp is not None:
        ax.plot(x_smooth, exp_decay(x_smooth, *popt_exp), "r-", linewidth=2.5, label=f"Exponential: R² = {r2_exp:.3f}")

    ax.plot(x_smooth, poly_func(x_smooth), "g--", linewidth=2.5, label=f"Polynomial (deg 2): R² = {r2_poly:.3f}")

    if popt_pow is not None:
        ax.plot(x_smooth, power_law(x_smooth, *popt_pow), "m:", linewidth=2.5, label=f"Power law: R² = {r2_pow:.3f}")

    ax.set_xlabel("Frequency (GHz)", fontsize=12)
    ax.set_ylabel("Standard Deviation of Hotspot Score", fontsize=12)
    ax.set_title("Distribution Spread vs Frequency\n(Sharpening with Increasing Frequency)", fontsize=13, fontweight="bold")
    ax.legend(loc="upper right", fontsize=10)
    ax.set_xlim(5.5, 16.5)
    ax.set_xticks(x)
    ax.grid(True, alpha=0.3, axis="y")

    # Add best fit info
    best_r2 = max(r2_exp, r2_poly, r2_pow)
    if best_r2 == r2_exp:
        best_model = f"Exponential: std = {popt_exp[0]:.3f}·e^(-{popt_exp[1]:.3f}·f) + {popt_exp[2]:.4f}"
    elif best_r2 == r2_poly:
        best_model = f"Polynomial: std = {poly_coeffs[0]:.5f}·f² + {poly_coeffs[1]:.4f}·f + {poly_coeffs[2]:.3f}"
    else:
        best_model = f"Power law: std = {popt_pow[0]:.3f}·f^({popt_pow[1]:.2f})"

    ax.text(
        0.02,
        0.02,
        f"Best fit: {best_model}",
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
    )

    plt.tight_layout()
    plt.savefig(output_dir / "distribution_spread_fits.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("Saved: distribution_spread_fits.png")

    # Print results
    print("\n" + "=" * 60)
    print("DISTRIBUTION SPREAD FIT RESULTS")
    print("=" * 60)
    print(f"Exponential R²: {r2_exp:.4f}")
    print(f"Polynomial R²:  {r2_poly:.4f}")
    print(f"Power Law R²:   {r2_pow:.4f}")
    print(f"Best model: {best_model}")
    print("=" * 60)


# =============================================================================
# PAIRPLOT WITH TOP 20 CANDIDATES ONLY
# =============================================================================


def create_pairplot_top20(candidate_df: pd.DataFrame, output_dir: Path):
    """
    Create pairplot using only the top 20 candidates per frequency/phantom.
    This uses the actual candidate data (not all proxy scores).
    """
    # candidate_df already contains only top 20 per combination
    # Select columns for pairplot
    plot_df = candidate_df[["freq_ghz", "phantom", "hotspot_score", "distance_to_skin_mm", "peak_sapd_mw_m2"]].dropna()

    # Rename for cleaner labels
    plot_df = plot_df.rename(
        columns={
            "hotspot_score": "Hotspot Score",
            "distance_to_skin_mm": "Distance to Skin (mm)",
            "peak_sapd_mw_m2": "Peak SAPD (mW/m²)",
            "freq_ghz": "Frequency (GHz)",
        }
    )

    # Create pairplot colored by frequency
    g = sns.pairplot(
        plot_df,
        hue="Frequency (GHz)",
        palette="viridis",
        diag_kind="kde",
        plot_kws={"alpha": 0.6, "s": 40, "edgecolor": "white"},
        diag_kws={"alpha": 0.6},
        corner=False,
    )

    g.fig.suptitle("Pairplot: Top 20 Candidates per Phantom/Frequency\n(400 total data points)", y=1.02, fontsize=13, fontweight="bold")

    plt.tight_layout()
    plt.savefig(output_dir / "pairplot_top20_by_frequency.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: pairplot_top20_by_frequency.png")

    # Also create one colored by phantom
    g = sns.pairplot(
        plot_df,
        hue="phantom",
        palette=PHANTOM_COLORS,
        diag_kind="kde",
        plot_kws={"alpha": 0.6, "s": 40, "edgecolor": "white"},
        diag_kws={"alpha": 0.6},
        corner=False,
    )

    g.fig.suptitle("Pairplot: Top 20 Candidates per Phantom/Frequency\n(400 total data points)", y=1.02, fontsize=13, fontweight="bold")

    plt.tight_layout()
    plt.savefig(output_dir / "pairplot_top20_by_phantom.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: pairplot_top20_by_phantom.png")


# =============================================================================
# INDIVIDUAL DISTRIBUTION PLOTS FOR SUPPLEMENTARY
# =============================================================================


def create_individual_distribution_plots(proxy_df: pd.DataFrame, output_dir: Path):
    """
    Create individual distribution plots for each phantom/frequency.
    These are for supplementary materials - one figure per combination.
    """
    if proxy_df.empty:
        print("No proxy data for individual plots")
        return

    supp_dir = output_dir / "supplementary_distributions"
    supp_dir.mkdir(parents=True, exist_ok=True)

    frequencies = sorted(proxy_df["freq_ghz"].unique())
    phantoms = sorted(proxy_df["phantom"].unique())

    for phantom in phantoms:
        for freq in frequencies:
            data = proxy_df[(proxy_df["phantom"] == phantom) & (proxy_df["freq_ghz"] == freq)]["proxy_score"]

            if data.empty:
                continue

            fig, ax = plt.subplots(figsize=(8, 5))

            ax.hist(data, bins=60, alpha=0.7, color=PHANTOM_COLORS.get(phantom, "steelblue"), edgecolor="white", density=True)

            # Add statistics
            ax.axvline(data.mean(), color="red", linestyle="--", linewidth=2, label=f"Mean: {data.mean():.4f}")
            ax.axvline(data.quantile(0.95), color="orange", linestyle="--", linewidth=2, label=f"95th %ile: {data.quantile(0.95):.4f}")
            ax.axvline(data.max(), color="darkred", linestyle="-", linewidth=2, label=f"Max: {data.max():.4f}")

            ax.set_xlabel("Hotspot Score (proxy)", fontsize=11)
            ax.set_ylabel("Density", fontsize=11)
            ax.set_title(f"Hotspot Score Distribution\n{PHANTOM_LABELS.get(phantom, phantom)} @ {freq} GHz", fontsize=12, fontweight="bold")
            ax.legend(loc="upper right", fontsize=9)
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(supp_dir / f"dist_{phantom}_{freq}GHz.png", dpi=150, bbox_inches="tight")
            plt.close()

    print(f"Saved {len(frequencies) * len(phantoms)} individual distribution plots to: {supp_dir}")


# =============================================================================
# IEEE DOUBLE-COLUMN WIDE VIOLIN PLOT (LOG SCALE)
# =============================================================================


def create_ieee_wide_violin_log(proxy_df: pd.DataFrame, model: dict, output_dir: Path):
    """
    Create IEEE double-column wide violin plot with:
    - All 20 violins on single x-axis (grouped by frequency)
    - Log scale on both y-axes
    - Secondary y-axis for predicted SAPD

    IEEE double-column width = 7 inches
    """
    if proxy_df.empty:
        print("No proxy data for IEEE wide violin")
        return

    alpha = model["slope_alpha"]
    beta = model["intercept_beta"]

    # IEEE double column dimensions
    fig_width = 7.0
    fig_height = 3.5

    frequencies = [7, 9, 11, 13, 15]
    phantoms = ["duke", "ella", "eartha", "thelonious"]
    # Position calculations
    n_phantoms = 4
    width = 0.18
    gap_within = 0.22
    gap_between = 0.4

    positions = []
    colors = []
    data_list = []

    x = 0
    for freq in frequencies:
        for phantom in phantoms:
            data = proxy_df[(proxy_df["freq_ghz"] == freq) & (proxy_df["phantom"] == phantom)]["proxy_score"]
            if not data.empty:
                # Filter out zeros/negatives for log scale
                data = data[data > 0]
                sample = data.sample(n=min(2000, len(data)), random_state=42)
                positions.append(x)
                data_list.append(sample.values)
                colors.append(PHANTOM_COLORS[phantom])
            x += gap_within
        x += gap_between

    # Create figure
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    # Violin plot
    parts = ax.violinplot(data_list, positions=positions, widths=width * 4, showmeans=False, showmedians=True)

    # Color each violin
    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(colors[i])
        pc.set_alpha(0.7)
        pc.set_edgecolor("black")
        pc.set_linewidth(0.5)

    # Style lines
    parts["cmedians"].set_color("black")
    parts["cmedians"].set_linewidth(1)
    parts["cbars"].set_color("gray")
    parts["cmins"].set_color("gray")
    parts["cmaxes"].set_color("gray")

    # Log scale on primary y-axis
    ax.set_yscale("log")

    # Frequency group labels
    freq_centers = []
    x = 0
    for freq in frequencies:
        center = x + (n_phantoms - 1) * gap_within / 2
        freq_centers.append(center)
        x += n_phantoms * gap_within + gap_between

    ax.set_xticks(freq_centers)
    ax.set_xticklabels([f"{f} GHz" for f in frequencies], fontsize=9, fontweight="bold")

    # Vertical separators
    for i in range(1, len(frequencies)):
        sep_x = i * (n_phantoms * gap_within + gap_between) - gap_between / 2
        ax.axvline(sep_x, color="gray", linestyle="--", alpha=0.3, linewidth=0.8)

    ax.set_ylabel("Hotspot Score (log)", fontsize=10)
    ax.set_xlabel("Frequency", fontsize=10)
    ax.set_title("Hotspot Score Distribution by Frequency and Phantom", fontsize=11, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y", which="both")
    ax.set_xlim(-0.3, x - gap_between + 0.3)

    # Legend
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=PHANTOM_COLORS[p], label=PHANTOM_LABELS[p].split()[0], alpha=0.7, edgecolor="black") for p in phantoms
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=7, ncol=2)

    # Secondary y-axis for SAPD (also log scale)
    ax2 = ax.twinx()

    # Get y limits from primary axis (in log space)
    hs_min, hs_max = ax.get_ylim()

    # Apply linear model to get SAPD limits
    sapd_min = alpha * hs_min + beta
    sapd_max = alpha * hs_max + beta

    # Ensure positive values for log scale
    sapd_min = max(sapd_min, 0.01)

    ax2.set_yscale("log")
    ax2.set_ylim(sapd_min, sapd_max)
    ax2.set_ylabel("Predicted SAPD (mW/m², log)", fontsize=9, color="darkgreen")
    ax2.tick_params(axis="y", colors="darkgreen", labelsize=8)
    ax2.spines["right"].set_color("darkgreen")

    plt.tight_layout()
    plt.savefig(output_dir / "ieee_wide_violins_log.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("Saved: ieee_wide_violins_log.png")


# =============================================================================
# MAIN
# =============================================================================


def load_all_proxy_scores(base_dir: Path) -> pd.DataFrame:
    """Load all_proxy_scores.csv from each phantom/frequency combination."""
    all_scores = []
    freq_folders = sorted([f for f in base_dir.iterdir() if f.is_dir() and f.name.endswith("GHz")])

    for freq_folder in freq_folders:
        freq_ghz = int(freq_folder.name.replace("GHz", ""))
        phantom_folders = [f for f in freq_folder.iterdir() if f.is_dir()]

        for phantom_folder in phantom_folders:
            phantom_name = phantom_folder.name
            proxy_csv = phantom_folder / "auto_induced" / "all_proxy_scores.csv"

            if proxy_csv.exists():
                df = pd.read_csv(proxy_csv)
                df["freq_ghz"] = freq_ghz
                df["phantom"] = phantom_name
                all_scores.append(df)

    if all_scores:
        return pd.concat(all_scores, ignore_index=True)
    return pd.DataFrame()


def main():
    """Run enhanced analyses."""
    # Paths
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent / "results" / "auto_induced_FR3"
    output_dir = base_dir / "statistical_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading data from: {base_dir}")
    print(f"Output directory: {output_dir}")
    print("=" * 60)

    # Load data
    results = load_all_results(base_dir)
    print(f"Loaded {len(results)} phantom/frequency combinations")

    candidate_df = create_candidate_dataframe(results)
    print(f"Created candidate DataFrame: {len(candidate_df)} rows (top 20 per combination)")

    proxy_df = load_all_proxy_scores(base_dir)
    print(f"Loaded proxy scores: {len(proxy_df):,} total points")

    # Load model parameters
    model = load_model_parameters(output_dir)
    print(f"Model: SAPD = {model['slope_alpha']:.3f} × HS + {model['intercept_beta']:.3f}")

    # Enhanced violin plots
    print("\n" + "=" * 60)
    print("Creating enhanced violin plots with dual axis + markers...")
    print("=" * 60)
    create_enhanced_violin_distribution(candidate_df, model, output_dir)

    # Distribution spread with exponential fit
    print("\n" + "=" * 60)
    print("Creating distribution spread analysis with fits...")
    print("=" * 60)
    create_distribution_spread_analysis(proxy_df, output_dir)

    # Pairplot with top 20 only
    print("\n" + "=" * 60)
    print("Creating pairplot (top 20 candidates only)...")
    print("=" * 60)
    create_pairplot_top20(candidate_df, output_dir)

    # Individual distributions for supplementary
    print("\n" + "=" * 60)
    print("Creating individual distribution plots for supplementary...")
    print("=" * 60)
    create_individual_distribution_plots(proxy_df, output_dir)

    # IEEE wide violin (log scale)
    print("\n" + "=" * 60)
    print("Creating IEEE double-column wide violin (log scale)...")
    print("=" * 60)
    create_ieee_wide_violin_log(proxy_df, model, output_dir)

    print("\n" + "=" * 60)
    print("ALL ENHANCED ANALYSES COMPLETE")
    print(f"Results saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
