import os
import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


def run_new_analysis():
    """
    Performs new, hypothesis-driven analysis on the near-field simulation results.
    """
    print("--- Starting New Post-Processing Analysis ---")

    # --- 1. Load Data ---
    results_pickle_path = "results/near_field/thelonious/aggregated_results.pkl"
    plots_dir = "post_process_results/plots"
    os.makedirs(plots_dir, exist_ok=True)

    if not os.path.exists(results_pickle_path):
        print(f"ERROR: Aggregated results file not found at '{results_pickle_path}'")
        return

    with open(results_pickle_path, "rb") as f:
        cached_data = pickle.load(f)

    results_df = cached_data["summary_results"]

    print("Data loaded successfully.")

    # --- 2. Hypothesis 1: Correlation between Head SAR and Eye SAR ---
    print("\n--- Hypothesis 1: Analyzing Head vs. Eye SAR Correlation ---")
    front_of_eyes_df = results_df[results_df["scenario"] == "front_of_eyes"].copy()

    # Ensure both columns are numeric and drop rows with missing values for this analysis
    front_of_eyes_df["SAR_head"] = pd.to_numeric(
        front_of_eyes_df["SAR_head"], errors="coerce"
    )
    front_of_eyes_df["psSAR10g_eyes"] = pd.to_numeric(
        front_of_eyes_df["psSAR10g_eyes"], errors="coerce"
    )
    correlation_df = front_of_eyes_df.dropna(subset=["SAR_head", "psSAR10g_eyes"])

    correlation = correlation_df["SAR_head"].corr(correlation_df["psSAR10g_eyes"])
    print(
        f"Correlation between Head SAR and Eye psSAR10g for 'front_of_eyes': {correlation:.4f}"
    )

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.scatterplot(
        data=correlation_df,
        x="SAR_head",
        y="psSAR10g_eyes",
        hue="frequency_mhz",
        palette="viridis",
        s=100,
        ax=ax,
    )
    ax.set_title(
        "Correlation between Head SAR and Eye psSAR10g\n(front_of_eyes scenario)"
    )
    ax.set_xlabel("Normalized Head SAR (mW/kg)")
    ax.set_ylabel("Normalized psSAR10g Eyes (mW/kg)")
    ax.grid(True)
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, "correlation_head_vs_eye_sar.png"))
    plt.close(fig)
    print("Generated plot: correlation_head_vs_eye_sar.png")

    # --- 3. Hypothesis 2: Frequency-Dependent SAR Penetration Depth ---
    print("\n--- Hypothesis 2: Analyzing SAR Penetration Depth ---")
    penetration_df = results_df.copy()
    penetration_df["penetration_ratio"] = (
        penetration_df["psSAR10g_brain"] / penetration_df["psSAR10g_skin"]
    )

    avg_penetration_ratio = (
        penetration_df.groupby(["scenario", "frequency_mhz"])["penetration_ratio"]
        .mean()
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(12, 7))
    sns.lineplot(
        data=avg_penetration_ratio,
        x="frequency_mhz",
        y="penetration_ratio",
        hue="scenario",
        marker="o",
        ax=ax,
    )
    ax.set_title("SAR Penetration Depth: Brain-to-Skin SAR Ratio vs. Frequency")
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Ratio of psSAR10g (Brain / Skin)")
    ax.set_yscale("log")
    ax.grid(True, which="both", ls="--")
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, "penetration_ratio_vs_frequency.png"))
    plt.close(fig)
    print("Generated plot: penetration_ratio_vs_frequency.png")

    print("\n--- New Post-Processing Analysis Finished ---")


if __name__ == "__main__":
    run_new_analysis()
