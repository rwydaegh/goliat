#!/usr/bin/env python3
"""
Statistical analysis of auto-induced exposure FR3 results.

This script performs:
1. Linear regression: Hotspot Score → SAPD prediction model
2. Hotspot score distribution analysis with frequency-dependent sharpening
3. YZ-plane spatial visualization focus
4. Data bank generation for supplementary materials

Author: Generated for GOLIAT project
Date: 2026-02-01
"""

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import pearsonr, spearmanr

# Set style for all plots
plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams["font.size"] = 11
plt.rcParams["axes.labelsize"] = 12
plt.rcParams["axes.titlesize"] = 13
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["figure.dpi"] = 150


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
                print(f"Loaded proxy scores: {freq_ghz}GHz / {phantom_name} ({len(df):,} points)")

    if all_scores:
        return pd.concat(all_scores, ignore_index=True)
    return pd.DataFrame()


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


# =============================================================================
# ANALYSIS 1: Linear Regression Model
# =============================================================================


def fit_linear_model(candidate_df: pd.DataFrame, output_dir: Path) -> dict:
    """
    Fit linear regression: SAPD = α × hotspot_score + β

    Returns model parameters and statistics.
    """
    # Filter valid data
    df = candidate_df.dropna(subset=["hotspot_score", "peak_sapd_mw_m2"])

    x = df["hotspot_score"].values
    y = df["peak_sapd_mw_m2"].values

    # Fit linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    # Additional statistics
    y_pred = slope * x + intercept
    residuals = y - y_pred
    rmse = np.sqrt(np.mean(residuals**2))

    # Pearson and Spearman correlations
    pearson_r, pearson_p = pearsonr(x, y)
    spearman_rho, spearman_p = spearmanr(x, y)

    model = {
        "slope_alpha": slope,
        "intercept_beta": intercept,
        "r_squared": r_value**2,
        "pearson_r": pearson_r,
        "spearman_rho": spearman_rho,
        "p_value": p_value,
        "std_err": std_err,
        "rmse_mw_m2": rmse,
        "n_samples": len(df),
    }

    print("\n" + "=" * 60)
    print("LINEAR MODEL: 4-cm^2 averaged APD = alpha * hotspot_score + beta")
    print("=" * 60)
    print(f"  alpha (slope):     {slope:.4f} mW/m² per unit hotspot score")
    print(f"  beta (intercept): {intercept:.4f} mW/m²")
    print(f"  R^2:           {r_value**2:.4f}")
    print(f"  Pearson r:     {pearson_r:.4f} (p={pearson_p:.2e})")
    print(f"  Spearman rho:  {spearman_rho:.4f} (p={spearman_p:.2e})")
    print(f"  RMSE:          {rmse:.4f} mW/m²")
    print(f"  N samples:     {len(df)}")
    print("=" * 60)

    # Create visualization
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Panel A: Scatter with regression line and prediction bands
    ax = axes[0]

    # Color by frequency
    colors = plt.cm.viridis(np.linspace(0, 1, df["freq_ghz"].nunique()))
    freq_colors = dict(zip(sorted(df["freq_ghz"].unique()), colors))

    for freq in sorted(df["freq_ghz"].unique()):
        mask = df["freq_ghz"] == freq
        ax.scatter(
            df.loc[mask, "hotspot_score"],
            df.loc[mask, "peak_sapd_mw_m2"],
            c=[freq_colors[freq]],
            label=f"{freq} GHz",
            alpha=0.7,
            s=60,
            edgecolors="white",
            linewidth=0.5,
        )

    # Regression line
    x_line = np.linspace(x.min(), x.max(), 100)
    y_line = slope * x_line + intercept
    ax.plot(x_line, y_line, "r-", linewidth=2, label=f"Fit: 4-cm$^2$ averaged APD = {slope:.2f}×HS + {intercept:.2f}")

    # 95% prediction interval
    n = len(x)
    t_val = stats.t.ppf(0.975, n - 2)
    s_err = np.sqrt(np.sum(residuals**2) / (n - 2))
    x_mean = np.mean(x)
    ss_x = np.sum((x - x_mean) ** 2)

    conf_interval = t_val * s_err * np.sqrt(1 + 1 / n + (x_line - x_mean) ** 2 / ss_x)
    ax.fill_between(x_line, y_line - conf_interval, y_line + conf_interval, alpha=0.2, color="red", label="95% prediction interval")

    ax.set_xlabel("Hotspot Score (mean |E|²)")
    ax.set_ylabel("Peak 4-cm$^2$ averaged APD (mW/m²)")
    ax.set_title(f"(a) Linear Model: R² = {r_value**2:.3f}, Pearson r = {pearson_r:.3f}")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)

    # Panel B: Residuals
    ax = axes[1]
    ax.scatter(y_pred, residuals, alpha=0.6, s=40, c="steelblue", edgecolors="white")
    ax.axhline(0, color="red", linestyle="--", linewidth=1.5)
    ax.axhline(rmse, color="gray", linestyle=":", label=f"±RMSE = ±{rmse:.2f}")
    ax.axhline(-rmse, color="gray", linestyle=":")
    ax.set_xlabel("Predicted 4-cm$^2$ averaged APD (mW/m²)")
    ax.set_ylabel("Residual (mW/m²)")
    ax.set_title("(b) Residual Analysis")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "linear_model_sapd_prediction.png", dpi=200, bbox_inches="tight")
    plt.savefig(output_dir / "linear_model_sapd_prediction.pdf", bbox_inches="tight")
    plt.close()
    print("Saved: linear_model_sapd_prediction.png and .pdf")

    return model


# =============================================================================
# ANALYSIS 2: Hotspot Score Distribution with Frequency Sharpening
# =============================================================================


def analyze_hotspot_distributions(proxy_df: pd.DataFrame, output_dir: Path) -> None:
    """
    Analyze hotspot score distributions across frequencies.
    Shows frequency-dependent sharpening and potential bimodality.
    """
    if proxy_df.empty:
        print("No proxy score data available for distribution analysis")
        return

    frequencies = sorted(proxy_df["freq_ghz"].unique())
    phantoms = sorted(proxy_df["phantom"].unique())

    # Figure 1: Histogram overlay across frequencies (all phantoms combined)
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    # Panel A: Overlaid histograms
    ax = axes[0, 0]
    colors = plt.cm.plasma(np.linspace(0.1, 0.9, len(frequencies)))

    for i, freq in enumerate(frequencies):
        freq_data = proxy_df[proxy_df["freq_ghz"] == freq]["proxy_score"]
        ax.hist(freq_data, bins=80, alpha=0.4, label=f"{freq} GHz", color=colors[i], density=True)

    ax.set_xlabel("Hotspot Score (proxy)")
    ax.set_ylabel("Density")
    ax.set_title("(a) Hotspot Score Distribution by Frequency")
    ax.legend()
    ax.set_xlim(0, proxy_df["proxy_score"].quantile(0.99))

    # Panel B: KDE comparison
    ax = axes[0, 1]
    for i, freq in enumerate(frequencies):
        freq_data = proxy_df[proxy_df["freq_ghz"] == freq]["proxy_score"]
        freq_data = freq_data[freq_data < freq_data.quantile(0.99)]  # Trim outliers
        try:
            freq_data.plot.kde(ax=ax, label=f"{freq} GHz", color=colors[i], linewidth=2)
        except Exception:
            pass

    ax.set_xlabel("Hotspot Score (proxy)")
    ax.set_ylabel("Density")
    ax.set_title("(b) KDE: Frequency-Dependent Sharpening")
    ax.legend()
    ax.set_xlim(0, None)

    # Panel C: CDF comparison
    ax = axes[1, 0]
    for i, freq in enumerate(frequencies):
        freq_data = proxy_df[proxy_df["freq_ghz"] == freq]["proxy_score"].sort_values()
        cdf = np.arange(1, len(freq_data) + 1) / len(freq_data)
        ax.plot(freq_data, cdf * 100, label=f"{freq} GHz", color=colors[i], linewidth=2)

    ax.axhline(95, color="red", linestyle="--", alpha=0.5, label="95th percentile")
    ax.set_xlabel("Hotspot Score (proxy)")
    ax.set_ylabel("Cumulative %")
    ax.set_title("(c) CDF Comparison")
    ax.legend()
    ax.set_xlim(0, proxy_df["proxy_score"].quantile(0.99))
    ax.set_ylim(0, 100)

    # Panel D: Standard deviation by frequency (sharpening metric)
    ax = axes[1, 1]
    stats_by_freq = proxy_df.groupby("freq_ghz")["proxy_score"].agg(["mean", "std", "max"])
    stats_by_freq["cv"] = stats_by_freq["std"] / stats_by_freq["mean"]  # Coefficient of variation

    ax.bar(stats_by_freq.index, stats_by_freq["std"], color="steelblue", alpha=0.7, label="Std Dev")
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("Standard Deviation of Hotspot Score")
    ax.set_title("(d) Distribution Spread by Frequency")

    # Add trend line
    z = np.polyfit(stats_by_freq.index, stats_by_freq["std"], 1)
    p = np.poly1d(z)
    ax.plot(stats_by_freq.index, p(stats_by_freq.index), "r--", linewidth=2, label=f"Trend: {z[0]:.4f}×freq + {z[1]:.3f}")
    ax.legend()

    plt.tight_layout()
    plt.savefig(output_dir / "hotspot_distribution_analysis.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("Saved: hotspot_distribution_analysis.png")

    # Figure 2: Per-phantom distributions
    fig, axes = plt.subplots(len(phantoms), len(frequencies), figsize=(3 * len(frequencies), 3 * len(phantoms)))

    for i, phantom in enumerate(phantoms):
        for j, freq in enumerate(frequencies):
            ax = axes[i, j] if len(phantoms) > 1 else axes[j]

            data = proxy_df[(proxy_df["phantom"] == phantom) & (proxy_df["freq_ghz"] == freq)]["proxy_score"]

            if not data.empty:
                ax.hist(data, bins=50, alpha=0.7, color=colors[j], density=True)
                ax.axvline(data.mean(), color="red", linestyle="--", linewidth=1, label=f"μ={data.mean():.3f}")
                ax.axvline(data.quantile(0.95), color="orange", linestyle=":", linewidth=1, label=f"95%={data.quantile(0.95):.3f}")

            if j == 0:
                ax.set_ylabel(phantom.capitalize())
            if i == 0:
                ax.set_title(f"{freq} GHz")
            if i == len(phantoms) - 1:
                ax.set_xlabel("Hotspot Score")

    plt.suptitle("Hotspot Score Distributions by Phantom and Frequency", y=1.02, fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "hotspot_distributions_grid.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: hotspot_distributions_grid.png")

    # Print statistics summary
    print("\n" + "=" * 60)
    print("HOTSPOT SCORE DISTRIBUTION STATISTICS")
    print("=" * 60)
    print(stats_by_freq.round(4).to_string())
    print("=" * 60)


# =============================================================================
# ANALYSIS 3: Dual-Axis Distribution (Hotspot + Predicted SAPD)
# =============================================================================


def create_dual_axis_distribution(proxy_df: pd.DataFrame, model: dict, output_dir: Path) -> None:
    """
    Create hotspot score histogram with secondary y-axis showing predicted SAPD.
    """
    if proxy_df.empty:
        print("No proxy score data for dual-axis plot")
        return

    alpha = model["slope_alpha"]
    beta = model["intercept_beta"]

    # Use a representative frequency (e.g., 11 GHz - middle of range)
    mid_freq = 11
    if mid_freq not in proxy_df["freq_ghz"].values:
        mid_freq = proxy_df["freq_ghz"].median()

    data = proxy_df[proxy_df["freq_ghz"] == mid_freq]["proxy_score"]

    fig, ax1 = plt.subplots(figsize=(12, 6))

    # Primary axis: Hotspot score histogram
    n, bins, patches = ax1.hist(data, bins=80, alpha=0.7, color="steelblue", edgecolor="white")
    ax1.set_xlabel("Hotspot Score (mean |E|²)", fontsize=12)
    ax1.set_ylabel("Count", fontsize=12, color="steelblue")
    ax1.tick_params(axis="y", labelcolor="steelblue")

    # Mark percentiles
    ax1.axvline(data.mean(), color="red", linestyle="--", linewidth=2, label=f"Mean: {data.mean():.3f}")
    ax1.axvline(data.quantile(0.95), color="orange", linestyle="--", linewidth=2, label=f"95th %ile: {data.quantile(0.95):.3f}")
    ax1.axvline(data.max(), color="darkred", linestyle="-", linewidth=2, label=f"Max: {data.max():.3f}")

    # Secondary axis: Predicted SAPD
    ax2 = ax1.twiny()  # Secondary x-axis at top

    # Map hotspot scores to predicted SAPD
    hs_min, hs_max = ax1.get_xlim()
    sapd_min = alpha * hs_min + beta
    sapd_max = alpha * hs_max + beta

    ax2.set_xlim(sapd_min, sapd_max)
    ax2.set_xlabel("Predicted 4-cm$^2$ averaged APD (mW/m²)", fontsize=12, color="darkgreen")
    ax2.tick_params(axis="x", labelcolor="darkgreen")

    # Title
    ax1.set_title(
        f"Hotspot Score Distribution at {mid_freq} GHz\n"
        + f"(4-cm$^2$ averaged APD = {alpha:.2f} × HS + {beta:.2f}, R² = {model['r_squared']:.3f})",
        fontsize=13,
        fontweight="bold",
        pad=30,
    )

    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "dual_axis_hotspot_sapd.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("Saved: dual_axis_hotspot_sapd.png")


# =============================================================================
# ANALYSIS 4: YZ Plane Spatial Visualization
# =============================================================================


def create_yz_spatial_plots(proxy_df: pd.DataFrame, results: list, output_dir: Path) -> None:
    """
    Create YZ-plane (side view) spatial visualizations.
    Focus for paper; XY and XZ go to data bank.
    """
    if proxy_df.empty:
        print("No proxy score data for spatial plots")
        return

    phantoms = sorted(proxy_df["phantom"].unique())
    frequencies = sorted(proxy_df["freq_ghz"].unique())

    # Get worst-case candidates from results
    worst_cases = {}
    for r in results:
        key = (r["freq_ghz"], r["phantom_name"])
        wc = r.get("worst_case", {})
        if wc:
            worst_cases[key] = wc

    # Create YZ-only figure for paper
    fig, axes = plt.subplots(len(phantoms), len(frequencies), figsize=(3 * len(frequencies), 4 * len(phantoms)))

    for i, phantom in enumerate(phantoms):
        for j, freq in enumerate(frequencies):
            ax = axes[i, j] if len(phantoms) > 1 else axes[j]

            # Get data for this phantom/frequency
            mask = (proxy_df["phantom"] == phantom) & (proxy_df["freq_ghz"] == freq)
            data = proxy_df[mask]

            if data.empty:
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
                continue

            # Subsample for plotting
            plot_data = data.sample(n=min(3000, len(data)), random_state=42)

            # YZ scatter (side view)
            scatter = ax.scatter(
                plot_data["y_mm"],
                plot_data["z_mm"],
                c=plot_data["proxy_score"],
                cmap="viridis",
                s=3,
                alpha=0.5,
                vmin=0,
                vmax=data["proxy_score"].quantile(0.95),
                rasterized=True,
            )

            # Mark worst-case location if available
            wc = worst_cases.get((freq, phantom))
            if wc and "focus_position_mm" in str(wc):
                # Would need to extract from candidates - skip for now
                pass

            ax.set_aspect("equal", adjustable="box")

            if j == 0:
                ax.set_ylabel(f"{phantom.capitalize()}\nZ (mm)")
            else:
                ax.set_ylabel("")

            if i == len(phantoms) - 1:
                ax.set_xlabel("Y (mm)")
            else:
                ax.set_xlabel("")

            if i == 0:
                ax.set_title(f"{freq} GHz")

    # Add colorbar
    fig.colorbar(scatter, ax=axes, shrink=0.6, label="Hotspot Score")

    plt.suptitle("Hotspot Score Spatial Distribution (YZ Side View)", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / "spatial_yz_plane_all.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: spatial_yz_plane_all.png")

    # Create single-phantom focus figure (for paper)
    for phantom in ["eartha", "duke"]:  # Representative phantoms
        if phantom not in phantoms:
            continue

        fig, axes = plt.subplots(1, len(frequencies), figsize=(3.5 * len(frequencies), 5))

        for j, freq in enumerate(frequencies):
            ax = axes[j]

            mask = (proxy_df["phantom"] == phantom) & (proxy_df["freq_ghz"] == freq)
            data = proxy_df[mask]

            if data.empty:
                continue

            plot_data = data.sample(n=min(4000, len(data)), random_state=42)

            scatter = ax.scatter(
                plot_data["y_mm"],
                plot_data["z_mm"],
                c=plot_data["proxy_score"],
                cmap="plasma",
                s=4,
                alpha=0.6,
                vmin=0,
                vmax=data["proxy_score"].quantile(0.95),
                rasterized=True,
            )

            ax.set_aspect("equal", adjustable="box")
            ax.set_xlabel("Y (mm)")
            ax.set_title(f"{freq} GHz")

            if j == 0:
                ax.set_ylabel("Z (mm)")

        fig.colorbar(scatter, ax=axes, shrink=0.8, label="Hotspot Score")

        plt.suptitle(f"Hotspot Score Distribution - {phantom.capitalize()} (YZ Side View)", fontsize=13, fontweight="bold")
        plt.tight_layout()
        plt.savefig(output_dir / f"spatial_yz_{phantom}_paper.png", dpi=200, bbox_inches="tight")
        plt.close()
        print(f"Saved: spatial_yz_{phantom}_paper.png")


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Run all analyses."""
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
    print(f"\nLoaded {len(results)} phantom/frequency combinations")

    candidate_df = create_candidate_dataframe(results)
    print(f"Created candidate DataFrame: {len(candidate_df)} rows")

    proxy_df = load_all_proxy_scores(base_dir)
    print(f"Loaded proxy scores: {len(proxy_df):,} total points")

    # Analysis 1: Linear model
    print("\n" + "=" * 60)
    print("ANALYSIS 1: Linear Regression Model")
    print("=" * 60)
    model = fit_linear_model(candidate_df, output_dir)

    # Save model parameters
    model_file = output_dir / "linear_model_parameters.json"
    with open(model_file, "w") as f:
        json.dump(model, f, indent=2)
    print(f"Saved model parameters to: {model_file}")

    # Analysis 2: Distribution analysis
    print("\n" + "=" * 60)
    print("ANALYSIS 2: Hotspot Score Distributions")
    print("=" * 60)
    analyze_hotspot_distributions(proxy_df, output_dir)

    # Analysis 3: Dual-axis distribution
    print("\n" + "=" * 60)
    print("ANALYSIS 3: Dual-Axis Distribution Plot")
    print("=" * 60)
    create_dual_axis_distribution(proxy_df, model, output_dir)

    # Analysis 4: YZ spatial plots
    print("\n" + "=" * 60)
    print("ANALYSIS 4: YZ Plane Spatial Visualizations")
    print("=" * 60)
    create_yz_spatial_plots(proxy_df, results, output_dir)

    print("\n" + "=" * 60)
    print("ALL ANALYSES COMPLETE")
    print(f"Results saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
