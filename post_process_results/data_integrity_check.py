import os
import pickle
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns

def run_data_integrity_checks():
    """
    Performs a series of checks on the data and plots to ensure integrity
    and address specific questions from the TODO list.
    """
    print("--- Starting Data Integrity & Enhancement Script ---")

    # --- 1. Load Data ---
    results_pickle_path = 'results/near_field/thelonious/aggregated_results.pkl'
    if not os.path.exists(results_pickle_path):
        print(f"ERROR: Aggregated results file not found at '{results_pickle_path}'")
        return

    with open(results_pickle_path, 'rb') as f:
        cached_data = pickle.load(f)

    results_df = cached_data['summary_results']
    print("Data loaded successfully.")

    # --- 2. Check for Missing Eye SAR Data ---
    print("\n--- Checking for Missing 'psSAR10g_eyes' Data ('front_of_eyes') ---")
    foe_df = results_df[results_df['scenario'] == 'front_of_eyes'].copy()

    nan_eye_sar = foe_df[foe_df['psSAR10g_eyes'].isna()]

    if not nan_eye_sar.empty:
        print("Found rows with NaN values for 'psSAR10g_eyes':")
        print(nan_eye_sar[['frequency_mhz', 'placement', 'psSAR10g_eyes']])
    else:
        print("No NaN values found for 'psSAR10g_eyes' in the 'front_of_eyes' scenario.")

    print("\nValue counts for 'psSAR10g_eyes' at each frequency:")
    print(foe_df.groupby('frequency_mhz')['psSAR10g_eyes'].apply(lambda x: x.notna().sum()))


    # --- 3. Fix Correlation Plot & Add Formula Fit ---
    print("\n--- Generating Corrected Correlation Plot with Linear Fit ---")
    plots_dir = 'post_process_results/plots'

    front_of_eyes_df = results_df[results_df['scenario'] == 'front_of_eyes'].copy()
    front_of_eyes_df['SAR_head'] = pd.to_numeric(front_of_eyes_df['SAR_head'], errors='coerce')
    front_of_eyes_df['psSAR10g_eyes'] = pd.to_numeric(front_of_eyes_df['psSAR10g_eyes'], errors='coerce')
    correlation_df = front_of_eyes_df.dropna(subset=['SAR_head', 'psSAR10g_eyes'])

    # Perform linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(correlation_df['SAR_head'], correlation_df['psSAR10g_eyes'])
    r_squared = r_value**2

    print(f"Linear Regression Fit: Eye_SAR = {slope:.2f} * Head_SAR + {intercept:.2f}")
    print(f"R-squared: {r_squared:.4f}")

    fig, ax = plt.subplots(figsize=(10, 6))

    # Scatter plot with correct categorical legend
    sns.scatterplot(data=correlation_df, x='SAR_head', y='psSAR10g_eyes', hue='frequency_mhz',
                    palette='viridis', s=100, ax=ax)

    # Plot the regression line
    x_vals = np.array(ax.get_xlim())
    y_vals = intercept + slope * x_vals
    ax.plot(x_vals, y_vals, '--', color='red', label=f'Linear Fit (R²={r_squared:.2f})')

    ax.set_title('Correlation between Head SAR and Eye psSAR10g\n(front_of_eyes scenario)')
    ax.set_xlabel('Normalized Head SAR (mW/kg)')
    ax.set_ylabel('Normalized psSAR10g Eyes (mW/kg)')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()

    # Overwrite the old plot
    plot_path = os.path.join(plots_dir, 'correlation_head_vs_eye_sar.png')
    fig.savefig(plot_path)
    plt.close(fig)
    print(f"Generated corrected plot with formula fit: {os.path.basename(plot_path)}")


    print("\n--- Data Integrity & Enhancement Script Finished ---")

if __name__ == "__main__":
    run_data_integrity_checks()
