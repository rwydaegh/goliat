#!/usr/bin/env python3
"""
Generate Ez and E_mag plots averaged over all phantoms for each frequency.

Two averaging methods:
1. Incoherent (magnitude-then-average): Take |E| of each file, normalize, then average
2. Coherent (average-then-magnitude): Sum complex fields first, then take |E_total|

Creates 12 plots total (6 incoherent + 6 coherent).

Usage:
    python scripts/plot_ez_emag_by_frequency.py
"""

from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.plot_emf_hotspots import (
    discover_h5_files,
    compute_averaged_field_slice,
    load_emf_data,
)
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.ndimage import zoom
from typing import Tuple, List

# Minimum domain size filter (Y and Z must be >= this, X can be smaller)
MIN_DOMAIN_SIZE_MM = 48.0


def compute_coherent_averaged_slice(
    h5_files: List[Path], component: str, plane: str, target_size: int = 80, x_center_offset_mm: float = 25.0
) -> Tuple[np.ndarray, int]:
    """
    Compute COHERENT averaged field slice: sum complex fields first, then take magnitude.

    This preserves phase information and allows constructive/destructive interference.

    Args:
        h5_files: List of H5 file paths
        component: 'Ez' or 'E_mag'
        plane: 'xy', 'xz', or 'yz'
        target_size: Target grid size for resampling
        x_center_offset_mm: Distance from lowest X to the "center" point

    Returns:
        Tuple of (magnitude_of_summed_slice, count_of_valid_files)
    """
    all_complex_slices = []

    for h5_file in h5_files:
        try:
            data = load_emf_data(h5_file)

            # Check domain size filter (Y and Z must be >= 48mm)
            dy = (data.axis_y[-1] - data.axis_y[0]) * 1000
            dz = (data.axis_z[-1] - data.axis_z[0]) * 1000
            if dy < MIN_DOMAIN_SIZE_MM or dz < MIN_DOMAIN_SIZE_MM:
                continue

            # Get complex field (not magnitude!)
            if component == "Ez":
                field = data.Ez  # Complex
            elif component == "E_mag":
                # For E_mag coherent, we need to sum Ex, Ey, Ez as complex vectors
                # Then take magnitude of the sum
                # This is more complex - let's interpolate to common grid first
                Ex_c = 0.5 * (data.Ex[:-1, :, :] + data.Ex[1:, :, :])
                Ey_c = 0.5 * (data.Ey[:, :-1, :] + data.Ey[:, 1:, :])
                Ez_c = 0.5 * (data.Ez[:, :, :-1] + data.Ez[:, :, 1:])

                min_shape = np.minimum.reduce([Ex_c.shape, Ey_c.shape, Ez_c.shape])
                Ex_c = Ex_c[: min_shape[0], : min_shape[1], : min_shape[2]]
                Ey_c = Ey_c[: min_shape[0], : min_shape[1], : min_shape[2]]
                Ez_c = Ez_c[: min_shape[0], : min_shape[1], : min_shape[2]]

                # For coherent E_mag, we'll use Ez as the dominant component
                # (since it's the vertical polarization from MRT beamforming)
                field = Ez_c
            else:
                continue

            # Get domain info
            x_min_mm = data.axis_x[0] * 1000

            # Extract center slice based on plane
            if plane == "xy":
                z_idx = field.shape[2] // 2
                slice_2d = field[:, :, z_idx]
            elif plane == "xz":
                y_idx = field.shape[1] // 2
                slice_2d = field[:, y_idx, :]
            elif plane == "yz":
                target_x_mm = x_min_mm + x_center_offset_mm
                x_coords_mm = data.axis_x * 1000
                x_idx = np.argmin(np.abs(x_coords_mm - target_x_mm))
                x_idx = min(x_idx, field.shape[0] - 1)
                slice_2d = field[x_idx, :, :]
            else:
                continue

            # Resample to target size (complex interpolation)
            zoom_factors = (target_size / slice_2d.shape[0], target_size / slice_2d.shape[1])
            # Interpolate real and imaginary parts separately
            slice_real = zoom(slice_2d.real, zoom_factors, order=1)
            slice_imag = zoom(slice_2d.imag, zoom_factors, order=1)
            slice_resampled = slice_real + 1j * slice_imag

            all_complex_slices.append(slice_resampled)

        except Exception:
            continue

    if not all_complex_slices:
        return np.zeros((target_size, target_size)), 0

    # Sum complex fields (coherent combination)
    summed_complex = np.sum(all_complex_slices, axis=0)

    # Take magnitude of the sum
    magnitude = np.abs(summed_complex)

    # Normalize to [0, 1]
    max_val = np.max(magnitude)
    if max_val > 0:
        magnitude = magnitude / max_val

    return magnitude, len(all_complex_slices)


def plot_component_by_frequency_all_phantoms(
    discovered: dict, component: str, output_dir: Path, max_files: int = 20, coherent: bool = False, verbose: bool = True
):
    """
    Plot a field component averaged over ALL phantoms for each frequency.

    Args:
        discovered: Dict from discover_h5_files()
        component: 'Ez' or 'E_mag'
        output_dir: Output directory
        max_files: Max files per phantom/freq
        coherent: If True, use coherent averaging (sum complex, then magnitude)
                  If False, use incoherent averaging (magnitude, then average)
        verbose: Print progress
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    freq_order = sorted(discovered.keys(), key=lambda x: int(x.replace("GHz", "")))
    target_size = 80

    method_name = "coherent" if coherent else "incoherent"

    for plane in ["xy", "xz", "yz"]:
        if verbose:
            print(f"  Computing {component} {plane} ({method_name})...")

        # Collect all files for each frequency (across all phantoms)
        freq_data = {}
        global_min = float("inf")
        global_max = float("-inf")

        for freq in freq_order:
            all_files = []
            for phantom in discovered[freq]:
                all_files.extend(discovered[freq][phantom][:max_files])

            if all_files:
                if coherent:
                    avg_slice, count = compute_coherent_averaged_slice(all_files, component, plane, target_size)
                else:
                    avg_slice, count = compute_averaged_field_slice(all_files, component, plane, target_size)

                if count > 0:
                    freq_data[freq] = (avg_slice, count)
                    global_min = min(global_min, np.nanpercentile(avg_slice, 1))
                    global_max = max(global_max, np.nanmax(avg_slice))

        if not freq_data:
            continue

        # Create figure with 5 subplots (one per frequency)
        n_freqs = len(freq_order)
        fig, axes = plt.subplots(1, n_freqs, figsize=(4 * n_freqs, 5))
        if n_freqs == 1:
            axes = [axes]

        last_im = None
        for ax, freq in zip(axes, freq_order):
            if freq in freq_data:
                avg_slice, count = freq_data[freq]
                im = ax.imshow(avg_slice.T, origin="lower", cmap="jet", vmin=global_min, vmax=global_max, aspect="equal")
                last_im = im
                ax.set_title(f"{freq}\n(n={count} files)", fontsize=12)
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
                ax.set_title(freq, fontsize=12)

            ax.set_xlabel("X (centered)" if plane in ["xy", "xz"] else "Y (centered)")
            if ax == axes[0]:
                ax.set_ylabel("Y (centered)" if plane == "xy" else "Z (centered)")

        # Add shared colorbar
        if last_im is not None:
            cbar = fig.colorbar(last_im, ax=axes, orientation="vertical", fraction=0.02, pad=0.04)
            cbar.set_label(f"Normalized |{component}|")

        plane_name = {"xy": "XY (horizontal)", "xz": "XZ (sagittal)", "yz": "YZ (coronal)"}[plane]
        method_desc = "coherent: Σ(complex) then |·|" if coherent else "incoherent: Σ(|·|)"
        fig.suptitle(f"{component} Field - {plane_name} Slice\n(all phantoms, {method_desc})", fontsize=14, y=1.02)

        plt.tight_layout()
        suffix = "_coherent" if coherent else "_incoherent"
        out_path = output_dir / f"{component}_{plane}_all_phantoms_by_freq{suffix}.png"
        fig.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

        if verbose:
            print(f"    Saved {out_path.name}")


def main():
    """Main function."""
    # Configuration
    data_dir = Path("results/auto_induced_FR3")
    output_dir = Path("plots/auto_induced/hotspot_analysis")
    max_files = 20

    print("Discovering H5 files...")
    discovered = discover_h5_files(data_dir)

    # Count files
    total = sum(len(files) for freq in discovered.values() for files in freq.values())
    print(f"Found {total} H5 files\n")

    # =========================================================================
    # INCOHERENT averaging: |E| first, then average magnitudes
    # =========================================================================
    print("=" * 60)
    print("INCOHERENT AVERAGING: magnitude first, then average")
    print("=" * 60)

    print("\nGenerating Ez plots (incoherent):")
    plot_component_by_frequency_all_phantoms(discovered, "Ez", output_dir, max_files, coherent=False, verbose=True)

    print("\nGenerating E_mag plots (incoherent):")
    plot_component_by_frequency_all_phantoms(discovered, "E_mag", output_dir, max_files, coherent=False, verbose=True)

    # =========================================================================
    # COHERENT averaging: sum complex fields first, then take magnitude
    # =========================================================================
    print("\n" + "=" * 60)
    print("COHERENT AVERAGING: sum complex fields, then magnitude")
    print("=" * 60)

    print("\nGenerating Ez plots (coherent):")
    plot_component_by_frequency_all_phantoms(discovered, "Ez", output_dir, max_files, coherent=True, verbose=True)

    print("\nGenerating E_mag plots (coherent):")
    plot_component_by_frequency_all_phantoms(discovered, "E_mag", output_dir, max_files, coherent=True, verbose=True)

    print(f"\nAll plots saved to {output_dir}")
    print("\nSummary of generated files:")
    print("  Incoherent (|E| then average):")
    print("    - Ez_xy/xz/yz_all_phantoms_by_freq_incoherent.png")
    print("    - E_mag_xy/xz/yz_all_phantoms_by_freq_incoherent.png")
    print("  Coherent (sum complex, then |·|):")
    print("    - Ez_xy/xz/yz_all_phantoms_by_freq_coherent.png")
    print("    - E_mag_xy/xz/yz_all_phantoms_by_freq_coherent.png")


if __name__ == "__main__":
    main()
