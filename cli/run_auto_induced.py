"""CLI runner for auto-induced exposure analysis.

Config-driven approach that matches GOLIAT patterns.
"""

import argparse
import glob
import json
import sys
import time
from pathlib import Path


def main():
    """Main entry point for auto-induced CLI command."""
    parser = argparse.ArgumentParser(
        prog="goliat auto-induced",
        description="Auto-induced exposure: find worst-case SAPD from combined fields",
    )
    parser.add_argument(
        "config",
        type=str,
        help="Path to configuration file (JSON) with auto_induced settings",
    )
    parser.add_argument(
        "--skip-sapd",
        action="store_true",
        help="Skip SAPD extraction (only create combined H5 files)",
    )

    args = parser.parse_args()

    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        # Try adding configs/ prefix and .json suffix
        candidates = [
            config_path,
            Path("configs") / config_path,
            Path("configs") / f"{config_path}.json",
            config_path.with_suffix(".json"),
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = candidate
                break
        else:
            print(f"ERROR: Config file not found: {args.config}")
            sys.exit(1)

    # Parse config (with extends support)
    from goliat.config import Config

    config = Config(str(config_path))

    # Print header
    print("\n" + "=" * 60)
    print("GOLIAT Auto-Induced Exposure Analysis")
    print("=" * 60)
    print(f"Config: {config_path}")

    # Get auto_induced settings from config
    auto_induced_cfg = config["auto_induced"] or {}

    if not auto_induced_cfg:
        print("\nERROR: No 'auto_induced' section in config. Add:")
        print("""
    "auto_induced": {
        "enabled": true,
        "top_n": 3,
        "cube_size_mm": 100
    }
""")
        sys.exit(1)

    if not auto_induced_cfg.get("enabled", True):
        print("\nAuto-induced is disabled in config (enabled: false)")
        sys.exit(0)

    # Extract settings with defaults
    top_n = auto_induced_cfg.get("top_n", 1)
    cube_size_mm = auto_induced_cfg.get("cube_size_mm", 100.0)
    skip_sapd = args.skip_sapd or auto_induced_cfg.get("skip_sapd", False)

    # Determine paths from config
    phantoms = config["phantoms"] or []
    if not isinstance(phantoms, list):
        phantoms = [phantoms]
    frequencies = config["frequencies_mhz"] or []
    if not isinstance(frequencies, list):
        frequencies = [frequencies]

    base_dir = config.base_dir
    study_type = "far_field"  # Auto-induced is always far-field post-processing

    print("\nSettings:")
    print(f"  Top N candidates: {top_n}")
    print(f"  Cube size: {cube_size_mm} mm")
    print(f"  Skip SAPD: {skip_sapd}")
    print(f"  Phantoms: {phantoms}")
    print(f"  Frequencies: {frequencies} MHz")

    # Process each phantom/frequency combination
    for phantom in phantoms:
        for freq in frequencies:
            freq_str = str(freq)
            print(f"\n{'=' * 60}")
            print(f"Processing: {phantom} @ {freq_str} MHz")
            print("=" * 60)

            # Locate results directory
            results_dir = Path(base_dir) / "results" / study_type / phantom / f"{freq_str}MHz"
            if not results_dir.exists():
                print(f"  WARNING: Results directory not found: {results_dir}")
                continue

            # Find H5 files
            h5_patterns = glob.glob(str(results_dir / "**" / "*_Output.h5"), recursive=True)
            # Exclude any already-combined files in auto_induced subdirectory
            h5_paths = sorted([p for p in h5_patterns if "auto_induced" not in p])

            if not h5_paths:
                print(f"  WARNING: No _Output.h5 files found in {results_dir}")
                continue

            print(f"  Found {len(h5_paths)} _Output.h5 files")

            # Find _Input.h5 (any one will do, they're all the same grid)
            input_h5_patterns = glob.glob(str(results_dir / "**" / "*_Input.h5"), recursive=True)
            input_h5_paths = [p for p in input_h5_patterns if "auto_induced" not in p]

            if not input_h5_paths:
                print(f"  WARNING: No _Input.h5 files found in {results_dir}")
                continue

            input_h5 = input_h5_paths[0]
            print(f"  Using input H5: {Path(input_h5).name}")

            # Output directory
            output_dir = results_dir / "auto_induced"
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"  Output: {output_dir}")

            # Run the workflow
            _run_auto_induced_workflow(
                h5_paths=h5_paths,
                input_h5=input_h5,
                output_dir=output_dir,
                config_path=str(config_path),
                top_n=top_n,
                cube_size_mm=cube_size_mm,
                skip_sapd=skip_sapd,
            )

    print("\n" + "=" * 60)
    print("Auto-Induced Analysis Complete")
    print("=" * 60)


def _run_auto_induced_workflow(
    h5_paths: list,
    input_h5: str,
    output_dir: Path,
    config_path: str,
    top_n: int,
    cube_size_mm: float,
    skip_sapd: bool,
):
    """Run the auto-induced workflow for a single phantom/frequency."""
    import numpy as np

    # Step 1: Find focus points
    print(f"\n  --- Step 1: Finding top-{top_n} worst-case focus points ---")
    t1 = time.perf_counter()

    from goliat.utils.focus_optimizer import find_focus_and_compute_weights, compute_optimal_phases, compute_weights

    focus_indices, weights, info = find_focus_and_compute_weights(h5_paths, input_h5, top_n=top_n)

    if top_n == 1:
        focus_indices = np.array([focus_indices])

    t1_elapsed = time.perf_counter() - t1
    print(f"    Found {len(focus_indices)} candidate(s) in {t1_elapsed:.2f}s:")
    for i, (focus_idx, mag_sum) in enumerate(zip(focus_indices, info["all_magnitude_sums"])):
        print(f"      #{i + 1}: voxel [{focus_idx[0]}, {focus_idx[1]}, {focus_idx[2]}], Σ|E|={mag_sum:.4e}")

    # Step 2: Combine fields
    print("\n  --- Step 2: Combining fields ---")
    t2 = time.perf_counter()

    from goliat.utils.field_combiner import combine_fields_sliced

    combined_h5_paths = []
    for i, focus_idx in enumerate(focus_indices):
        phases = compute_optimal_phases(h5_paths, focus_idx)
        candidate_weights = compute_weights(phases)

        if top_n == 1:
            output_h5 = output_dir / "combined_Output.h5"
        else:
            output_h5 = output_dir / f"combined_candidate{i + 1}_Output.h5"

        print(f"    Candidate #{i + 1}: {output_h5.name}")

        result = combine_fields_sliced(
            h5_paths=h5_paths,
            weights=candidate_weights,
            template_h5_path=h5_paths[0],
            output_h5_path=str(output_h5),
            center_idx=focus_idx,
            side_length_mm=cube_size_mm,
        )
        combined_h5_paths.append(output_h5)
        print(f"      Sliced shape: {result['sliced_shape']}")

    t2_elapsed = time.perf_counter() - t2
    print(f"    Combined {len(combined_h5_paths)} file(s) in {t2_elapsed:.2f}s")

    # Step 3: SAPD extraction
    sapd_results = []
    if skip_sapd:
        print("\n  --- Skipping SAPD extraction ---")
    else:
        print("\n  --- Step 3: Extracting SAPD ---")
        t3 = time.perf_counter()

        for i, combined_h5 in enumerate(combined_h5_paths):
            print(f"    Candidate #{i + 1}: {combined_h5.name}")

            try:
                from goliat.extraction.auto_induced_extractor import extract_sapd_from_h5

                result = extract_sapd_from_h5(
                    combined_h5_path=str(combined_h5),
                    config_path=config_path,
                    output_dir=str(output_dir),
                    candidate_index=i + 1,
                )
                sapd_results.append(result)

                if result and "peak_sapd_W_m2" in result:
                    print(f"      Peak SAPD: {result['peak_sapd_W_m2']:.4f} W/m²")
                else:
                    print("      SAPD extraction returned no data")
            except Exception as e:
                print(f"      ERROR: {e}")
                sapd_results.append({"error": str(e)})

        t3_elapsed = time.perf_counter() - t3
        print(f"    Extracted SAPD in {t3_elapsed:.2f}s")

    # Write summary
    summary = {
        "n_directions": len(h5_paths),
        "n_candidates": top_n,
        "cube_size_mm": cube_size_mm,
        "combined_h5_files": [str(p) for p in combined_h5_paths],
        "focus_points": [
            {
                "voxel_index": focus_idx.tolist(),
                "magnitude_sum": float(mag_sum),
            }
            for focus_idx, mag_sum in zip(focus_indices, info["all_magnitude_sums"])
        ],
    }

    if sapd_results:
        summary["sapd_results"] = sapd_results
        valid_sapd = [r.get("peak_sapd_W_m2") for r in sapd_results if r.get("peak_sapd_W_m2")]
        if valid_sapd:
            worst_sapd = max(valid_sapd)
            worst_idx = [r.get("peak_sapd_W_m2") for r in sapd_results].index(worst_sapd)
            summary["worst_case"] = {
                "candidate_index": worst_idx + 1,
                "peak_sapd_W_m2": worst_sapd,
            }
            print(f"\n    Worst-case SAPD: {worst_sapd:.4f} W/m² (candidate #{worst_idx + 1})")

    summary_path = output_dir / "auto_induced_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n    Summary: {summary_path}")


if __name__ == "__main__":
    main()
