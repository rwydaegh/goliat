#!/usr/bin/env python3
"""
Compute projected cross-sectional area of an STL mesh for any viewing direction.

Directions can be specified as:
- Orthogonal: "x_pos", "x_neg", "y_pos", "y_neg", "z_pos", "z_neg"
- Spherical: "theta_phi" format (e.g., "45_90" means θ=45°, φ=90°)

Usage:
    python compute_cross_section.py <stl_file> [directions...]

Examples:
    python compute_cross_section.py mesh.stl x_pos y_neg 45_90
    python compute_cross_section.py mesh.stl  # Uses all orthogonal directions
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Union

import numpy as np
import trimesh
from scipy.spatial import ConvexHull


def direction_to_vector(direction: str) -> np.ndarray:
    """
    Convert a direction string to a unit vector.

    Args:
        direction: Either an orthogonal direction ("x_pos", "x_neg", etc.)
                   or spherical coordinates "theta_phi" (e.g., "45_90")

    Returns:
        Unit vector as numpy array of shape (3,)
    """
    # Orthogonal directions mapping
    orthogonal_map = {
        "x_pos": np.array([1.0, 0.0, 0.0]),
        "x_neg": np.array([-1.0, 0.0, 0.0]),
        "y_pos": np.array([0.0, 1.0, 0.0]),
        "y_neg": np.array([0.0, -1.0, 0.0]),
        "z_pos": np.array([0.0, 0.0, 1.0]),
        "z_neg": np.array([0.0, 0.0, -1.0]),
    }

    if direction in orthogonal_map:
        return orthogonal_map[direction]

    # Try to parse as spherical coordinates (theta_phi format)
    try:
        parts = direction.split("_")
        if len(parts) == 2:
            theta_deg = float(parts[0])
            phi_deg = float(parts[1])

            # Convert to radians
            theta = np.radians(theta_deg)
            phi = np.radians(phi_deg)

            # Spherical to Cartesian conversion
            # theta: polar angle from z-axis (0° = +z, 90° = xy-plane)
            # phi: azimuthal angle from x-axis in xy-plane
            x = np.sin(theta) * np.cos(phi)
            y = np.sin(theta) * np.sin(phi)
            z = np.cos(theta)

            return np.array([x, y, z])
    except (ValueError, IndexError):
        pass

    raise ValueError(
        f"Invalid direction '{direction}'. Use orthogonal (x_pos, x_neg, y_pos, y_neg, z_pos, z_neg) or spherical (theta_phi, e.g., 45_90)."
    )


def create_perpendicular_basis(view_direction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Create two orthonormal basis vectors perpendicular to the view direction.

    Args:
        view_direction: Unit vector defining the viewing direction

    Returns:
        Tuple of two orthonormal vectors (u, v) perpendicular to view_direction
    """
    # Normalize the view direction (should already be normalized, but ensure)
    n = view_direction / np.linalg.norm(view_direction)

    # Choose a reference vector not parallel to n
    if abs(n[0]) < 0.9:
        ref = np.array([1.0, 0.0, 0.0])
    else:
        ref = np.array([0.0, 1.0, 0.0])

    # Create first perpendicular vector using cross product
    u = np.cross(n, ref)
    u = u / np.linalg.norm(u)

    # Create second perpendicular vector
    v = np.cross(n, u)
    v = v / np.linalg.norm(v)

    return u, v


def compute_projected_area(mesh: trimesh.Trimesh, view_direction: np.ndarray) -> float:
    """
    Compute the projected cross-sectional area of a mesh for a given viewing direction.

    The method projects all mesh vertices onto a plane perpendicular to the view
    direction, then computes the convex hull area of the projected points.

    Args:
        mesh: A trimesh Trimesh object
        view_direction: Unit vector defining the viewing direction

    Returns:
        Projected area in the same units as the mesh (squared)
    """
    # Get the perpendicular plane basis vectors
    u, v = create_perpendicular_basis(view_direction)

    # Get all vertices from the mesh
    vertices = mesh.vertices

    # Project vertices onto the 2D plane
    # For each vertex, compute its 2D coordinates in the (u, v) basis
    projected_2d = np.column_stack([np.dot(vertices, u), np.dot(vertices, v)])

    # Compute the convex hull of the projected points
    try:
        hull = ConvexHull(projected_2d)
        area = hull.volume  # In 2D, ConvexHull.volume gives the area
    except Exception as e:
        # Handle degenerate cases (e.g., all points collinear)
        print(f"Warning: Could not compute convex hull: {e}")
        area = 0.0

    return area


def compute_cross_sections(stl_path: Union[str, Path], directions: list[str] | None = None) -> dict[str, float]:
    """
    Compute projected cross-sectional areas for multiple viewing directions.

    Args:
        stl_path: Path to the STL file
        directions: List of direction strings. If None, uses all orthogonal directions.

    Returns:
        Dictionary mapping direction names to areas in m²
    """
    stl_path = Path(stl_path)

    if not stl_path.exists():
        raise FileNotFoundError(f"STL file not found: {stl_path}")

    # Default to all orthogonal directions
    if directions is None:
        directions = ["x_pos", "x_neg", "y_pos", "y_neg", "z_pos", "z_neg"]

    # Load the mesh
    print(f"Loading mesh from: {stl_path}")
    mesh = trimesh.load(stl_path)

    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"Expected a single mesh, got {type(mesh)}")

    print(f"Mesh loaded: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")

    # Determine units - assume mm if not specified, convert to m
    # STL files from medical imaging are typically in mm
    # Check the bounding box to estimate units
    bbox = mesh.bounding_box.extents
    max_extent = max(bbox)

    # If max extent > 10, assume mm (human body scale)
    if max_extent > 10:
        scale_factor = 1e-6  # mm² to m²
        unit_assumption = "mm"
    else:
        scale_factor = 1.0  # Already in m²
        unit_assumption = "m"

    print(f"Bounding box extents: {bbox}")
    print(f"Assuming mesh units: {unit_assumption} (converting areas to m²)")

    # Compute areas for each direction
    results = {}

    for direction in directions:
        print(f"\nProcessing direction: {direction}")

        try:
            view_vector = direction_to_vector(direction)
            print(f"  View vector: {view_vector}")

            area_raw = compute_projected_area(mesh, view_vector)
            area_m2 = area_raw * scale_factor

            print(f"  Projected area: {area_raw:.4f} {unit_assumption}² = {area_m2:.6f} m²")

            results[direction] = area_m2

        except ValueError as e:
            print(f"  Error: {e}")
            results[direction] = None

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Compute projected cross-sectional area of an STL mesh.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("stl_file", type=Path, help="Path to the STL file")

    parser.add_argument(
        "directions",
        nargs="*",
        default=None,
        help=(
            "Viewing directions. Orthogonal: x_pos, x_neg, y_pos, y_neg, z_pos, z_neg. "
            "Spherical: theta_phi (e.g., 45_90). Default: all orthogonal directions."
        ),
    )

    parser.add_argument("-o", "--output", type=Path, default=None, help="Output JSON file path. If not specified, prints to stdout.")

    args = parser.parse_args()

    # Use None for default directions if empty list provided
    directions = args.directions if args.directions else None

    try:
        results = compute_cross_sections(args.stl_file, directions)

        # Format output as JSON
        output_json = json.dumps(results, indent=2)

        if args.output:
            args.output.write_text(output_json)
            print(f"\nResults saved to: {args.output}")
        else:
            print("\n" + "=" * 50)
            print("RESULTS (areas in m²):")
            print("=" * 50)
            print(output_json)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
