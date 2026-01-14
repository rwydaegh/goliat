#!/usr/bin/env python
"""Convert cross-section pickle files to JSON for numpy version compatibility."""

import json
import pickle
from pathlib import Path


def convert_pkl_to_json(pkl_path: Path) -> Path:
    """Convert a pickle file to JSON format.

    Args:
        pkl_path: Path to the pickle file.

    Returns:
        Path to the created JSON file.
    """
    with open(pkl_path, "rb") as f:
        data = pickle.load(f)

    # Convert numpy arrays to lists
    json_data = {
        "theta": data["theta"].tolist(),
        "phi": data["phi"].tolist(),
        "areas": data["areas"].tolist(),
        "units": data["units"],
        "stats": data["stats"],
        "phantom_name": data["phantom_name"],
        "bounding_box": data["bounding_box"] if isinstance(data["bounding_box"], list) else data["bounding_box"].tolist(),
        "n_theta": int(data.get("n_theta", len(data["theta"]))),
        "n_phi": int(data.get("n_phi", len(data["phi"][0]) if len(data["phi"]) > 0 else 0)),
    }

    json_path = pkl_path.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)

    print(f"Converted {pkl_path.name} -> {json_path.name} ({json_path.stat().st_size / 1024:.1f} KB)")
    return json_path


def main():
    """Convert all cross-section pickle files to JSON."""
    base_dir = Path(__file__).parent.parent / "data" / "phantom_skins"

    pkl_files = list(base_dir.rglob("cross_section_pattern.pkl"))

    if not pkl_files:
        print(f"No pickle files found in {base_dir}")
        return

    print(f"Found {len(pkl_files)} pickle files to convert:\n")

    for pkl_path in pkl_files:
        try:
            convert_pkl_to_json(pkl_path)
        except Exception as e:
            print(f"ERROR converting {pkl_path}: {e}")

    print("\nDone! You can now delete the .pkl files if desired.")


if __name__ == "__main__":
    main()
