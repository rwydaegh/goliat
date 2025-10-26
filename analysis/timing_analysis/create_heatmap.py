import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os


def create_heatmap(csv_path, output_dir):
    """
    Reads timing data from a CSV and creates a heatmap of setup times.
    """
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at '{csv_path}'")
        return

    df = pd.read_csv(csv_path)

    # Pivot the data to create a matrix suitable for a heatmap
    # We will use Frequency as the y-axis, Simulation Index as the x-axis,
    # and Setup Time as the values.
    heatmap_data = df.pivot_table(index="Frequency (MHz)", columns="Simulation Index", values="Setup Time (s)")

    # Create the heatmap
    plt.figure(figsize=(16, 8))
    sns.heatmap(
        heatmap_data,
        annot=True,
        fmt=".1f",
        linewidths=0.5,
        cmap="viridis",
        cbar_kws={"label": "Setup Time (seconds)"},
    )

    plt.title("Heatmap of Simulation Setup Time Degradation", fontsize=16)
    plt.xlabel("Simulation Index (within Frequency Sweep)", fontsize=12)
    plt.ylabel("Frequency (MHz)", fontsize=12)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    heatmap_plot_path = os.path.join(output_dir, "setup_time_heatmap.png")
    plt.savefig(heatmap_plot_path)
    plt.close()

    print(f"Saved heatmap plot to {heatmap_plot_path}")
    return heatmap_plot_path


def create_run_time_heatmap(csv_path, output_dir):
    """
    Reads timing data from a CSV and creates a heatmap of run times.
    """
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at '{csv_path}'")
        return

    df = pd.read_csv(csv_path)

    # Pivot the data to create a matrix suitable for a heatmap
    heatmap_data = df.pivot_table(index="Frequency (MHz)", columns="Simulation Index", values="Run Time (s)")

    # Create the heatmap
    plt.figure(figsize=(16, 8))
    sns.heatmap(
        heatmap_data,
        annot=True,
        fmt=".1f",
        linewidths=0.5,
        cmap="viridis",
        cbar_kws={"label": "Run Time (seconds)"},
    )

    plt.title("Heatmap of Simulation Run Time Degradation", fontsize=16)
    plt.xlabel("Simulation Index (within Frequency Sweep)", fontsize=12)
    plt.ylabel("Frequency (MHz)", fontsize=12)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    heatmap_plot_path = os.path.join(output_dir, "run_time_heatmap.png")
    plt.savefig(heatmap_plot_path)
    plt.close()

    print(f"Saved heatmap plot to {heatmap_plot_path}")
    return heatmap_plot_path


def main():
    """
    Main function to run the heatmap generation.
    """
    csv_file = "analysis/manual_timing_data.csv"
    output_plot_dir = "analysis/plots"
    create_heatmap(csv_file, output_plot_dir)
    create_run_time_heatmap(csv_file, output_plot_dir)


if __name__ == "__main__":
    main()
