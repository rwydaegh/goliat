import re
import pandas as pd


def parse_log_file(log_file_path):
    with open(log_file_path, "r") as f:
        log_content = f.read()

    # Regex to find the start of each simulation's processing log
    frequency_blocks = re.split(
        r"--- Processing Frequency \d+/\d+: (\d+MHz) for Phantom \'(\w+)\' ---",
        log_content,
    )

    if len(frequency_blocks) < 2:
        return pd.DataFrame()

    data = []
    # Start from the first match, skipping the initial content before the first frequency block
    for i in range(1, len(frequency_blocks), 3):
        frequency_str = frequency_blocks[i]
        phantom_name = frequency_blocks[i + 1]
        block = frequency_blocks[i + 2]

        frequency_mhz = int(re.search(r"(\d+)MHz", frequency_str).group(1))

        # --- Extract total setup time ---
        finished_setup_match = re.search(r"--- Finished: setup \(took ([\d.]+)s\) ---", block)
        total_setup_time = float(finished_setup_match.group(1)) if finished_setup_match else None

        # --- Extract total time for BaseSetup._finalize_setup ---
        base_setup_finalize_match = re.search(
            r"Total time: ([\d.]+) s\s+File: .*base_setup\.py\s+Function: BaseSetup\._finalize_setup",
            block,
        )
        base_setup_finalize_time = float(base_setup_finalize_match.group(1)) if base_setup_finalize_match else None

        # --- Extract total time for FarFieldSetup.run_full_setup ---
        far_field_run_full_setup_match = re.search(
            r"Total time: ([\d.]+) s\s+File: .*far_field_setup\.py\s+Function: FarFieldSetup\.run_full_setup",
            block,
        )
        far_field_run_full_setup_time = float(far_field_run_full_setup_match.group(1)) if far_field_run_full_setup_match else None

        # --- Extract total time for FarFieldSetup._create_simulation_entity ---
        far_field_create_entity_match = re.search(
            r"Total time: ([\d.]+) s\s+File: .*far_field_setup\.py\s+Function: FarFieldSetup\._create_simulation_entity",
            block,
        )
        far_field_create_entity_time = float(far_field_create_entity_match.group(1)) if far_field_create_entity_match else None

        # --- Extract total time for FarFieldSetup._apply_common_settings ---
        far_field_apply_common_match = re.search(
            r"Total time: ([\d.]+) s\s+File: .*far_field_setup\.py\s+Function: FarFieldSetup\._apply_common_settings",
            block,
        )
        far_field_apply_common_time = float(far_field_apply_common_match.group(1)) if far_field_apply_common_match else None

        # --- Extract total time for FarFieldSetup._finalize_setup ---
        far_field_finalize_match = re.search(
            r"Total time: ([\d.]+) s\s+File: .*far_field_setup\.py\s+Function: FarFieldSetup\._finalize_setup",
            block,
        )
        far_field_finalize_time = float(far_field_finalize_match.group(1)) if far_field_finalize_match else None

        # --- Extract simulation time in periods ---
        sim_time_periods_match = re.search(r"Simulation time set to ([\d.]+) periods", block)
        sim_time_periods = float(sim_time_periods_match.group(1)) if sim_time_periods_match else None

        # --- Extract grid resolution ---
        grid_resolution_match = re.search(r"frequency-specific \(\d+MHz\) resolution: ([\d.]+) mm", block)
        grid_resolution = float(grid_resolution_match.group(1)) if grid_resolution_match else None

        data.append(
            {
                "Frequency (MHz)": frequency_mhz,
                "Total Setup Time (s)": total_setup_time,
                "BaseSetup._finalize_setup (s)": base_setup_finalize_time,
                "FarFieldSetup.run_full_setup (s)": far_field_run_full_setup_time,
                "FarFieldSetup._create_simulation_entity (s)": far_field_create_entity_time,
                "FarFieldSetup._apply_common_settings (s)": far_field_apply_common_time,
                "FarFieldSetup._finalize_setup (s)": far_field_finalize_time,
                "Simulation Time (periods)": sim_time_periods,
                "Grid Resolution (mm)": grid_resolution,
            }
        )

    df = pd.DataFrame(data)
    return df


if __name__ == "__main__":
    log_file = "logs/21-08_22-48-49.log"
    df = parse_log_file(log_file)

    # Identify columns where values are strictly increasing
    increasing_columns = []
    for col in df.columns:
        if df[col].is_monotonic_increasing and not df[col].is_unique:
            # Exclude columns that are constant
            if df[col].nunique() > 1:
                increasing_columns.append(col)

    if increasing_columns:
        print("Columns with increasing values:")
        # Format the output as a markdown table
        print(df[["Frequency (MHz)"] + increasing_columns].to_markdown(index=False))
    else:
        print("No columns with strictly increasing values found.")
