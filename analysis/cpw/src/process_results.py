import pandas as pd
import json
import os
import pickle
import numpy as np
import matplotlib.pyplot as plt


def extract_volume_data(html_file_path):
    """
    Parses the HTML file to extract tissue volume data.
    """
    if not os.path.exists(html_file_path):
        raise FileNotFoundError(f"HTML file not found at: {html_file_path}")

    tables = pd.read_html(html_file_path)
    df = tables[0]
    volume_data = df[["Tissue", "Total Volume"]]
    return volume_data


def merge_data(volume_data_path, material_properties_path, mapping_file_path):
    """
    Merges volume and material property data.
    """
    with open(volume_data_path, "rb") as f:
        volume_df = pickle.load(f)

    with open(material_properties_path, "rb") as f:
        material_df = pd.DataFrame(pickle.load(f))

    with open(mapping_file_path, "r") as f:
        name_mapping = json.load(f)

    # Create a reverse mapping for easier lookup
    reverse_mapping = {v: k for k, v in name_mapping.items()}

    # Apply the mapping to the material dataframe
    material_df["Tissue"] = material_df["Name"].map(reverse_mapping).fillna(material_df["Name"])

    # Merge the dataframes
    merged_df = pd.merge(volume_df, material_df, on="Tissue")

    return merged_df


def plot_data(df, frequency_mhz):
    """
    Generates a 2D plot of Volume vs. Relative Permittivity.
    """
    os.makedirs("analysis/cpw/plots", exist_ok=True)
    plt.figure(figsize=(12, 8))
    plt.scatter(df["RelativePermittivity"], df["Total Volume"], alpha=0.7)
    plt.yscale("log")

    # for i, txt in enumerate(df['Tissue']):
    #     plt.annotate(txt, (df['RelativePermittivity'].iloc[i], df['Total Volume'].iloc[i]), fontsize=8)

    plt.xlabel("Relative Permittivity")
    plt.ylabel("Total Volume (m^3) - Log Scale")
    plt.title(f"Tissue Volume vs. Relative Permittivity at {frequency_mhz} MHz")
    plt.grid(True)
    output_path = f"analysis/cpw/plots/volume_vs_permittivity_{frequency_mhz}.png"
    plt.savefig(output_path)
    print(f"Plot saved to {output_path}")
    plt.close()


def plot_cpw(df, frequency_mhz):
    """
    Generates a 2D plot of Cells Per Wavelength.
    """
    os.makedirs("analysis/cpw/plots", exist_ok=True)
    plt.figure(figsize=(12, 8))
    plt.scatter(df["RelativePermittivity"], df["CPW"], alpha=0.7)

    # for i, txt in enumerate(df['Tissue']):
    #     plt.annotate(txt, (df['RelativePermittivity'].iloc[i], df['CPW'].iloc[i]), fontsize=8)

    plt.xlabel("Relative Permittivity")
    plt.ylabel("Cells Per Wavelength (CPW)")
    plt.ylim(0, 25)
    plt.title(f"Cells Per Wavelength at {frequency_mhz} MHz")
    plt.grid(True)
    output_path = f"analysis/cpw/plots/cpw_{frequency_mhz}.png"
    plt.savefig(output_path)
    print(f"Plot saved to {output_path}")
    plt.close()


def plot_volume_vs_cpw(df, frequency_mhz):
    """
    Generates a 2D plot of Volume vs. CPW, with Relative Permittivity as color.
    """
    os.makedirs("analysis/cpw/plots", exist_ok=True)
    plt.figure(figsize=(14, 8))
    # Only plot data points with CPW <= 25 for clarity
    plot_df = df[df["CPW"] <= 25].copy()

    scatter = plt.scatter(
        plot_df["CPW"],
        plot_df["Total Volume"],
        c=plot_df["RelativePermittivity"],
        cmap="viridis",
        alpha=0.9,
        vmin=1,
    )
    plt.yscale("log")
    plt.xlim(0, 25)

    # Add a colorbar
    cbar = plt.colorbar(scatter)
    cbar.set_label("Relative Permittivity")

    plt.xlabel("Cells Per Wavelength (CPW)")
    plt.ylabel("Total Volume (m^3) - Log Scale")
    plt.title(f"Tissue Volume vs. CPW at {frequency_mhz} MHz")
    plt.grid(True)

    # Label all tissues
    for i, row in plot_df.iterrows():
        plt.annotate(
            row["Tissue"],
            (row["CPW"], row["Total Volume"]),
            fontsize=8,
            textcoords="offset points",
            xytext=(0, 5),
            ha="center",
        )

    output_path = f"analysis/cpw/plots/volume_vs_cpw_{frequency_mhz}.png"
    plt.savefig(output_path)
    print(f"Plot saved to {output_path}")
    plt.close()


def plot_cross_frequency(all_data, tissues, property_name):
    """
    Generates a cross-frequency plot for selected tissues and a given property.
    """
    os.makedirs("analysis/cpw/plots", exist_ok=True)
    plt.figure(figsize=(12, 8))

    for tissue in tissues:
        tissue_data = all_data[all_data["Tissue"] == tissue]
        if not tissue_data.empty:
            plt.plot(
                tissue_data["Frequency"],
                tissue_data[property_name],
                marker="o",
                label=tissue,
            )

    plt.xlabel("Frequency (MHz)")
    plt.ylabel(property_name)
    plt.title(f"{property_name} vs. Frequency for Selected Tissues")
    plt.xlim(400, 6000)
    if property_name == "RequiredGridSize_mm":
        plt.yscale("log")
        # Label each point for the eye
        eye_data = all_data[all_data["Tissue"] == "Eye_vitreous_humor"]
        if not eye_data.empty:
            for i, row in eye_data.iterrows():
                plt.annotate(
                    f"{row[property_name]:.2f}",
                    (row["Frequency"], row[property_name]),
                    textcoords="offset points",
                    xytext=(0, 5),
                    ha="center",
                )

    plt.legend()
    plt.grid(True)
    output_path = f"analysis/cpw/plots/cross_freq_{property_name}.png"
    plt.savefig(output_path)
    print(f"Plot saved to {output_path}")
    plt.close()


def plot_required_gridding_per_freq(df, frequency_mhz):
    """
    Generates a plot of the required grid size to achieve CPW=10.
    """
    os.makedirs("analysis/cpw/plots", exist_ok=True)

    c = 299792458  # Speed of light in m/s
    wavelength = c / (frequency_mhz * 1e6)

    # Calculate required grid size in mm for CPW=10
    df["RequiredGridSize_mm"] = (wavelength / (10 * np.sqrt(df["RelativePermittivity"]))) * 1000

    # Filter for the first half of the log scale
    min_grid = df["RequiredGridSize_mm"].min()
    max_grid = df["RequiredGridSize_mm"].max()
    cutoff = np.sqrt(min_grid * max_grid)
    plot_df = df[df["RequiredGridSize_mm"] <= cutoff]

    plt.figure(figsize=(14, 8))
    scatter = plt.scatter(
        plot_df["RequiredGridSize_mm"],
        plot_df["Total Volume"],
        c=plot_df["RelativePermittivity"],
        cmap="viridis",
        alpha=0.9,
        vmin=1,
    )
    plt.xscale("log")
    plt.yscale("log")

    cbar = plt.colorbar(scatter)
    cbar.set_label("Relative Permittivity")

    plt.xlabel("Required Grid Size (mm) for CPW=10")
    plt.ylabel("Total Volume (m^3) - Log Scale")
    plt.title(f"Required Grid Size for CPW=10 at {frequency_mhz} MHz")
    plt.grid(True)

    # Label all tissues
    for i, row in plot_df.iterrows():
        plt.annotate(
            row["Tissue"],
            (row["RequiredGridSize_mm"], row["Total Volume"]),
            fontsize=8,
            textcoords="offset points",
            xytext=(0, 5),
            ha="center",
        )

    output_path = f"analysis/cpw/plots/required_gridding_{frequency_mhz}.png"
    plt.savefig(output_path)
    print(f"Plot saved to {output_path}")
    plt.close()


def get_required_gridding_for_tissue(df, tissue_name, cpw_target=10):
    """
    Calculates the required grid size for a specific tissue to achieve a target CPW.
    """
    c = 299792458  # Speed of light in m/s

    tissue_df = df[df["Tissue"] == tissue_name].copy()
    if tissue_df.empty:
        return {}

    # Calculate required grid size in mm for the target CPW
    wavelength = c / (tissue_df["Frequency"] * 1e6)
    tissue_df["RequiredGridSize_mm"] = (wavelength / (cpw_target * np.sqrt(tissue_df["RelativePermittivity"]))) * 1000

    # Create a dictionary of {frequency: grid_size}
    gridding_dict = tissue_df.set_index("Frequency")["RequiredGridSize_mm"].to_dict()

    # Round to 3 decimal places for cleaner output
    return {k: round(v, 3) for k, v in gridding_dict.items()}


def plot_aggregated_required_gridding(df):
    """
    Generates an aggregated plot showing the max required grid size for each tissue.
    """
    os.makedirs("analysis/cpw/plots", exist_ok=True)

    # Find the max required grid size for each tissue across all frequencies
    max_grid_size_df = df.loc[df.groupby("Tissue")["RequiredGridSize_mm"].idxmax()]

    # Filter for the first half of the log scale
    min_grid = max_grid_size_df["RequiredGridSize_mm"].min()
    max_grid = max_grid_size_df["RequiredGridSize_mm"].max()
    cutoff = np.sqrt(min_grid * max_grid)
    plot_df = max_grid_size_df[max_grid_size_df["RequiredGridSize_mm"] <= cutoff]

    plt.figure(figsize=(14, 8))
    scatter = plt.scatter(
        plot_df["RequiredGridSize_mm"],
        plot_df["Total Volume"],
        c=plot_df["RelativePermittivity"],
        cmap="viridis",
        alpha=0.9,
        vmin=1,
    )
    plt.xscale("log")
    plt.yscale("log")

    cbar = plt.colorbar(scatter)
    cbar.set_label("Relative Permittivity (at worst-case frequency)")

    plt.xlabel("Maximum Required Grid Size (mm) for CPW=10")
    plt.ylabel("Total Volume (m^3) - Log Scale")
    plt.title("Aggregated Maximum Required Grid Size for CPW=10 Across All Frequencies")
    plt.grid(True)

    # Label all tissues
    for i, row in plot_df.iterrows():
        plt.annotate(
            f"{row['Tissue']} @ {int(row['Frequency'])}MHz",
            (row["RequiredGridSize_mm"], row["Total Volume"]),
            fontsize=8,
            textcoords="offset points",
            xytext=(0, 5),
            ha="center",
        )

    output_path = f"analysis/cpw/plots/aggregated_required_gridding.png"
    plt.savefig(output_path)
    print(f"Plot saved to {output_path}")
    plt.close()


if __name__ == "__main__":
    # --- Step 1: Extract Volume Data (if needed) ---
    # Ensure the path is correct for where the initial results are.
    # This might need to be adjusted based on the actual simulation output directory.
    html_path = "results/far_field/thelonious/450MHz/environmental_x_pos_theta/sar_stats_all_tissues.html"
    volume_pickle_path = "analysis/cpw/data/volume_data.pkl"
    if not os.path.exists(volume_pickle_path):
        volume_df = extract_volume_data(html_path)
        volume_df.to_pickle(volume_pickle_path)
        print(f"Volume data extracted and saved to {volume_pickle_path}")

    # --- Step 2: Process data for all frequencies ---
    with open("analysis/cpw/all_freq_setup_config.json", "r") as f:
        config = json.load(f)
    frequencies = config["frequencies_mhz"]

    all_merged_data = []

    for freq in frequencies:
        print(f"--- Processing frequency: {freq} MHz ---")
        material_props_path = f"analysis/cpw/data/material_properties_{freq}.pkl"
        mapping_path = "material_name_mapping.json"

        if not os.path.exists(material_props_path):
            print(f"Warning: Material properties file not found for {freq} MHz. Skipping.")
            continue

        merged_data = merge_data(volume_pickle_path, material_props_path, mapping_path)
        merged_data["Frequency"] = freq

        # Calculate CPW once
        c = 299792458  # Speed of light in m/s
        wavelength = c / (freq * 1e6)
        grid_size_mm = config.get("simulation_parameters", {}).get("global_gridding", 1.0)
        grid_size_m = grid_size_mm / 1000.0
        merged_data["CPW"] = wavelength / (grid_size_m * np.sqrt(merged_data["RelativePermittivity"]))

        all_merged_data.append(merged_data)

        # Plot individual frequency data
        plot_data(merged_data, freq)
        plot_cpw(merged_data, freq)
        plot_volume_vs_cpw(merged_data, freq)
        plot_required_gridding_per_freq(merged_data, freq)

    # --- Step 3: Create cross-frequency plots ---
    if all_merged_data:
        combined_df = pd.concat(all_merged_data, ignore_index=True)

        # Create aggregated plot
        plot_aggregated_required_gridding(combined_df)

        # --- Quantitative and Qualitative Analysis of Eye (Vitreous Humor) ---
        eye_tissues = ["Eye_vitreous_humor", "Eye_lens", "Eye_Sclera", "Cornea"]
        eye_df = combined_df[combined_df["Tissue"].isin(eye_tissues)]

        if not eye_df.empty:
            # Get unique volumes for each eye tissue
            eye_volumes = eye_df.drop_duplicates(subset=["Tissue"])

            total_eye_volume = eye_volumes["Total Volume"].sum()
            vitreous_humor_volume = eye_volumes[eye_volumes["Tissue"] == "Eye_vitreous_humor"]["Total Volume"].iloc[0]

            percentage = (vitreous_humor_volume / total_eye_volume) * 100

            print(f"\n--- Analysis of Eye (Vitreous Humor) Volume ---")
            print(f"The volume of the Eye (Vitreous Humor) is: {vitreous_humor_volume:.4e} m^3")
            print(f"The total volume of the eye is: {total_eye_volume:.4e} m^3")
            print(f"The Eye (Vitreous Humor) makes up {percentage:.2f}% of the total eye volume.")
            print(f"------------------------------------------------\n")

        critical_tissues = [
            "Brain (Grey Matter)",
            "Skin",
            "Muscle",
            "Fat",
            "Bone (Cortical)",
        ]

        plot_cross_frequency(combined_df, critical_tissues, "RelativePermittivity")
        plot_cross_frequency(combined_df, critical_tissues, "CPW")
        plot_cross_frequency(
            combined_df,
            ["Eye_vitreous_humor", "Stomach", "Muscle"],
            "RequiredGridSize_mm",
        )

        # --- Step 4: Get and print the required gridding for the eye ---
        required_gridding = get_required_gridding_for_tissue(combined_df, "Eye_vitreous_humor", cpw_target=10)
        if required_gridding:
            print("\n--- Required Gridding for Eye (Vitreous Humor) at CPW=10 ---")
            # Format as a JSON string for easy copy-pasting
            print(json.dumps({"global_gridding_per_frequency": required_gridding}, indent=4))
            print("----------------------------------------------------------\n")
