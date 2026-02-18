#!/usr/bin/env python3
"""
EMF Hotspot Analysis and Visualization Script

This script performs aggregate analysis of electromagnetic field (EMF) data from
auto-induced exposure simulations. It focuses on:
- Averaging field patterns across multiple hotspot candidates
- Comparing patterns across phantoms and frequencies
- Statistical summaries of field distributions
- Key visualizations like Ex, Ey, Ez slices through hotspot centers

Author: Generated for GOLIAT project
"""

import h5py
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Tuple, Optional, Dict, List
import json
from dataclasses import dataclass
import warnings
from collections import defaultdict
import re

# Suppress matplotlib warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Use non-interactive backend for batch processing
import matplotlib  # noqa: E402

matplotlib.use("Agg")

# Configure matplotlib for publication-quality figures
plt.rcParams.update(
    {
        "font.size": 12,
        "font.family": "serif",
        "axes.labelsize": 14,
        "axes.titlesize": 16,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 11,
        "figure.titlesize": 18,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    }
)

# Minimum domain size filter (mm) - hotspots with any dimension smaller are excluded
MIN_DOMAIN_SIZE_MM = 48.0


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class EMFData:
    """Container for electromagnetic field data from H5 file."""

    Ex: np.ndarray  # Complex phasor
    Ey: np.ndarray
    Ez: np.ndarray
    axis_x: np.ndarray  # Grid axes in meters
    axis_y: np.ndarray
    axis_z: np.ndarray

    @property
    def E_magnitude(self) -> np.ndarray:
        """Compute |E| = sqrt(|Ex|^2 + |Ey|^2 + |Ez|^2) at cell centers."""
        Ex_c = 0.5 * (self.Ex[:-1, :, :] + self.Ex[1:, :, :])
        Ey_c = 0.5 * (self.Ey[:, :-1, :] + self.Ey[:, 1:, :])
        Ez_c = 0.5 * (self.Ez[:, :, :-1] + self.Ez[:, :, 1:])

        min_shape = np.minimum.reduce([Ex_c.shape, Ey_c.shape, Ez_c.shape])
        Ex_c = Ex_c[: min_shape[0], : min_shape[1], : min_shape[2]]
        Ey_c = Ey_c[: min_shape[0], : min_shape[1], : min_shape[2]]
        Ez_c = Ez_c[: min_shape[0], : min_shape[1], : min_shape[2]]

        return np.sqrt(np.abs(Ex_c) ** 2 + np.abs(Ey_c) ** 2 + np.abs(Ez_c) ** 2)

    @property
    def grid_center_x(self) -> np.ndarray:
        return 0.5 * (self.axis_x[:-1] + self.axis_x[1:])

    @property
    def grid_center_y(self) -> np.ndarray:
        return 0.5 * (self.axis_y[:-1] + self.axis_y[1:])

    @property
    def grid_center_z(self) -> np.ndarray:
        return 0.5 * (self.axis_z[:-1] + self.axis_z[1:])

    @property
    def domain_center(self) -> Tuple[float, float, float]:
        """Return domain center in mm."""
        cx = (self.axis_x[0] + self.axis_x[-1]) / 2 * 1000
        cy = (self.axis_y[0] + self.axis_y[-1]) / 2 * 1000
        cz = (self.axis_z[0] + self.axis_z[-1]) / 2 * 1000
        return (cx, cy, cz)

    @property
    def domain_size_mm(self) -> Tuple[float, float, float]:
        """Return domain size in mm."""
        dx = (self.axis_x[-1] - self.axis_x[0]) * 1000
        dy = (self.axis_y[-1] - self.axis_y[0]) * 1000
        dz = (self.axis_z[-1] - self.axis_z[0]) * 1000
        return (dx, dy, dz)

    def passes_size_filter(self, min_size_mm: float = MIN_DOMAIN_SIZE_MM) -> bool:
        """Check if domain size passes minimum size filter.

        X dimension can be smaller than min_size_mm (it starts at lowest x and extends).
        Y and Z dimensions must be >= min_size_mm.
        """
        dx, dy, dz = self.domain_size_mm
        # X can be smaller, but Y and Z must meet minimum
        return dy >= min_size_mm and dz >= min_size_mm


@dataclass
class HotspotStats:
    """Statistics for a hotspot."""

    file_path: Path
    phantom: str
    frequency: str
    candidate_num: int
    max_Ex: float
    max_Ey: float
    max_Ez: float
    max_E_mag: float
    mean_Ex: float
    mean_Ey: float
    mean_Ez: float
    mean_E_mag: float
    hotspot_location: Tuple[float, float, float]  # x, y, z in mm
    domain_center: Tuple[float, float, float]  # mm
    domain_size: Tuple[float, float, float]  # mm


# =============================================================================
# H5 File Loading Functions
# =============================================================================


def find_field_group(h5file: h5py.File) -> str:
    """Find the FieldGroups key containing EM E(x,y,z,f0) data."""
    for key in h5file["FieldGroups"].keys():
        group = h5file["FieldGroups"][key]
        if "AllFields" in group and "EM E(x,y,z,f0)" in group["AllFields"]:
            return key
    raise ValueError("Could not find EM E(x,y,z,f0) in FieldGroups")


def find_mesh_group(h5file: h5py.File) -> str:
    """Find the Meshes key containing axis data."""
    for key in h5file["Meshes"].keys():
        mesh = h5file["Meshes"][key]
        if "axis_x" in mesh and "axis_y" in mesh and "axis_z" in mesh:
            return key
    raise ValueError("Could not find mesh with axis data")


def load_complex_field(dataset: h5py.Dataset) -> np.ndarray:
    """Load field component and convert to complex array."""
    data = dataset[:]
    return data[..., 0] + 1j * data[..., 1]


def load_emf_data(h5_path: Path) -> EMFData:
    """Load EMF data from an H5 file (E-field only for efficiency)."""
    with h5py.File(h5_path, "r") as f:
        field_key = find_field_group(f)
        mesh_key = find_mesh_group(f)

        e_base = f["FieldGroups"][field_key]["AllFields"]["EM E(x,y,z,f0)"]["_Object"]["Snapshots"]["0"]
        Ex = load_complex_field(e_base["comp0"])
        Ey = load_complex_field(e_base["comp1"])
        Ez = load_complex_field(e_base["comp2"])

        mesh = f["Meshes"][mesh_key]
        axis_x = mesh["axis_x"][:]
        axis_y = mesh["axis_y"][:]
        axis_z = mesh["axis_z"][:]

    return EMFData(Ex=Ex, Ey=Ey, Ez=Ez, axis_x=axis_x, axis_y=axis_y, axis_z=axis_z)


def extract_candidate_number(filename: str) -> int:
    """Extract candidate number from filename like 'combined_candidate1_Output.h5'."""
    match = re.search(r"candidate(\d+)", filename)
    return int(match.group(1)) if match else 0


# =============================================================================
# Discovery Functions
# =============================================================================


def discover_h5_files(base_path: Path) -> Dict[str, Dict[str, List[Path]]]:
    """Discover all H5 files organized by frequency and phantom."""
    results = {}

    for freq_dir in sorted(base_path.iterdir()):
        if freq_dir.is_dir() and "GHz" in freq_dir.name:
            freq = freq_dir.name
            results[freq] = {}

            for phantom_dir in sorted(freq_dir.iterdir()):
                if phantom_dir.is_dir():
                    phantom = phantom_dir.name
                    auto_induced_dir = phantom_dir / "auto_induced"

                    if auto_induced_dir.exists():
                        h5_files = list(auto_induced_dir.glob("combined_candidate*_Output.h5"))
                        h5_files.sort(key=lambda p: extract_candidate_number(p.name))
                        if h5_files:
                            results[freq][phantom] = h5_files

    return results


def filter_files_by_domain_size(h5_files: List[Path], min_size_mm: float = MIN_DOMAIN_SIZE_MM) -> List[Path]:
    """Filter H5 files to only include those with domain size >= min_size_mm in all dimensions."""
    valid_files = []
    for h5_file in h5_files:
        try:
            data = load_emf_data(h5_file)
            if data.passes_size_filter(min_size_mm):
                valid_files.append(h5_file)
        except Exception:
            pass
    return valid_files


# =============================================================================
# Analysis Functions
# =============================================================================


def compute_hotspot_stats(h5_path: Path, phantom: str, frequency: str) -> Optional[HotspotStats]:
    """Compute statistics for a single hotspot file. Returns None if domain too small."""
    data = load_emf_data(h5_path)

    # Check domain size filter
    if not data.passes_size_filter():
        return None

    Ex_mag = np.abs(data.Ex)
    Ey_mag = np.abs(data.Ey)
    Ez_mag = np.abs(data.Ez)
    E_mag = data.E_magnitude

    # Find hotspot location (max |E|)
    hotspot_idx = np.unravel_index(np.argmax(E_mag), E_mag.shape)

    x_mm = data.grid_center_x[min(hotspot_idx[0], len(data.grid_center_x) - 1)] * 1000
    y_mm = data.grid_center_y[min(hotspot_idx[1], len(data.grid_center_y) - 1)] * 1000
    z_mm = data.grid_center_z[min(hotspot_idx[2], len(data.grid_center_z) - 1)] * 1000

    return HotspotStats(
        file_path=h5_path,
        phantom=phantom,
        frequency=frequency,
        candidate_num=extract_candidate_number(h5_path.name),
        max_Ex=float(np.max(Ex_mag)),
        max_Ey=float(np.max(Ey_mag)),
        max_Ez=float(np.max(Ez_mag)),
        max_E_mag=float(np.max(E_mag)),
        mean_Ex=float(np.mean(Ex_mag)),
        mean_Ey=float(np.mean(Ey_mag)),
        mean_Ez=float(np.mean(Ez_mag)),
        mean_E_mag=float(np.mean(E_mag)),
        hotspot_location=(x_mm, y_mm, z_mm),
        domain_center=data.domain_center,
        domain_size=data.domain_size_mm,
    )


def analyze_all_hotspots(discovered: Dict[str, Dict[str, List[Path]]], max_per_combo: int = 20, verbose: bool = True) -> List[HotspotStats]:
    """Analyze all discovered hotspots and return statistics."""
    all_stats = []
    skipped_count = 0

    for freq in sorted(discovered.keys(), key=lambda x: int(x.replace("GHz", ""))):
        for phantom in sorted(discovered[freq].keys()):
            files = discovered[freq][phantom][:max_per_combo]

            if verbose:
                print(f"Analyzing {freq}/{phantom}: {len(files)} files...")

            valid_count = 0
            for h5_file in files:
                try:
                    stats = compute_hotspot_stats(h5_file, phantom, freq)
                    if stats is not None:
                        all_stats.append(stats)
                        valid_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    print(f"  Error processing {h5_file.name}: {e}")

            if verbose and valid_count < len(files):
                print(f"    ({valid_count} passed size filter, {len(files) - valid_count} skipped)")

    if verbose and skipped_count > 0:
        print(f"\nTotal skipped due to domain size < {MIN_DOMAIN_SIZE_MM}mm: {skipped_count}")

    return all_stats


# =============================================================================
# Averaging Functions
# =============================================================================


def compute_averaged_field_slice(
    h5_files: List[Path], component: str, plane: str, target_size: int = 80, x_center_offset_mm: float = 25.0
) -> Tuple[np.ndarray, int]:
    """
    Compute averaged field slice across multiple H5 files.

    All fields are normalized to [0,1] before averaging, then resampled to a common grid.

    For X dimension: data starts at lowest X and extends as far as it goes.
    When combining, the "center" of the output grid corresponds to x_center_offset_mm
    from the lowest X value in each file.

    For Y and Z dimensions: centered normally on the domain center.

    Args:
        h5_files: List of H5 file paths
        component: 'Ex', 'Ey', 'Ez', or 'E_mag'
        plane: 'xy', 'xz', or 'yz'
        target_size: Target grid size for resampling
        x_center_offset_mm: Distance from lowest X to the "center" point (default 25mm)

    Returns:
        Tuple of (averaged_slice, count_of_valid_files)
    """
    from scipy.ndimage import zoom

    all_slices = []

    for h5_file in h5_files:
        try:
            data = load_emf_data(h5_file)

            # Check domain size filter (Y and Z must be >= 48mm, X can be smaller)
            if not data.passes_size_filter():
                continue

            # Get field
            if component == "Ex":
                field = np.abs(data.Ex)
            elif component == "Ey":
                field = np.abs(data.Ey)
            elif component == "Ez":
                field = np.abs(data.Ez)
            elif component == "E_mag":
                field = data.E_magnitude
            else:
                continue

            # Get domain info
            dx, dy, dz = data.domain_size_mm
            x_min_mm = data.axis_x[0] * 1000

            # Extract center slice based on plane
            # For planes involving X: use x_center_offset_mm from lowest X as the "center"
            # For Y and Z: use the actual center

            if plane == "xy":
                # Z is perpendicular - use center
                z_idx = field.shape[2] // 2
                slice_2d = field[:, :, z_idx]
                # First axis is X (special handling), second is Y (centered)

            elif plane == "xz":
                # Y is perpendicular - use center
                y_idx = field.shape[1] // 2
                slice_2d = field[:, y_idx, :]
                # First axis is X (special handling), second is Z (centered)

            elif plane == "yz":
                # X is perpendicular - use x_center_offset_mm from lowest X
                # Find the index corresponding to x_center_offset_mm from lowest X
                target_x_mm = x_min_mm + x_center_offset_mm
                x_coords_mm = data.axis_x * 1000
                x_idx = np.argmin(np.abs(x_coords_mm - target_x_mm))
                x_idx = min(x_idx, field.shape[0] - 1)
                slice_2d = field[x_idx, :, :]
                # Both axes are Y and Z (centered normally)
            else:
                continue

            # Normalize to [0, 1]
            max_val = np.max(slice_2d)
            if max_val > 0:
                slice_norm = slice_2d / max_val
            else:
                continue

            # Resample to target size
            zoom_factors = (target_size / slice_norm.shape[0], target_size / slice_norm.shape[1])
            slice_resampled = zoom(slice_norm, zoom_factors, order=1)

            all_slices.append(slice_resampled)

        except Exception:
            continue

    if not all_slices:
        return np.zeros((target_size, target_size)), 0

    # Average all slices
    avg_slice = np.mean(all_slices, axis=0)
    return avg_slice, len(all_slices)


# =============================================================================
# Plotting Functions
# =============================================================================


def plot_averaged_component_grid(
    discovered: Dict[str, Dict[str, List[Path]]], component: str, plane: str, output_dir: Path, max_files: int = 20, verbose: bool = True
):
    """
    Plot a grid of AVERAGED field slices for a component/plane combination.

    Each cell shows the average across all valid candidates (not just candidate 1).
    All subplots share the same colorbar range for comparability.
    """
    freq_order = sorted(discovered.keys(), key=lambda x: int(x.replace("GHz", "")))
    phantom_order = ["duke", "ella", "eartha", "thelonious"]
    phantom_order = [p for p in phantom_order if any(p in discovered[f] for f in freq_order)]

    n_freqs = len(freq_order)
    n_phantoms = len(phantom_order)

    if verbose:
        print(f"  Computing averaged {component} {plane} slices...")

    # Compute all averaged slices first
    averaged_data = {}
    global_min = float("inf")
    global_max = float("-inf")

    for phantom in phantom_order:
        for freq in freq_order:
            if phantom in discovered[freq] and discovered[freq][phantom]:
                files = discovered[freq][phantom][:max_files]
                avg_slice, count = compute_averaged_field_slice(files, component, plane)

                if count > 0:
                    averaged_data[(phantom, freq)] = (avg_slice, count)
                    global_min = min(global_min, np.nanpercentile(avg_slice, 1))
                    global_max = max(global_max, np.nanmax(avg_slice))

    if not averaged_data:
        if verbose:
            print(f"    No valid data for {component} {plane}")
        return

    # Create figure
    fig, axes = plt.subplots(n_phantoms, n_freqs, figsize=(4 * n_freqs, 4 * n_phantoms))
    if n_phantoms == 1:
        axes = axes.reshape(1, -1)
    if n_freqs == 1:
        axes = axes.reshape(-1, 1)

    last_im = None

    for i, phantom in enumerate(phantom_order):
        for j, freq in enumerate(freq_order):
            ax = axes[i, j]

            key = (phantom, freq)
            if key in averaged_data:
                avg_slice, count = averaged_data[key]

                # Use jet colormap, shared colorbar range
                im = ax.imshow(avg_slice.T, origin="lower", cmap="jet", vmin=global_min, vmax=global_max, aspect="equal")
                last_im = im
                ax.set_title(f"{freq} - {phantom.capitalize()}\n(n={count})", fontsize=10)
            else:
                ax.text(0.5, 0.5, "No valid data", ha="center", va="center", transform=ax.transAxes)
                ax.set_title(f"{freq} - {phantom.capitalize()}", fontsize=10)

            # Center axes labels (relative to center)
            ax.set_xlabel("X (centered)" if plane in ["xy", "xz"] else "Y (centered)")
            ax.set_ylabel("Y (centered)" if plane == "xy" else "Z (centered)")

            # Only show labels on edges
            if i < n_phantoms - 1:
                ax.set_xlabel("")
            if j > 0:
                ax.set_ylabel("")

    # Add shared colorbar
    if last_im is not None:
        cbar = fig.colorbar(last_im, ax=axes, orientation="vertical", fraction=0.02, pad=0.04)
        cbar.set_label(f"Normalized |{component}|")

    plane_name = {"xy": "XY (horizontal)", "xz": "XZ (sagittal)", "yz": "YZ (coronal)"}[plane]
    fig.suptitle(
        f"Averaged {component} Field - {plane_name} Center Slice\n(averaged across all candidates, domain ≥ {MIN_DOMAIN_SIZE_MM}mm)",
        fontsize=14,
        y=1.02,
    )

    plt.tight_layout()
    fig.savefig(output_dir / f"{component}_{plane}_averaged_grid.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    if verbose:
        print(f"    Saved {component}_{plane}_averaged_grid.png")


def plot_mean_vs_peak(stats: List[HotspotStats], component: str, output_dir: Path):
    """Plot mean vs peak for a specific component."""
    phantom_order = ["duke", "ella", "eartha", "thelonious"]
    colors = {"duke": "C0", "ella": "C1", "eartha": "C2", "thelonious": "C3"}

    fig, ax = plt.subplots(figsize=(10, 8))

    for phantom in phantom_order:
        phantom_stats = [s for s in stats if s.phantom == phantom]
        if not phantom_stats:
            continue

        if component == "Ex":
            means = [s.mean_Ex for s in phantom_stats]
            maxes = [s.max_Ex for s in phantom_stats]
        elif component == "Ey":
            means = [s.mean_Ey for s in phantom_stats]
            maxes = [s.max_Ey for s in phantom_stats]
        elif component == "Ez":
            means = [s.mean_Ez for s in phantom_stats]
            maxes = [s.max_Ez for s in phantom_stats]
        else:  # E_mag
            means = [s.mean_E_mag for s in phantom_stats]
            maxes = [s.max_E_mag for s in phantom_stats]

        ax.scatter(means, maxes, label=phantom.capitalize(), alpha=0.6, s=50, c=colors[phantom])

    ax.set_xlabel(f"Mean |{component}| [V/m]")
    ax.set_ylabel(f"Peak |{component}| [V/m]")
    ax.set_title(f"Mean vs Peak {component} Field\n(domain ≥ {MIN_DOMAIN_SIZE_MM}mm)")
    ax.legend()
    ax.grid(alpha=0.3)

    # Add diagonal reference line
    lims = [min(ax.get_xlim()[0], ax.get_ylim()[0]), max(ax.get_xlim()[1], ax.get_ylim()[1])]
    ax.plot([lims[0], lims[1]], [lims[0], lims[1]], "k--", alpha=0.3, linewidth=1)

    plt.tight_layout()
    fig.savefig(output_dir / f"mean_vs_peak_{component}.png", dpi=300)
    plt.close(fig)


def plot_peak_by_freq_phantom(stats: List[HotspotStats], component: str, output_dir: Path):
    """Plot peak field by frequency and phantom for a component."""
    data_by_freq = defaultdict(list)
    for s in stats:
        data_by_freq[s.frequency].append(s)

    freq_order = sorted(data_by_freq.keys(), key=lambda x: int(x.replace("GHz", "")))
    phantom_order = ["duke", "ella", "eartha", "thelonious"]

    fig, ax = plt.subplots(figsize=(12, 6))

    x = np.arange(len(freq_order))
    width = 0.2
    colors = plt.cm.Set2(np.linspace(0, 1, len(phantom_order)))

    for i, phantom in enumerate(phantom_order):
        means = []
        stds = []
        for freq in freq_order:
            phantom_freq_stats = [s for s in stats if s.phantom == phantom and s.frequency == freq]
            if phantom_freq_stats:
                if component == "Ex":
                    vals = [s.max_Ex for s in phantom_freq_stats]
                elif component == "Ey":
                    vals = [s.max_Ey for s in phantom_freq_stats]
                elif component == "Ez":
                    vals = [s.max_Ez for s in phantom_freq_stats]
                else:
                    vals = [s.max_E_mag for s in phantom_freq_stats]
                means.append(np.mean(vals))
                stds.append(np.std(vals))
            else:
                means.append(0)
                stds.append(0)

        ax.bar(x + i * width, means, width, yerr=stds, label=phantom.capitalize(), color=colors[i], capsize=3, alpha=0.8)

    ax.set_xlabel("Frequency")
    ax.set_ylabel(f"Peak |{component}| [V/m]")
    ax.set_title(f"Peak {component} Field by Frequency and Phantom\n(averaged across candidates, domain ≥ {MIN_DOMAIN_SIZE_MM}mm)")
    ax.set_xticks(x + width * (len(phantom_order) - 1) / 2)
    ax.set_xticklabels(freq_order)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    fig.savefig(output_dir / f"peak_{component}_by_freq_phantom.png", dpi=300)
    plt.close(fig)


def plot_summary_statistics(stats: List[HotspotStats], output_dir: Path, verbose: bool = True):
    """Generate all summary plots from hotspot statistics."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print("Generating summary statistics plots...")

    # Generate plots for each component
    for component in ["Ex", "Ey", "Ez", "E_mag"]:
        if verbose:
            print(f"  Plotting {component}...")
        plot_mean_vs_peak(stats, component, output_dir)
        plot_peak_by_freq_phantom(stats, component, output_dir)

    # Hotspot Z-location distribution
    data_by_phantom = defaultdict(list)
    for s in stats:
        data_by_phantom[s.phantom].append(s)

    freq_order = sorted(set(s.frequency for s in stats), key=lambda x: int(x.replace("GHz", "")))
    phantom_order = ["duke", "ella", "eartha", "thelonious"]
    phantom_order = [p for p in phantom_order if p in data_by_phantom]

    if phantom_order:
        fig, axes = plt.subplots(1, len(phantom_order), figsize=(4 * len(phantom_order), 5), sharey=True)
        if len(phantom_order) == 1:
            axes = [axes]

        for ax, phantom in zip(axes, phantom_order):
            phantom_stats = data_by_phantom[phantom]
            z_locs = [s.hotspot_location[2] for s in phantom_stats]
            freqs = [s.frequency for s in phantom_stats]

            freq_colors = {f: plt.cm.viridis(i / len(freq_order)) for i, f in enumerate(freq_order)}
            colors = [freq_colors.get(f, "gray") for f in freqs]

            ax.scatter(range(len(z_locs)), z_locs, c=colors, alpha=0.7, s=50)
            ax.set_xlabel("Candidate Index")
            ax.set_title(phantom.capitalize())
            ax.grid(alpha=0.3)

        axes[0].set_ylabel("Hotspot Z Location [mm]")
        fig.suptitle(f"Hotspot Z-Location Distribution\n(domain ≥ {MIN_DOMAIN_SIZE_MM}mm)", fontsize=14)

        sm = plt.cm.ScalarMappable(cmap="viridis", norm=plt.Normalize(0, len(freq_order) - 1))
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=axes, orientation="vertical", fraction=0.02, pad=0.04)
        cbar.set_ticks(range(len(freq_order)))
        cbar.set_ticklabels(freq_order)
        cbar.set_label("Frequency")

        plt.tight_layout()
        fig.savefig(output_dir / "hotspot_z_distribution.png", dpi=300)
        plt.close(fig)

    # Box plots for each component
    for component in ["Ex", "Ey", "Ez", "E_mag"]:
        fig, ax = plt.subplots(figsize=(12, 6))

        box_data = []
        labels = []
        for freq in freq_order:
            freq_stats = [s for s in stats if s.frequency == freq]
            if component == "Ex":
                box_data.append([s.max_Ex for s in freq_stats])
            elif component == "Ey":
                box_data.append([s.max_Ey for s in freq_stats])
            elif component == "Ez":
                box_data.append([s.max_Ez for s in freq_stats])
            else:
                box_data.append([s.max_E_mag for s in freq_stats])
            labels.append(freq)

        bp = ax.boxplot(box_data, tick_labels=labels, patch_artist=True)

        colors = plt.cm.plasma(np.linspace(0.2, 0.8, len(freq_order)))
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_xlabel("Frequency")
        ax.set_ylabel(f"Peak |{component}| [V/m]")
        ax.set_title(f"Distribution of Peak {component} Field by Frequency\n(domain ≥ {MIN_DOMAIN_SIZE_MM}mm)")
        ax.grid(axis="y", alpha=0.3)

        plt.tight_layout()
        fig.savefig(output_dir / f"boxplot_{component}_by_freq.png", dpi=300)
        plt.close(fig)

    if verbose:
        print(f"Summary plots saved to {output_dir}")


def plot_all_averaged_grids(discovered: Dict[str, Dict[str, List[Path]]], output_dir: Path, max_files: int = 20, verbose: bool = True):
    """Generate all component/plane combination grids with averaging."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print("Generating averaged slice grids...")

    components = ["Ex", "Ey", "Ez", "E_mag"]
    planes = ["xy", "xz", "yz"]

    for component in components:
        for plane in planes:
            plot_averaged_component_grid(discovered, component, plane, output_dir, max_files=max_files, verbose=verbose)

    if verbose:
        print(f"Averaged slice grids saved to {output_dir}")


def plot_ez_by_frequency_all_phantoms(
    discovered: Dict[str, Dict[str, List[Path]]], output_dir: Path, max_files: int = 20, verbose: bool = True
):
    """
    Plot Ez field averaged over ALL phantoms for each frequency.

    Creates 3 plots (xy, xz, yz planes) with 5 subplots each (one per frequency).
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    freq_order = sorted(discovered.keys(), key=lambda x: int(x.replace("GHz", "")))
    target_size = 80

    for plane in ["xy", "xz", "yz"]:
        if verbose:
            print(f"  Computing Ez {plane} averaged over all phantoms...")

        # Collect all files for each frequency (across all phantoms)
        freq_data = {}
        global_min = float("inf")
        global_max = float("-inf")

        for freq in freq_order:
            all_files = []
            for phantom in discovered[freq]:
                all_files.extend(discovered[freq][phantom][:max_files])

            if all_files:
                avg_slice, count = compute_averaged_field_slice(all_files, "Ez", plane, target_size)
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
            cbar.set_label("Normalized |Ez|")

        plane_name = {"xy": "XY (horizontal)", "xz": "XZ (sagittal)", "yz": "YZ (coronal)"}[plane]
        fig.suptitle(f"Ez Field - {plane_name} Slice\n(averaged over ALL phantoms)", fontsize=14, y=1.02)

        plt.tight_layout()
        fig.savefig(output_dir / f"Ez_{plane}_all_phantoms_by_freq.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

        if verbose:
            print(f"    Saved Ez_{plane}_all_phantoms_by_freq.png")


# =============================================================================
# Main Execution
# =============================================================================


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze and visualize EMF hotspot data with aggregate statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full analysis on auto_induced_FR3 data
  python plot_emf_hotspots.py --discover results/auto_induced_FR3

  # Analyze specific frequency
  python plot_emf_hotspots.py --discover results/auto_induced_FR3 --freq 7GHz

  # Use all candidates (not just first 5)
  python plot_emf_hotspots.py --discover results/auto_induced_FR3 --max-files 20
        """,
    )

    parser.add_argument("--discover", type=Path, required=True, help="Base directory to discover H5 files")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("plots/auto_induced/hotspot_analysis"),
        help="Output directory for plots (default: plots/auto_induced/hotspot_analysis)",
    )
    parser.add_argument("--phantom", type=str, help="Filter by phantom name")
    parser.add_argument("--freq", type=str, help="Filter by frequency (e.g., 7GHz)")
    parser.add_argument("--max-files", type=int, default=20, help="Maximum files to analyze per phantom/freq (default: 20 = all)")
    parser.add_argument("--min-domain-size", type=float, default=48.0, help="Minimum domain size in mm (default: 48.0)")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    args = parser.parse_args()

    # Set the domain size filter
    min_domain_size = args.min_domain_size

    verbose = not args.quiet
    output_dir = args.output

    if not args.discover.exists():
        print(f"Error: Directory not found: {args.discover}")
        return 1

    # Discover files
    discovered = discover_h5_files(args.discover)

    # Print summary
    if verbose:
        print("\n" + "=" * 60)
        print("DISCOVERED H5 FILES")
        print("=" * 60)
        total = 0
        for freq in sorted(discovered.keys(), key=lambda x: int(x.replace("GHz", ""))):
            print(f"\n{freq}:")
            for phantom in sorted(discovered[freq].keys()):
                n = len(discovered[freq][phantom])
                total += n
                print(f"  {phantom}: {n} files")
        print(f"\nTotal: {total} H5 files")
        print(f"Domain size filter: ≥ {min_domain_size}mm in all dimensions")
        print("=" * 60 + "\n")

    # Apply filters
    if args.freq:
        discovered = {k: v for k, v in discovered.items() if k == args.freq}
    if args.phantom:
        discovered = {freq: {p: files for p, files in phantoms.items() if p == args.phantom} for freq, phantoms in discovered.items()}

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run analysis
    if verbose:
        print("Analyzing hotspot statistics...")

    stats = analyze_all_hotspots(discovered, max_per_combo=args.max_files, verbose=verbose)

    if not stats:
        print("No data to analyze (all filtered out by domain size)!")
        return 1

    if verbose:
        print(f"\nAnalyzed {len(stats)} hotspot files (passed size filter)")

    # Generate all averaged slice grids (Ex, Ey, Ez, E_mag for xy, xz, yz planes)
    plot_all_averaged_grids(discovered, output_dir, max_files=args.max_files, verbose=verbose)

    # Generate summary statistics plots
    plot_summary_statistics(stats, output_dir, verbose)

    # Save statistics to JSON
    stats_json = []
    for s in stats:
        stats_json.append(
            {
                "file": str(s.file_path),
                "phantom": s.phantom,
                "frequency": s.frequency,
                "candidate": s.candidate_num,
                "max_Ex": s.max_Ex,
                "max_Ey": s.max_Ey,
                "max_Ez": s.max_Ez,
                "max_E_mag": s.max_E_mag,
                "mean_Ex": s.mean_Ex,
                "mean_Ey": s.mean_Ey,
                "mean_Ez": s.mean_Ez,
                "mean_E_mag": s.mean_E_mag,
                "hotspot_location_mm": s.hotspot_location,
                "domain_center_mm": s.domain_center,
                "domain_size_mm": s.domain_size,
            }
        )

    json_path = output_dir / "hotspot_statistics.json"
    with open(json_path, "w") as f:
        json.dump(stats_json, f, indent=2)

    if verbose:
        print(f"\nStatistics saved to {json_path}")
        print(f"All plots saved to {output_dir}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
