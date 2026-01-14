#!/usr/bin/env python3
"""
Visualize cross-sectional area of an STL mesh as a 3D "antenna pattern".

The cross-sectional area is computed for many viewing directions and displayed
as a 3D surface where the distance from origin represents the projected area.
This creates a freakish "body silhouette pattern" visualization.
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib import cm
from scipy.spatial import ConvexHull


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
    """
    Generate direction vectors uniformly sampling a sphere.

    Returns:
        theta, phi (in radians), and direction vectors (n_theta, n_phi, 3)
    """
    theta = np.linspace(0, np.pi, n_theta)
    phi = np.linspace(0, 2 * np.pi, n_phi)

    THETA, PHI = np.meshgrid(theta, phi, indexing="ij")

    # Spherical to Cartesian
    X = np.sin(THETA) * np.cos(PHI)
    Y = np.sin(THETA) * np.sin(PHI)
    Z = np.cos(THETA)

    directions = np.stack([X, Y, Z], axis=-1)

    return THETA, PHI, directions


def compute_area_pattern(mesh: trimesh.Trimesh, n_theta: int = 36, n_phi: int = 72) -> tuple:
    """
    Compute cross-sectional area for all sampled directions.

    Returns:
        THETA, PHI, areas (all shape n_theta x n_phi)
    """
    THETA, PHI, directions = sample_sphere_directions(n_theta, n_phi)

    vertices = mesh.vertices
    areas = np.zeros((n_theta, n_phi))

    total = n_theta * n_phi
    print(f"Computing areas for {total} directions...")

    for i in range(n_theta):
        for j in range(n_phi):
            direction = directions[i, j]
            if np.linalg.norm(direction) > 0.01:  # Skip degenerate directions
                areas[i, j] = compute_projected_area(vertices, direction)

        if (i + 1) % 10 == 0:
            print(f"  Progress: {(i + 1) * n_phi}/{total} ({100 * (i + 1) / n_theta:.0f}%)")

    return THETA, PHI, areas


def plot_antenna_pattern(THETA, PHI, areas, title="Cross-Section 'Antenna Pattern'"):
    """
    Create a 3D antenna pattern visualization.
    """
    # Normalize areas to create a nice visualization
    areas_norm = areas / areas.max()

    # Convert to Cartesian for 3D plotting (radius = area)
    R = areas_norm
    X = R * np.sin(THETA) * np.cos(PHI)
    Y = R * np.sin(THETA) * np.sin(PHI)
    Z = R * np.cos(THETA)

    # Create figure with dark theme for that "freakish" look
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(14, 6))

    # 3D surface plot
    ax1 = fig.add_subplot(121, projection="3d")

    # Use a wild colormap
    colors = cm.inferno(areas_norm)

    ax1.plot_surface(
        X,
        Y,
        Z,
        facecolors=colors,
        rstride=1,
        cstride=1,
        antialiased=True,
        alpha=0.9,
        shade=True,
    )

    # Add wireframe for ghostly effect
    ax1.plot_wireframe(X, Y, Z, color="cyan", alpha=0.1, linewidth=0.3)

    ax1.set_xlabel("X", color="white")
    ax1.set_ylabel("Y", color="white")
    ax1.set_zlabel("Z", color="white")
    ax1.set_title(title, fontsize=14, color="cyan", fontweight="bold")

    # Equal aspect ratio
    max_range = np.max([X.max() - X.min(), Y.max() - Y.min(), Z.max() - Z.min()]) / 2.0
    mid_x = (X.max() + X.min()) / 2
    mid_y = (Y.max() + Y.min()) / 2
    mid_z = (Z.max() + Z.min()) / 2
    ax1.set_xlim(mid_x - max_range, mid_x + max_range)
    ax1.set_ylim(mid_y - max_range, mid_y + max_range)
    ax1.set_zlim(mid_z - max_range, mid_z + max_range)

    ax1.set_facecolor("black")

    # 2D polar plot (theta slice at equator)
    ax2 = fig.add_subplot(122, projection="polar")

    equator_idx = THETA.shape[0] // 2  # theta = 90° (equator)
    phi_slice = PHI[equator_idx, :]
    area_slice = areas_norm[equator_idx, :]

    ax2.plot(phi_slice, area_slice, color="cyan", linewidth=2, label="Equator (θ=90°)")
    ax2.fill(phi_slice, area_slice, color="cyan", alpha=0.3)

    # Add more slices
    for theta_deg, color in [(45, "magenta"), (135, "yellow")]:
        theta_idx = int(theta_deg / 180 * (THETA.shape[0] - 1))
        if 0 <= theta_idx < THETA.shape[0]:
            ax2.plot(phi_slice, areas_norm[theta_idx, :], color=color, linewidth=1.5, linestyle="--", alpha=0.7, label=f"θ={theta_deg}°")
            ax2.fill(phi_slice, areas_norm[theta_idx, :], color=color, alpha=0.1)

    ax2.set_title("Cross-Section Pattern (Polar Cuts)", fontsize=12, color="cyan", pad=15)
    ax2.legend(loc="upper right", fontsize=8)
    ax2.set_facecolor("black")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    return fig


def plot_heatmap(THETA, PHI, areas, title="Cross-Section Area Heatmap"):
    """Create a 2D heatmap of the cross-section pattern."""
    fig, ax = plt.subplots(figsize=(12, 6))

    plt.style.use("dark_background")

    # Convert to degrees for display
    theta_deg = np.degrees(THETA[:, 0])
    phi_deg = np.degrees(PHI[0, :])

    # Transpose for correct orientation
    im = ax.imshow(
        areas.T,
        extent=[theta_deg[0], theta_deg[-1], phi_deg[0], phi_deg[-1]],
        aspect="auto",
        origin="lower",
        cmap="inferno",
        interpolation="bicubic",
    )

    cbar = plt.colorbar(im, ax=ax, label="Projected Area (m²)")
    cbar.ax.yaxis.label.set_color("white")
    cbar.ax.tick_params(colors="white")

    ax.set_xlabel("θ (polar angle from Z-axis) [°]", color="white")
    ax.set_ylabel("φ (azimuthal angle from X-axis) [°]", color="white")
    ax.set_title(title, fontsize=14, color="cyan", fontweight="bold")

    # Add axis labels for directions
    ax.axvline(x=0, color="cyan", linestyle="--", alpha=0.5, label="+Z")
    ax.axvline(x=90, color="lime", linestyle="--", alpha=0.5, label="XY plane")
    ax.axvline(x=180, color="red", linestyle="--", alpha=0.5, label="-Z")

    return fig


def main():
    parser = argparse.ArgumentParser(description="Visualize cross-sectional area as an 'antenna pattern'.")

    parser.add_argument("stl_file", type=Path, help="Path to the STL file")
    parser.add_argument("--resolution", type=int, default=36, help="Angular resolution (number of theta samples)")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output image path (saves instead of displaying)")
    parser.add_argument("--no-show", action="store_true", help="Don't display the plot (useful with -o)")

    args = parser.parse_args()

    print(f"Loading mesh: {args.stl_file}")
    mesh = trimesh.load(args.stl_file)
    print(f"Mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")

    # Compute pattern
    n_theta = args.resolution
    n_phi = args.resolution * 2

    THETA, PHI, areas = compute_area_pattern(mesh, n_theta, n_phi)

    # Convert to m² if needed
    bbox = mesh.bounding_box.extents
    if max(bbox) > 10:  # Assume mm
        areas *= 1e-6
        print("Converted areas from mm² to m²")

    print("\nArea statistics:")
    print(f"  Min: {areas.min():.6f} m²")
    print(f"  Max: {areas.max():.6f} m²")
    print(f"  Mean: {areas.mean():.6f} m²")
    print(f"  Ratio (max/min): {areas.max() / areas.min():.2f}")

    # Create visualizations
    fig1 = plot_antenna_pattern(THETA, PHI, areas, title="Body Cross-Section 'Antenna Pattern'")
    fig2 = plot_heatmap(THETA, PHI, areas, title="Cross-Section Area Map (θ vs φ)")

    if args.output:
        # Save pattern plot
        pattern_path = args.output.with_stem(args.output.stem + "_pattern")
        fig1.savefig(pattern_path, dpi=150, bbox_inches="tight", facecolor="black", edgecolor="none")
        print(f"Saved pattern to: {pattern_path}")

        # Save heatmap
        heatmap_path = args.output.with_stem(args.output.stem + "_heatmap")
        fig2.savefig(heatmap_path, dpi=150, bbox_inches="tight", facecolor="black", edgecolor="none")
        print(f"Saved heatmap to: {heatmap_path}")

    if not args.no_show:
        plt.show()

    plt.close("all")


if __name__ == "__main__":
    main()
