"""Utilities for extracting skin voxel locations from Sim4Life _Input.h5 files.

This module enables efficient worst-case SAPD search by identifying skin voxels
(~88k) instead of processing the full phantom volume (~8M voxels).
"""

import h5py
import numpy as np
from typing import Tuple, Dict, Sequence, Optional


def extract_skin_voxels(
    input_h5_path: str,
    skin_keywords: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
    """Extract skin voxel mask and grid axes from a Sim4Life _Input.h5 file.

    Args:
        input_h5_path: Path to the _Input.h5 file.
        skin_keywords: Keywords to match skin tissues (case-insensitive).
            Defaults to ["skin"].

    Returns:
        Tuple of:
            - skin_mask: Boolean array (Nx, Ny, Nz) where True = skin voxel
            - axis_x: X-axis coordinates (Nx,)
            - axis_y: Y-axis coordinates (Ny,)
            - axis_z: Z-axis coordinates (Nz,)
            - tissue_map: Dict mapping voxel ID -> tissue name (for debugging)

    Raises:
        ValueError: If no mesh with voxel data is found.
    """
    if skin_keywords is None:
        skin_keywords = ["skin"]

    with h5py.File(input_h5_path, "r") as f:
        # Step 1: Build UUID -> material_name mapping from AllMaterialMaps
        uuid_to_name = _build_uuid_material_map(f)

        # Step 2: Find mesh with voxel data and extract
        for mesh_key in f["Meshes"].keys():
            mesh = f[f"Meshes/{mesh_key}"]
            if "voxels" not in mesh:
                continue

            voxels = mesh["voxels"][:]
            id_map = mesh["id_map"][:]
            axis_x = mesh["axis_x"][:]
            axis_y = mesh["axis_y"][:]
            axis_z = mesh["axis_z"][:]

            # Step 3: Map voxel IDs to tissue names
            voxel_id_to_name = _build_voxel_id_map(id_map, uuid_to_name)

            # Step 4: Find skin voxel IDs
            skin_ids = []
            for voxel_id, name in voxel_id_to_name.items():
                name_lower = name.lower()
                if any(kw.lower() in name_lower for kw in skin_keywords):
                    skin_ids.append(voxel_id)

            # Step 5: Create boolean mask
            skin_mask = np.isin(voxels, skin_ids)

            return skin_mask, axis_x, axis_y, axis_z, voxel_id_to_name

    raise ValueError(f"No mesh with voxel data found in {input_h5_path}")


def get_skin_voxel_coordinates(
    skin_mask: np.ndarray,
    axis_x: np.ndarray,
    axis_y: np.ndarray,
    axis_z: np.ndarray,
) -> np.ndarray:
    """Get physical coordinates of skin voxels.

    Args:
        skin_mask: Boolean mask from extract_skin_voxels.
        axis_x, axis_y, axis_z: Grid axes from extract_skin_voxels.

    Returns:
        Array of shape (N_skin_voxels, 3) with [x, y, z] coordinates in meters.
    """
    indices = np.argwhere(skin_mask)  # Shape: (N, 3) with [ix, iy, iz]

    # Convert indices to physical coordinates (voxel centers)
    # Note: axis arrays define node positions, voxel center is between nodes
    coords = np.zeros((len(indices), 3), dtype=np.float64)
    for i, (ix, iy, iz) in enumerate(indices):
        # Clamp to valid range for center calculation
        ix_clamped = min(ix, len(axis_x) - 2)
        iy_clamped = min(iy, len(axis_y) - 2)
        iz_clamped = min(iz, len(axis_z) - 2)

        coords[i, 0] = (axis_x[ix_clamped] + axis_x[ix_clamped + 1]) / 2
        coords[i, 1] = (axis_y[iy_clamped] + axis_y[iy_clamped + 1]) / 2
        coords[i, 2] = (axis_z[iz_clamped] + axis_z[iz_clamped + 1]) / 2

    return coords


def extract_air_voxels(
    input_h5_path: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
    """Extract air/background voxel mask from a Sim4Life _Input.h5 file.

    Air voxels are those whose voxel ID has no UUID mapping in AllMaterialMaps.
    This identifies external background and any unmapped regions.

    Args:
        input_h5_path: Path to the _Input.h5 file.

    Returns:
        Tuple of:
            - air_mask: Boolean array (Nx, Ny, Nz) where True = air voxel
            - axis_x: X-axis coordinates (Nx,)
            - axis_y: Y-axis coordinates (Ny,)
            - axis_z: Z-axis coordinates (Nz,)
            - tissue_map: Dict mapping voxel ID -> tissue name (for debugging)

    Raises:
        ValueError: If no mesh with voxel data is found.
    """
    with h5py.File(input_h5_path, "r") as f:
        # Step 1: Build UUID -> material_name mapping from AllMaterialMaps
        uuid_to_name = _build_uuid_material_map(f)

        # Step 2: Find mesh with voxel data and extract
        for mesh_key in f["Meshes"].keys():
            mesh = f[f"Meshes/{mesh_key}"]
            if "voxels" not in mesh:
                continue

            voxels = mesh["voxels"][:]
            id_map = mesh["id_map"][:]
            axis_x = mesh["axis_x"][:]
            axis_y = mesh["axis_y"][:]
            axis_z = mesh["axis_z"][:]

            # Step 3: Map voxel IDs to tissue names
            voxel_id_to_name = _build_voxel_id_map(id_map, uuid_to_name)

            # Step 4: Find air voxel IDs (those NOT in the mapping = unmapped)
            unique_ids = np.unique(voxels)
            air_ids = [vid for vid in unique_ids if vid not in voxel_id_to_name]

            # Step 5: Create boolean mask
            air_mask = np.isin(voxels, air_ids)

            return air_mask, axis_x, axis_y, axis_z, voxel_id_to_name

    raise ValueError(f"No mesh with voxel data found in {input_h5_path}")


def find_valid_air_focus_points(
    input_h5_path: str,
    cube_size_mm: float = 50.0,
    min_skin_volume_fraction: float = 0.05,
    skin_keywords: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Find air voxels that are valid focus point candidates (near skin).

    Uses scipy.ndimage.binary_dilation for efficient vectorized detection
    of air voxels that are within cube_size_mm of skin voxels.

    Note: This function finds air voxels that have at least ONE skin voxel
    within the cube radius (via dilation). The min_skin_volume_fraction
    parameter is accepted for API consistency but not strictly enforced here;
    actual skin fraction filtering happens implicitly during hotspot scoring
    (cubes with very little skin will have low scores).

    Args:
        input_h5_path: Path to _Input.h5.
        cube_size_mm: Size of the cube (in mm) that defines "near skin".
        min_skin_volume_fraction: Accepted for API consistency but not
            strictly enforced. See note above.
        skin_keywords: Keywords to match skin tissues (default: ["skin"]).

    Returns:
        Tuple of:
            - valid_air_indices: Array (N_valid, 3) of [ix, iy, iz] indices
            - axis_x: X-axis coordinates
            - axis_y: Y-axis coordinates
            - axis_z: Z-axis coordinates
            - skin_mask: The skin boolean mask (for reuse)

    Raises:
        ValueError: If no valid air focus points are found.
    """
    from scipy import ndimage

    # Load both masks
    air_mask, ax_x, ax_y, ax_z, _ = extract_air_voxels(input_h5_path)
    skin_mask, _, _, _, _ = extract_skin_voxels(input_h5_path, skin_keywords)

    # Get voxel spacing (meters) - assume approximately uniform
    dx = np.mean(np.diff(ax_x))
    dy = np.mean(np.diff(ax_y))
    dz = np.mean(np.diff(ax_z))

    # Cube half-width in voxels for each dimension
    cube_size_m = cube_size_mm / 1000.0
    half_nx = int(np.ceil(cube_size_m / (2 * dx)))
    half_ny = int(np.ceil(cube_size_m / (2 * dy)))
    half_nz = int(np.ceil(cube_size_m / (2 * dz)))

    # Create structuring element for dilation (rectangular box)
    # Size is (2*half + 1) in each dimension
    struct = np.ones((2 * half_nx + 1, 2 * half_ny + 1, 2 * half_nz + 1), dtype=bool)

    # Dilate skin mask - this expands it by the cube radius
    # Any voxel within struct distance of skin becomes True
    dilated_skin = ndimage.binary_dilation(skin_mask, structure=struct)

    # Valid air focus points: air AND within dilated skin region
    valid_air_mask = air_mask & dilated_skin

    # Get indices of valid air voxels
    valid_air_indices = np.argwhere(valid_air_mask)

    if len(valid_air_indices) == 0:
        raise ValueError(
            f"No valid air focus points found. Try increasing cube_size_mm "
            f"(current: {cube_size_mm}mm) or decreasing min_skin_volume_fraction "
            f"(current: {min_skin_volume_fraction})."
        )

    return valid_air_indices, ax_x, ax_y, ax_z, skin_mask


def _build_uuid_material_map(f: h5py.File) -> Dict[str, str]:
    """Build mapping from UUID string to material name."""
    uuid_to_name: Dict[str, str] = {}

    def visitor(name: str, obj):
        if hasattr(obj, "attrs") and "material_name" in obj.attrs:
            mat_name = obj.attrs["material_name"]
            if isinstance(mat_name, bytes):
                mat_name = mat_name.decode("utf-8")

            # Extract UUID from path: AllMaterialMaps/{grp}/{uuid}/Property_*/_Object
            # When using f.visititems(), path is "AllMaterialMaps/{grp}/{uuid}/..."
            parts = name.split("/")
            if len(parts) >= 3:
                uuid_str = parts[2]
                uuid_to_name[uuid_str] = mat_name

    # Visit entire file to find material_name attributes
    f.visititems(visitor)

    return uuid_to_name


def _build_voxel_id_map(id_map: np.ndarray, uuid_to_name: Dict[str, str]) -> Dict[int, str]:
    """Map voxel IDs (indices) to tissue names via UUID lookup."""
    voxel_id_to_name: Dict[int, str] = {}

    for i in range(len(id_map)):
        # Convert 16-byte array to UUID string format
        h = "".join(f"{b:02x}" for b in id_map[i])
        uuid_str = f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"

        if uuid_str in uuid_to_name:
            voxel_id_to_name[i] = uuid_to_name[uuid_str]

    return voxel_id_to_name


def print_tissue_summary(voxels: np.ndarray, tissue_map: Dict[int, str]) -> None:
    """Print summary of tissue voxel counts."""
    unique, counts = np.unique(voxels, return_counts=True)
    print("\nTissue voxel counts:")
    print("-" * 40)
    for voxel_id, count in sorted(zip(unique, counts), key=lambda x: -x[1]):
        name = tissue_map.get(voxel_id, f"Unknown (ID={voxel_id})")
        print(f"  {name:30s}: {count:>10,}")


# --- CLI for testing ---
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Extract skin voxel locations from Sim4Life _Input.h5")
    parser.add_argument("input_h5", help="Path to _Input.h5 file")
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=["skin"],
        help="Keywords to match skin tissues (default: skin)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Print tissue summary")

    args = parser.parse_args()

    try:
        skin_mask, ax_x, ax_y, ax_z, tissue_map = extract_skin_voxels(args.input_h5, args.keywords)

        n_skin = np.sum(skin_mask)
        n_total = skin_mask.size
        reduction = n_total / n_skin if n_skin > 0 else float("inf")

        print("\nSkin voxel extraction complete:")
        print(f"  Input file: {args.input_h5}")
        print(f"  Grid shape: {skin_mask.shape}")
        print(f"  Skin voxels: {n_skin:,} / {n_total:,} ({100 * n_skin / n_total:.2f}%)")
        print(f"  Reduction factor: {reduction:.1f}x")

        if args.verbose:
            # Re-open to get full voxel array for summary
            with h5py.File(args.input_h5, "r") as f:
                for mesh_key in f["Meshes"].keys():
                    if "voxels" in f[f"Meshes/{mesh_key}"]:
                        voxels = f[f"Meshes/{mesh_key}/voxels"][:]
                        print_tissue_summary(voxels, tissue_map)
                        break

        # Demo: get coordinates of first few skin voxels
        coords = get_skin_voxel_coordinates(skin_mask, ax_x, ax_y, ax_z)
        print("\nFirst 5 skin voxel coordinates (meters):")
        for i, (x, y, z) in enumerate(coords[:5]):
            print(f"  [{i}]: ({x:.4f}, {y:.4f}, {z:.4f})")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
