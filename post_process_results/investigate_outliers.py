import os
import pickle
import pandas as pd
import numpy as np


def investigate_outliers():
    """
    Digs into the aggregated data to identify the specific placements
    responsible for the observed outliers in the boxplots.
    """
    print("--- Starting Outlier Investigation ---")

    # --- 1. Load Data ---
    results_pickle_path = "results/near_field/thelonious/aggregated_results.pkl"
    if not os.path.exists(results_pickle_path):
        print(f"ERROR: Aggregated results file not found at '{results_pickle_path}'")
        return

    with open(results_pickle_path, "rb") as f:
        cached_data = pickle.load(f)

    results_df = cached_data["summary_results"]
    print("Data loaded successfully.")

    # --- 2. Investigate "front_of_eyes" 700 MHz outliers ---
    print("\n--- Investigating 'front_of_eyes' 700 MHz Outliers ---")
    foe_700_df = results_df[
        (results_df["scenario"] == "front_of_eyes")
        & (results_df["frequency_mhz"] == 700)
    ].copy()

    for metric in ["psSAR10g_brain", "psSAR10g_eyes"]:
        # Standard definition of an outlier
        Q1 = foe_700_df[metric].quantile(0.25)
        Q3 = foe_700_df[metric].quantile(0.75)
        IQR = Q3 - Q1
        outlier_threshold = Q3 + 1.5 * IQR

        outliers = foe_700_df[foe_700_df[metric] > outlier_threshold]

        print(f"\nOutliers for {metric} (Threshold > {outlier_threshold:.2f} mW/kg):")
        if not outliers.empty:
            print(
                outliers[["placement", metric]]
                .sort_values(by=metric, ascending=False)
                .to_string()
            )
        else:
            print("No outliers found.")

    # --- 3. Investigate "by_belly" skin outliers ---
    print("\n--- Investigating 'by_belly' Skin Outliers ---")
    belly_df = results_df[results_df["scenario"] == "by_belly"].copy()
    frequencies = sorted(belly_df["frequency_mhz"].unique())

    for freq in frequencies:
        if freq == 700:
            continue  # Skip 700 MHz as per the user's request

        freq_df = belly_df[belly_df["frequency_mhz"] == freq]

        metric = "psSAR10g_skin"
        Q1 = freq_df[metric].quantile(0.25)
        Q3 = freq_df[metric].quantile(0.75)
        IQR = Q3 - Q1
        outlier_threshold = Q3 + 1.5 * IQR

        outliers = freq_df[freq_df[metric] > outlier_threshold]

        print(
            f"\nOutliers for psSAR10g_skin at {freq} MHz (Threshold > {outlier_threshold:.2f} mW/kg):"
        )
        if not outliers.empty:
            print(
                outliers[["placement", metric]]
                .sort_values(by=metric, ascending=False)
                .to_string()
            )
        else:
            print("No outliers found.")

    print("\n--- Outlier Investigation Finished ---")


if __name__ == "__main__":
    investigate_outliers()
