import re
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os


def parse_log_file(log_path):
    """
    Parses the progress log to extract setup and run times for each simulation.
    """
    with open(log_path, "r") as f:
        log_content = f.read()

    data = []

    # Regex to find frequency blocks and their entire content until the next one starts
    frequency_blocks = re.split(
        r"(?=--- Processing Frequency \d+/\d+: \d+MHz for Phantom '\w+' ---)",
        log_content,
    )

    for block_content in frequency_blocks:
        if not block_content.strip():
            continue

        freq_match = re.search(
            r"--- Processing Frequency (\d+/\d+): (\d+)MHz for Phantom '(\w+)' ---",
            block_content,
        )
        if not freq_match:
            continue

        freq_num_str, freq_mhz, phantom = freq_match.groups()

        # Extract setup times
        setup_matches = re.finditer(
            r"Setting up simulation (\d+/\d+): (.*?)\n.*?Done in ([\d.]+)s",
            block_content,
            re.DOTALL,
        )

        # Extract run times
        run_matches = re.finditer(
            r"--- Running simulation \d+/\d+: (EM_FDTD_.*?_(\d+MHz)_.*?) ---\n.*?Total simulation run time: ([\d.]+)s",
            block_content,
            re.DOTALL,
        )

        setups = list(setup_matches)
        runs = list(run_matches)

        num_sims = min(len(setups), len(runs))

        for i in range(num_sims):
            setup_match = setups[i]
            run_match = runs[i]

            sim_index_str, direction_polarization, setup_time_str = setup_match.groups()
            sim_name, run_freq, run_time_str = run_match.groups()

            parts = sim_name.split("_")

            data.append(
                {
                    "Frequency (MHz)": int(freq_mhz),
                    "Phantom": phantom,
                    "Simulation Index": i + 1,
                    "Simulation Name": sim_name,
                    "Direction": "_".join(parts[4:-1]),
                    "Polarization": parts[-1],
                    "Setup Time (s)": float(setup_time_str),
                    "Run Time (s)": float(run_time_str),
                }
            )

    return pd.DataFrame(data)


def create_plots(df, output_dir):
    """
    Generates and saves plots visualizing the timing data.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    sns.set_theme(style="whitegrid")

    # Plot 1: Setup Time vs. Simulation Index
    plt.figure(figsize=(14, 8))
    ax1 = sns.lineplot(
        data=df,
        x="Simulation Index",
        y="Setup Time (s)",
        hue="Frequency (MHz)",
        palette="viridis",
        marker="o",
        legend="full",
    )
    ax1.set_title("Simulation Setup Time Degradation", fontsize=16)
    ax1.set_xlabel("Simulation Index (within Frequency Sweep)", fontsize=12)
    ax1.set_ylabel("Setup Time (seconds)", fontsize=12)
    ax1.set_xticks(range(1, 13))
    plt.legend(title="Frequency (MHz)")
    plt.grid(True, which="both", linestyle="--")

    setup_plot_path = os.path.join(output_dir, "setup_time_degradation.png")
    plt.savefig(setup_plot_path)
    plt.close()
    print(f"Saved setup time plot to {setup_plot_path}")

    # Plot 2: Run Time vs. Simulation Index
    plt.figure(figsize=(14, 8))
    ax2 = sns.lineplot(
        data=df,
        x="Simulation Index",
        y="Run Time (s)",
        hue="Frequency (MHz)",
        palette="plasma",
        marker="o",
        legend="full",
    )
    ax2.set_title("Simulation Run Time", fontsize=16)
    ax2.set_xlabel("Simulation Index (within Frequency Sweep)", fontsize=12)
    ax2.set_ylabel("Run Time (seconds)", fontsize=12)
    ax2.set_xticks(range(1, 13))
    plt.legend(title="Frequency (MHz)")
    plt.grid(True, which="both", linestyle="--")

    run_plot_path = os.path.join(output_dir, "run_time_consistency.png")
    plt.savefig(run_plot_path)
    plt.close()
    print(f"Saved run time plot to {run_plot_path}")

    return setup_plot_path, run_plot_path


def main():
    """
    Main function to run the analysis.
    """
    log_file = "06-08_01-38-33.progress.log"
    output_csv = "analysis/timing_data.csv"
    output_plot_dir = "analysis/plots"

    if not os.path.exists(log_file):
        print(f"Error: Log file not found at '{log_file}'")
        return

    print("Parsing log file...")
    timing_df = parse_log_file(log_file)

    if timing_df.empty:
        print("No data could be extracted. Please check the log file format.")
        return

    print(f"Extracted data for {len(timing_df)} simulations.")

    # Save the data to a CSV file
    timing_df.to_csv(output_csv, index=False)
    print(f"Timing data saved to {output_csv}")

    # Create and save the plots
    create_plots(timing_df, output_plot_dir)


if __name__ == "__main__":
    main()
