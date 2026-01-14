#!/usr/bin/env python3
"""
Batch compute cross-sectional area patterns for all available phantom skin meshes.

This script:
1. Scans data/skin_meshes/ for available phantoms with reduced.stl files
2. Computes cross-sectional area for many viewing directions
3. Generates visualization plots (PNG)
4. Saves pattern data as pickle files for later use

Usage:
    python scripts/batch_cross_section_analysis.py [--resolution N] [--force]
"""

import argparse
import pickle
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib import cm
from scipy.spatial import ConvexHull


# ============================================================================
# Constants
# ============================================================================

# Directory containing phantom skin meshes
SKIN_MESH_DIR = Path("data/phantom_skins")

# Max file size to process (bytes) - skip raw meshes
MAX_STL_SIZE_MB = 10  # Only process reduced meshes < 10 MB


# ============================================================================
# Core computation functions (from compute_cross_section.py)
# ============================================================================


def create_perpendicular_basis(view_direction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Create two orthonormal basis vectors perpendicular to the view direction."""
    n = view_direction / np.linalg.norm(view_direction)

    if abs(n[0]) < 0.9:
        ref = np.array([1.0, 0.0, 0.0])
    else:
        ref = np.array([0.0, 1.0, 0.0])

    u = np.cross(n, ref)
    u = u / np.linalg.norm(u)
    v = np.cross(n, u)
    v = v / np.linalg.norm(v)

    return u, v


def compute_projected_area(vertices: np.ndarray, view_direction: np.ndarray) -> float:
    """Compute the projected convex hull area for a given viewing direction."""
    u, v = create_perpendicular_basis(view_direction)

    projected_2d = np.column_stack([np.dot(vertices, u), np.dot(vertices, v)])

    try:
        hull = ConvexHull(projected_2d)
        return hull.volume  # In 2D, volume = area
    except Exception:
        return 0.0


def sample_sphere_directions(n_theta: int = 36, n_phi: int = 72) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate direction vectors uniformly sampling a sphere."""
    theta = np.linspace(0, np.pi, n_theta)
    phi = np.linspace(0, 2 * np.pi, n_phi)

    THETA, PHI = np.meshgrid(theta, phi, indexing="ij")

    X = np.sin(THETA) * np.cos(PHI)
    Y = np.sin(THETA) * np.sin(PHI)
    Z = np.cos(THETA)

    directions = np.stack([X, Y, Z], axis=-1)

    return THETA, PHI, directions


def compute_area_pattern(mesh: trimesh.Trimesh, n_theta: int = 36, n_phi: int = 72) -> dict:
    """
    Compute cross-sectional area pattern for all sampled directions.

    Returns a dictionary with all pattern data for serialization.
    """
    THETA, PHI, directions = sample_sphere_directions(n_theta, n_phi)

    vertices = mesh.vertices
    areas = np.zeros((n_theta, n_phi))

    total = n_theta * n_phi
    print(f"    Computing areas for {total} directions...")

    for i in range(n_theta):
        for j in range(n_phi):
            direction = directions[i, j]
            if np.linalg.norm(direction) > 0.01:
                areas[i, j] = compute_projected_area(vertices, direction)

        if (i + 1) % 12 == 0:
            print(f"      Progress: {(i + 1) * n_phi}/{total} ({100 * (i + 1) / n_theta:.0f}%)")

    # Determine unit conversion
    bbox = mesh.bounding_box.extents
    if max(bbox) > 10:  # Assume mm
        areas *= 1e-6
        units = "m²"
        input_units = "mm"
    else:
        units = "m²"
        input_units = "m"

    return {
        "theta": THETA,
        "phi": PHI,
        "areas": areas,
        "units": units,
        "input_units": input_units,
        "n_theta": n_theta,
        "n_phi": n_phi,
        "bounding_box": bbox.tolist(),
        "n_vertices": len(mesh.vertices),
        "n_faces": len(mesh.faces),
        "stats": {
            "min": float(areas.min()),
            "max": float(areas.max()),
            "mean": float(areas.mean()),
            "ratio": float(areas.max() / areas.min()) if areas.min() > 0 else float("inf"),
        },
    }


# ============================================================================
# Visualization functions (from visualize_cross_section_pattern.py)
# ============================================================================


def plot_antenna_pattern(pattern_data: dict, phantom_name: str, output_path: Path):
    """Create a 3D antenna pattern visualization."""
    THETA = pattern_data["theta"]
    PHI = pattern_data["phi"]
    areas = pattern_data["areas"]

    # Normalize areas
    areas_norm = areas / areas.max()

    # Convert to Cartesian
    R = areas_norm
    X = R * np.sin(THETA) * np.cos(PHI)
    Y = R * np.sin(THETA) * np.sin(PHI)
    Z = R * np.cos(THETA)

    # Dark theme
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(14, 6))

    # 3D surface plot
    ax1 = fig.add_subplot(121, projection="3d")
    colors = cm.inferno(areas_norm)

    ax1.plot_surface(X, Y, Z, facecolors=colors, rstride=1, cstride=1, antialiased=True, alpha=0.9, shade=True)

    ax1.plot_wireframe(X, Y, Z, color="cyan", alpha=0.1, linewidth=0.3)

    ax1.set_xlabel("X", color="white")
    ax1.set_ylabel("Y", color="white")
    ax1.set_zlabel("Z", color="white")
    ax1.set_title(f"{phantom_name.upper()} - Cross-Section Pattern", fontsize=14, color="cyan", fontweight="bold")

    # Equal aspect ratio
    max_range = np.max([X.max() - X.min(), Y.max() - Y.min(), Z.max() - Z.min()]) / 2.0
    mid_x, mid_y, mid_z = (X.max() + X.min()) / 2, (Y.max() + Y.min()) / 2, (Z.max() + Z.min()) / 2
    ax1.set_xlim(mid_x - max_range, mid_x + max_range)
    ax1.set_ylim(mid_y - max_range, mid_y + max_range)
    ax1.set_zlim(mid_z - max_range, mid_z + max_range)
    ax1.set_facecolor("black")

    # 2D polar plot
    ax2 = fig.add_subplot(122, projection="polar")
    equator_idx = THETA.shape[0] // 2
    phi_slice = PHI[equator_idx, :]
    area_slice = areas_norm[equator_idx, :]

    ax2.plot(phi_slice, area_slice, color="cyan", linewidth=2, label="Equator (θ=90°)")
    ax2.fill(phi_slice, area_slice, color="cyan", alpha=0.3)

    for theta_deg, color in [(45, "magenta"), (135, "yellow")]:
        theta_idx = int(theta_deg / 180 * (THETA.shape[0] - 1))
        if 0 <= theta_idx < THETA.shape[0]:
            ax2.plot(phi_slice, areas_norm[theta_idx, :], color=color, linewidth=1.5, linestyle="--", alpha=0.7, label=f"θ={theta_deg}°")
            ax2.fill(phi_slice, areas_norm[theta_idx, :], color=color, alpha=0.1)

    ax2.set_title("Polar Cuts", fontsize=12, color="cyan", pad=15)
    ax2.legend(loc="upper right", fontsize=8)
    ax2.set_facecolor("black")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="black", edgecolor="none")
    plt.close(fig)

    return output_path


def plot_heatmap(pattern_data: dict, phantom_name: str, output_path: Path):
    """Create a 2D heatmap visualization."""
    THETA = pattern_data["theta"]
    PHI = pattern_data["phi"]
    areas = pattern_data["areas"]

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12, 6))

    theta_deg = np.degrees(THETA[:, 0])
    phi_deg = np.degrees(PHI[0, :])

    im = ax.imshow(
        areas.T,
        extent=[theta_deg[0], theta_deg[-1], phi_deg[0], phi_deg[-1]],
        aspect="auto",
        origin="lower",
        cmap="inferno",
        interpolation="bicubic",
    )

    cbar = plt.colorbar(im, ax=ax, label=f"Projected Area ({pattern_data['units']})")
    cbar.ax.yaxis.label.set_color("white")
    cbar.ax.tick_params(colors="white")

    ax.set_xlabel("θ (polar angle) [°]", color="white")
    ax.set_ylabel("φ (azimuthal angle) [°]", color="white")
    ax.set_title(f"{phantom_name.upper()} - Cross-Section Area Map", fontsize=14, color="cyan", fontweight="bold")

    ax.axvline(x=90, color="lime", linestyle="--", alpha=0.5)

    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="black", edgecolor="none")
    plt.close(fig)

    return output_path


# ============================================================================
# Phantom discovery and processing
# ============================================================================


def discover_phantoms(base_dir: Path, max_size_mb: float = MAX_STL_SIZE_MB) -> list[dict]:
    """
    Discover available phantom meshes.

    Returns list of dicts with phantom info.
    """
    phantoms = []

    if not base_dir.exists():
        print(f"Warning: Base directory {base_dir} does not exist")
        return phantoms

    for phantom_dir in sorted(base_dir.iterdir()):
        if not phantom_dir.is_dir():
            continue

        phantom_name = phantom_dir.name

        # Look for reduced.stl first, then other STL files
        stl_candidates = [
            phantom_dir / "reduced.stl",
            phantom_dir / "skin_mesh_optimized.stl",
            phantom_dir / "skin_mesh.stl",
        ]

        for stl_path in stl_candidates:
            if stl_path.exists():
                size_mb = stl_path.stat().st_size / (1024 * 1024)

                if size_mb <= max_size_mb:
                    phantoms.append(
                        {
                            "name": phantom_name,
                            "dir": phantom_dir,
                            "stl_path": stl_path,
                            "size_mb": size_mb,
                            "stl_type": stl_path.stem,
                        }
                    )
                    break
                else:
                    print(f"  Skipping {phantom_name}/{stl_path.name}: {size_mb:.1f} MB > {max_size_mb} MB")

    return phantoms


def process_phantom(phantom: dict, resolution: int, force: bool = False) -> dict | None:
    """
    Process a single phantom mesh.

    Returns pattern data dict or None if skipped.
    """
    phantom_dir = phantom["dir"]
    phantom_name = phantom["name"]
    stl_path = phantom["stl_path"]

    # Output paths
    pickle_path = phantom_dir / "cross_section_pattern.pkl"
    pattern_png = phantom_dir / "cross_section_pattern.png"
    heatmap_png = phantom_dir / "cross_section_heatmap.png"

    # Check if already processed
    if pickle_path.exists() and not force:
        print("  Already processed (use --force to recompute)")

        # Load existing data
        with open(pickle_path, "rb") as f:
            return pickle.load(f)

    # Load mesh
    print(f"  Loading mesh: {stl_path.name} ({phantom['size_mb']:.1f} MB)")
    mesh = trimesh.load(stl_path)
    print(f"  Mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")

    # Compute pattern
    n_theta = resolution
    n_phi = resolution * 2
    pattern_data = compute_area_pattern(mesh, n_theta, n_phi)
    pattern_data["phantom_name"] = phantom_name
    pattern_data["stl_path"] = str(stl_path)

    # Print stats
    stats = pattern_data["stats"]
    print(f"  Area stats: min={stats['min']:.4f}, max={stats['max']:.4f}, " + f"ratio={stats['ratio']:.2f}")

    # Save pickle
    with open(pickle_path, "wb") as f:
        pickle.dump(pattern_data, f)
    print(f"  Saved: {pickle_path.name}")

    # Generate visualizations
    plot_antenna_pattern(pattern_data, phantom_name, pattern_png)
    print(f"  Saved: {pattern_png.name}")

    plot_heatmap(pattern_data, phantom_name, heatmap_png)
    print(f"  Saved: {heatmap_png.name}")

    return pattern_data


# ============================================================================
# Main
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Batch compute cross-sectional patterns for all phantom meshes.")
    parser.add_argument("--resolution", type=int, default=36, help="Angular resolution (number of theta samples, default: 36)")
    parser.add_argument("--force", action="store_true", help="Recompute even if results exist")
    parser.add_argument(
        "--max-size", type=float, default=MAX_STL_SIZE_MB, help=f"Maximum STL file size in MB to process (default: {MAX_STL_SIZE_MB})"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Cross-Section Pattern Batch Analysis")
    print("=" * 60)

    # Discover phantoms
    print(f"\nScanning {SKIN_MESH_DIR} for phantoms...")
    phantoms = discover_phantoms(SKIN_MESH_DIR, args.max_size)

    if not phantoms:
        print("\nNo processable phantoms found!")
        print(f"Make sure reduced.stl files exist in {SKIN_MESH_DIR}/<phantom_name>/")
        print(f"Only files < {args.max_size} MB will be processed.")
        return

    print(f"\nFound {len(phantoms)} phantom(s) to process:")
    for p in phantoms:
        print(f"  - {p['name']}: {p['stl_path'].name} ({p['size_mb']:.1f} MB)")

    # Process each phantom
    results = {}
    print()

    for phantom in phantoms:
        print(f"\n{'=' * 60}")
        print(f"Processing: {phantom['name'].upper()}")
        print(f"{'=' * 60}")

        try:
            pattern_data = process_phantom(phantom, args.resolution, args.force)
            if pattern_data:
                results[phantom["name"]] = pattern_data["stats"]
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback

            traceback.print_exc()

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")

    if results:
        # Print comparison table
        print(f"\n{'Phantom':<15} {'Min (m²)':<12} {'Max (m²)':<12} {'Mean (m²)':<12} {'Ratio':<8}")
        print("-" * 60)
        for name, stats in sorted(results.items()):
            print(f"{name:<15} {stats['min']:<12.4f} {stats['max']:<12.4f} " + f"{stats['mean']:<12.4f} {stats['ratio']:<8.2f}")

    print(f"\nProcessed {len(results)} phantom(s)")
    print(f"Results saved to {SKIN_MESH_DIR}/<phantom>/")


if __name__ == "__main__":
    main()
