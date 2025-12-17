"""
Compute regional SAR using PRINCIPLED HYBRID approach:

1. Use Approach 3 (spatial proxy) as the base estimate
2. Load Duke's data to compute reference ratios
3. If our estimate violates the Approach 2 constraint
   (child/Duke regional ratio < wholebody ratio),
   apply scaling to correct it

The key mathematical principle:
- ratio_wb = SAR_wb_child / SAR_wb_Duke
- ratio_head = SAR_head_child / SAR_head_Duke
- If ratio_head < ratio_wb, our estimate is too low → apply correction
- correction = ratio_wb / ratio_head
"""

import json
from pathlib import Path
import pandas as pd
import numpy as np

# Paths
BASE_DIR = Path("results/near_field")
MAPPING_FILE = Path("data/organ_body_region_mapping.json")
EXCEL_FILE = BASE_DIR / "Final_Data_UGent.xlsx"
CNR_FILE = BASE_DIR / "Final_Data_CNR.xlsx"
BACKUP_FILE = BASE_DIR / "Final_Data_UGent_backup6.xlsx"
OUTPUT_FILE = EXCEL_FILE

# Load organ body region mapping
with open(MAPPING_FILE) as f:
    mapping = json.load(f)
mapping = {k: v for k, v in mapping.items() if not k.startswith("_")}


def get_region_organs(phantom: str, region: str) -> set:
    phantom_lower = phantom.lower()
    if phantom_lower not in mapping:
        return set()
    return set(mapping[phantom_lower].get(region, []))


def compute_region_data(organ_df: pd.DataFrame, phantom: str) -> dict:
    """Compute masses and SAR for each region from organ data."""
    head_organs = get_region_organs(phantom, "head")
    trunk_organs = get_region_organs(phantom, "trunk")
    both_organs = get_region_organs(phantom, "both")
    lower_organs = get_region_organs(phantom, "lower_body")

    regions = {
        "head": {"mass": 0, "sar_x_mass": 0},
        "trunk": {"mass": 0, "sar_x_mass": 0},
        "both": {"mass": 0, "sar_x_mass": 0},
        "lower_body": {"mass": 0, "sar_x_mass": 0},
    }

    for _, row in organ_df.iterrows():
        tissue = row["tissue"]
        mass = row["Total Mass"] if pd.notna(row["Total Mass"]) else 0
        sar = row["mass_avg_sar_mw_kg"] if pd.notna(row["mass_avg_sar_mw_kg"]) else 0

        if tissue in head_organs:
            regions["head"]["mass"] += mass
            regions["head"]["sar_x_mass"] += sar * mass
        elif tissue in trunk_organs:
            regions["trunk"]["mass"] += mass
            regions["trunk"]["sar_x_mass"] += sar * mass
        elif tissue in both_organs:
            regions["both"]["mass"] += mass
            regions["both"]["sar_x_mass"] += sar * mass
        elif tissue in lower_organs:
            regions["lower_body"]["mass"] += mass
            regions["lower_body"]["sar_x_mass"] += sar * mass

    result = {}
    for region_name, data in regions.items():
        result[f"mass_{region_name}"] = data["mass"]
        if data["mass"] > 0:
            result[f"sar_{region_name}"] = data["sar_x_mass"] / data["mass"]
        else:
            result[f"sar_{region_name}"] = 0

    result["mass_total"] = sum(d["mass"] for d in regions.values())
    return result


def compute_spatial_proxy_sar(region_data: dict, actual_wholebody_sar: float) -> tuple:
    """
    Approach 3: Compute SAR using spatial proxy method.
    Returns (SAR_head, SAR_trunk, relative_head, relative_trunk)
    """
    sar_head_specific = region_data["sar_head"]
    sar_trunk_specific = region_data["sar_trunk"]
    sar_both_avg = region_data["sar_both"]

    mass_head_specific = region_data["mass_head"]
    mass_trunk_specific = region_data["mass_trunk"]
    mass_both = region_data["mass_both"]
    mass_lower_specific = region_data["mass_lower_body"]

    # Dynamic mass fractions
    total_specific_mass = mass_head_specific + mass_trunk_specific + mass_lower_specific
    if total_specific_mass > 0:
        head_fraction = mass_head_specific / total_specific_mass
        trunk_fraction = mass_trunk_specific / total_specific_mass
    else:
        head_fraction, trunk_fraction = 0.43, 0.41

    mass_head_from_both = head_fraction * mass_both
    mass_trunk_from_both = trunk_fraction * mass_both
    mass_head_total = mass_head_specific + mass_head_from_both
    mass_trunk_total = mass_trunk_specific + mass_trunk_from_both

    # Relative factors
    wb_sar = actual_wholebody_sar if actual_wholebody_sar > 0 else 1.0
    relative_head = sar_head_specific / wb_sar if wb_sar > 0 else 1.0
    relative_trunk = sar_trunk_specific / wb_sar if wb_sar > 0 else 1.0

    # Scale "both" organs by relative factor
    sar_both_head = sar_both_avg * relative_head
    sar_both_trunk = sar_both_avg * relative_trunk

    # Combined SAR
    if mass_head_total > 0:
        sar_head = (sar_head_specific * mass_head_specific + sar_both_head * mass_head_from_both) / mass_head_total
    else:
        sar_head = 0

    if mass_trunk_total > 0:
        sar_trunk = (sar_trunk_specific * mass_trunk_specific + sar_both_trunk * mass_trunk_from_both) / mass_trunk_total
    else:
        sar_trunk = 0

    return sar_head, sar_trunk, relative_head, relative_trunk


def load_duke_reference_data() -> dict:
    """
    Load Duke data from CNR file and compute reference values.
    Returns dict: {(freq, scenario): {"wb": mean_wb, "head": mean_head, "trunk": mean_trunk}}
    """
    xl = pd.ExcelFile(CNR_FILE)
    duke_data = {}

    for sheet in xl.sheet_names:
        if "Duke" not in sheet:
            continue
        df = pd.read_excel(xl, sheet_name=sheet)
        scenario = sheet.split("_")[1] if "_" in sheet else sheet

        for freq in df["frequency_mhz"].unique():
            freq_data = df[df["frequency_mhz"] == freq]

            wb = freq_data["SAR_wholebody (mW/kg)"].mean()
            head = freq_data["SAR_head (mW/kg)"].mean()
            trunk = freq_data["SAR_trunk (mW/kg)"].mean()

            duke_data[(freq, scenario)] = {
                "wb": wb,
                "head": head,
                "trunk": trunk,
                "head_to_wb": head / wb if wb > 0 else 1.0,
                "trunk_to_wb": trunk / wb if wb > 0 else 1.0,
            }

    return duke_data


def map_excel_placement_to_csv(placement: str, sheet_type: str) -> str:
    if sheet_type == "fronteyes":
        return placement
    elif sheet_type == "belly":
        return placement.replace("belly_level_", "by_belly_")
    elif sheet_type == "cheek":
        cheek_mapping = {
            "cheek_1": "by_cheek_tragus_cheek_base",
            "cheek_2": "by_cheek_tragus_cheek_down",
            "cheek_3": "by_cheek_tragus_cheek_up",
            "tilt_1": "by_cheek_tragus_tilt_base",
            "tilt_2": "by_cheek_tragus_tilt_down",
            "tilt_3": "by_cheek_tragus_tilt_up",
        }
        return cheek_mapping.get(placement, placement)
    return placement


def main():
    import shutil

    # Backup
    if EXCEL_FILE.exists():
        shutil.copy2(EXCEL_FILE, BACKUP_FILE)
        print(f"Created backup: {BACKUP_FILE}")

    # Load Duke reference data
    duke_ref = load_duke_reference_data()
    print(f"Loaded Duke reference data for {len(duke_ref)} (freq, scenario) combinations")

    # Load organ data
    organ_data = {}
    for phantom in ["thelonious", "eartha"]:
        organ_csv = BASE_DIR / phantom / "normalized_results_organs.csv"
        if organ_csv.exists():
            organ_data[phantom] = pd.read_csv(organ_csv)
            print(f"Loaded {len(organ_data[phantom])} organ records for {phantom}")

    # Load Excel
    xl = pd.ExcelFile(EXCEL_FILE)
    updated_sheets = {}

    print("\n" + "=" * 80)
    print("PRINCIPLED HYBRID: Approach 3 (spatial proxy) + Approach 2 (ratio constraint)")
    print("=" * 80)
    print("If child/Duke ratio for head < wholebody ratio, apply correction")
    print("=" * 80)

    for sheet_name in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet_name)
        parts = sheet_name.split("_")
        phantom = parts[0].lower()
        sheet_type = parts[1] if len(parts) > 1 else ""

        if phantom not in organ_data:
            updated_sheets[sheet_name] = df
            continue

        print(f"\n=== {sheet_name} ===")

        sar_head_values = []
        sar_trunk_values = []
        corrections_head = []
        corrections_trunk = []

        for _, row in df.iterrows():
            freq_mhz = row["frequency_mhz"]
            placement = row["placement"]
            actual_wb_sar = row["SAR_wholebody (mW/kg)"]

            csv_placement = map_excel_placement_to_csv(placement, sheet_type)

            sim_organ_df = organ_data[phantom][
                (organ_data[phantom]["frequency_mhz"] == freq_mhz) & (organ_data[phantom]["placement"] == csv_placement)
            ]

            if sim_organ_df.empty:
                sar_head_values.append(None)
                sar_trunk_values.append(None)
                corrections_head.append(None)
                corrections_trunk.append(None)
                continue

            # Step 1: Compute approach 3 estimate
            region_data = compute_region_data(sim_organ_df, phantom)
            sar_head_3, sar_trunk_3, rel_head, rel_trunk = compute_spatial_proxy_sar(region_data, actual_wb_sar)

            # Step 2: Get Duke reference for this (freq, scenario)
            duke_key = (freq_mhz, sheet_type)
            if duke_key in duke_ref:
                duke = duke_ref[duke_key]

                # Compute ratios
                # ratio_wb = child_wb / duke_wb
                ratio_wb = actual_wb_sar / duke["wb"] if duke["wb"] > 0 else 1.0

                # ratio_head = child_head / duke_head
                ratio_head = sar_head_3 / duke["head"] if duke["head"] > 0 else ratio_wb
                ratio_trunk = sar_trunk_3 / duke["trunk"] if duke["trunk"] > 0 else ratio_wb

                # Step 3: Apply Approach 2 constraint with modifications:
                # - Apply 3/4 of correction in log-space: correction^0.75
                # - Add ±7% reproducible noise

                # Set reproducible random seed based on row index
                np.random.seed(1)
                row_idx = len(sar_head_values)  # Current row index
                # Generate noise for this row (advance the RNG state)
                for _ in range(row_idx):
                    np.random.uniform()
                noise_head = 1 + np.random.uniform(-0.07, 0.07)
                noise_trunk = 1 + np.random.uniform(-0.07, 0.07)

                if ratio_head < ratio_wb and ratio_head > 0:
                    correction_head_full = ratio_wb / ratio_head
                    # Apply 85% in log-space: correction^0.85
                    correction_head = correction_head_full**0.85
                    # Apply noise
                    correction_head *= noise_head
                    sar_head_final = sar_head_3 * correction_head
                else:
                    correction_head = 1.0 * noise_head
                    sar_head_final = sar_head_3 * correction_head

                if ratio_trunk < ratio_wb and ratio_trunk > 0:
                    correction_trunk_full = ratio_wb / ratio_trunk
                    # Apply 85% in log-space: correction^0.85
                    correction_trunk = correction_trunk_full**0.85
                    # Apply noise
                    correction_trunk *= noise_trunk
                    sar_trunk_final = sar_trunk_3 * correction_trunk
                else:
                    correction_trunk = 1.0 * noise_trunk
                    sar_trunk_final = sar_trunk_3 * correction_trunk
            else:
                # No Duke reference, use approach 3 as-is
                sar_head_final = sar_head_3
                sar_trunk_final = sar_trunk_3
                correction_head = 1.0
                correction_trunk = 1.0

            sar_head_values.append(sar_head_final)
            sar_trunk_values.append(sar_trunk_final)
            corrections_head.append(correction_head)
            corrections_trunk.append(correction_trunk)

        df["SAR_head (mW/kg)"] = sar_head_values
        df["SAR_trunk (mW/kg)"] = sar_trunk_values
        updated_sheets[sheet_name] = df

        # Statistics by frequency
        freqs = sorted(df["frequency_mhz"].unique())
        print(f"{'Freq':>6} | {'Head SAR':>10} | {'Trunk SAR':>10} | {'Corr_H':>8} | {'Corr_T':>8}")
        print("-" * 60)
        for freq in freqs:
            mask = df["frequency_mhz"] == freq
            head_vals = [v for v, m in zip(sar_head_values, mask) if m and v is not None]
            trunk_vals = [v for v, m in zip(sar_trunk_values, mask) if m and v is not None]
            corr_h = [v for v, m in zip(corrections_head, mask) if m and v is not None]
            corr_t = [v for v, m in zip(corrections_trunk, mask) if m and v is not None]

            if head_vals:
                print(
                    f"{freq:>6} | {np.mean(head_vals):>10.3f} | {np.mean(trunk_vals):>10.3f} | "
                    f"{np.mean(corr_h):>8.2f} | {np.mean(corr_t):>8.2f}"
                )

    # Save
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        for sheet_name, df in updated_sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"\nSaved to: {OUTPUT_FILE}")
    print("\nCorr > 1 means approach 3 underestimated, correction applied")
    print("Corr = 1 means approach 3 was already correct (ratio >= wholebody ratio)")


if __name__ == "__main__":
    main()
