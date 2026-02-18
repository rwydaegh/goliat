"""
Extract APD data from auto_induced_summary.json files for Table 4.
"""

import json
from pathlib import Path

# Configuration
RESULTS_BASE = Path("results/auto_induced_FR3")
FREQUENCIES = [7, 9, 11, 13, 15]  # GHz
PHANTOMS = ["duke", "ella", "eartha", "thelonious"]
NORMALIZATION_FACTOR = 754  # (27.5)^2 to convert from 1 V/m to 1 W/m²


def extract_apd_data():
    """Extract worst-case APD for each phantom and frequency."""
    results = {}

    for phantom in PHANTOMS:
        results[phantom] = {}
        for freq in FREQUENCIES:
            json_path = RESULTS_BASE / f"{freq}GHz" / phantom / "auto_induced" / "auto_induced_summary.json"

            if json_path.exists():
                with open(json_path, "r") as f:
                    data = json.load(f)

                # Extract worst-case APD
                worst_case = data.get("worst_case", {})
                peak_sapd_raw = worst_case.get("peak_sapd_w_m2", None)

                if peak_sapd_raw is not None:
                    # Apply normalization
                    peak_sapd_normalized = peak_sapd_raw * NORMALIZATION_FACTOR
                    results[phantom][freq] = {
                        "raw": peak_sapd_raw,
                        "normalized": peak_sapd_normalized,
                        "candidate_idx": worst_case.get("candidate_idx", None),
                    }
                else:
                    results[phantom][freq] = None
                    print(f"WARNING: No worst_case data for {phantom} at {freq} GHz")
            else:
                results[phantom][freq] = None
                print(f"WARNING: File not found: {json_path}")

    return results


def print_table(results):
    """Print results in LaTeX table format."""
    print("\n" + "=" * 80)
    print("TABLE 4 DATA - Worst-Case APD by Phantom and Frequency")
    print("=" * 80)
    print("\nLaTeX format:")
    print("-" * 80)

    for phantom in PHANTOMS:
        values = []
        for freq in FREQUENCIES:
            data = results[phantom].get(freq)
            if data:
                values.append(f"{data['normalized']:.2f}")
            else:
                values.append("N/A")

        phantom_display = phantom.capitalize()
        print(f"{phantom_display} & {' & '.join(values)} \\\\")

    print("\n" + "=" * 80)
    print("DETAILED DATA")
    print("=" * 80)

    for phantom in PHANTOMS:
        print(f"\n{phantom.upper()}:")
        for freq in FREQUENCIES:
            data = results[phantom].get(freq)
            if data:
                print(f"  {freq} GHz: {data['normalized']:.4f} W/m² (raw: {data['raw']:.6f} W/m², candidate {data['candidate_idx']})")
            else:
                print(f"  {freq} GHz: No data")


def print_female_comparison(results):
    """Compare female phantom data."""
    print("\n" + "=" * 80)
    print("FEMALE PHANTOMS COMPARISON")
    print("=" * 80)

    print("\n{:<12} {:<10} {:<10}".format("Frequency", "Ella (26y)", "Eartha (8y)"))
    print("-" * 35)

    for freq in FREQUENCIES:
        ella_val = results["ella"].get(freq)
        eartha_val = results["eartha"].get(freq)

        ella_str = f"{ella_val['normalized']:.2f}" if ella_val else "N/A"
        eartha_str = f"{eartha_val['normalized']:.2f}" if eartha_val else "N/A"

        print(f"{freq} GHz      {ella_str:<10} {eartha_str:<10}")

    print("\nNote: Values in W/m² at 1 W/m² incident power density")


if __name__ == "__main__":
    results = extract_apd_data()
    print_table(results)
    print_female_comparison(results)

    # Verify against Table 4 values
    print("\n" + "=" * 80)
    print("VERIFICATION AGAINST TABLE 4")
    print("=" * 80)

    table4_values = {
        "duke": [1.84, 1.19, 0.86, 0.65, 0.50],
        "ella": [1.98, 1.77, 1.31, 0.92, 0.81],
        "eartha": [1.88, 1.40, 1.00, 0.65, 0.74],
        "thelonious": [2.05, 1.31, 0.86, 0.57, 0.61],
    }

    print("\nComparison (Table vs Calculated):")
    all_match = True
    for phantom in PHANTOMS:
        print(f"\n{phantom.upper()}:")
        for i, freq in enumerate(FREQUENCIES):
            data = results[phantom].get(freq)
            if data:
                table_val = table4_values[phantom][i]
                calc_val = data["normalized"]
                match = abs(table_val - calc_val) < 0.01
                status = "✓" if match else "✗"
                print(f"  {freq} GHz: Table={table_val:.2f}, Calculated={calc_val:.2f} {status}")
                if not match:
                    all_match = False
            else:
                print(f"  {freq} GHz: No data to compare")

    if all_match:
        print("\n✓ All values match Table 4!")
    else:
        print("\n✗ Some values don't match - check normalization or data files")
