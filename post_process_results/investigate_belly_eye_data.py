import os
import pickle
import pandas as pd

def investigate_belly_eye_data():
    """
    Performs a deep investigation into the psSAR10g_eyes data for the
    "by_belly" scenario to understand why it disappears from the line plot.
    """
    print("--- Deep Investigation: 'by_belly' Eye SAR Data ---")

    # --- 1. Load Data ---
    results_pickle_path = 'results/near_field/thelonious/aggregated_results.pkl'
    if not os.path.exists(results_pickle_path):
        print(f"ERROR: Aggregated results file not found at '{results_pickle_path}'")
        return

    with open(results_pickle_path, 'rb') as f:
        cached_data = pickle.load(f)

    results_df = cached_data['summary_results']
    print("Data loaded successfully.")

    # --- 2. Isolate and inspect the specific data ---
    belly_df = results_df[results_df['scenario'] == 'by_belly'].copy()

    eye_sar_by_freq = belly_df.groupby('frequency_mhz')['psSAR10g_eyes'].agg(['mean', 'sum', 'count', 'max'])

    print("\n--- Aggregated 'psSAR10g_eyes' data for 'by_belly' scenario ---")
    print(eye_sar_by_freq.to_string())

    print("\n--- Detailed data for frequencies > 1450 MHz ---")
    high_freq_belly_eye_df = belly_df[belly_df['frequency_mhz'] > 1450]
    print(high_freq_belly_eye_df[['frequency_mhz', 'placement', 'psSAR10g_eyes']].to_string())

    print("\n--- Conclusion ---")
    if (eye_sar_by_freq['max'][eye_sar_by_freq.index > 1450] == 0).all():
        print("The psSAR10g in the eyes for the 'by_belly' scenario is consistently ZERO for all frequencies above 1450 MHz.")
        print("The line plot is not missing data; it correctly shows that the value drops to zero and stays there.")
    else:
        print("The data for frequencies > 1450 MHz is not consistently zero. Further investigation needed.")

    print("\n--- Investigation Finished ---")

if __name__ == "__main__":
    investigate_belly_eye_data()
