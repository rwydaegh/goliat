"""Mesh slicing utilities for SAPD extraction.

Provides functions to slice 3D mesh entities to a bounding box around a center point.
Used by both SapdExtractor and AutoInducedProcessor to reduce SAPD computation time.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # s4l_v1 types would go here


def slice_entity_to_box(
    entity,
    center_mm: list[float],
    side_len_mm: float,
    model_module,
    xcoremodeling_module,
    logger: logging.Logger | None = None,
) -> tuple:
    """Slices a mesh entity to a bounding box around a center point.

    Uses 6 PlanarCut operations to create a box-shaped region of the mesh.
    This is more robust than CSG operations for complex anatomical meshes.

    Args:
        entity: The mesh entity to slice (will be modified in-place if slicing succeeds).
        center_mm: Center point in mm [x, y, z].
        side_len_mm: Side length of the bounding box in mm.
        model_module: The s4l_v1.model module (for Vec3).
        xcoremodeling_module: The XCoreModeling module (for PlanarCut, mesh repair).
        logger: Optional logger for debug output.

    Returns:
        Tuple of (sliced_entity, success_bool). If slicing fails, returns original entity.
    """
    if center_mm is None or side_len_mm is None:
        return entity, False

    try:
        half_side = side_len_mm / 2.0

        # Use 6 PlanarCut operations to cut mesh to a box
        # PlanarCut keeps the volume in the half-space along the plane normal

        # Cut -X side: keep everything with x > center_x - half_side
        entity = xcoremodeling_module.PlanarCut(
            entity,
            model_module.Vec3(center_mm[0] - half_side, center_mm[1], center_mm[2]),
            model_module.Vec3(1, 0, 0),
        )

        # Cut +X side: keep everything with x < center_x + half_side
        entity = xcoremodeling_module.PlanarCut(
            entity,
            model_module.Vec3(center_mm[0] + half_side, center_mm[1], center_mm[2]),
            model_module.Vec3(-1, 0, 0),
        )

        # Cut -Y side
        entity = xcoremodeling_module.PlanarCut(
            entity,
            model_module.Vec3(center_mm[0], center_mm[1] - half_side, center_mm[2]),
            model_module.Vec3(0, 1, 0),
        )

        # Cut +Y side
        entity = xcoremodeling_module.PlanarCut(
            entity,
            model_module.Vec3(center_mm[0], center_mm[1] + half_side, center_mm[2]),
            model_module.Vec3(0, -1, 0),
        )

        # Cut -Z side
        entity = xcoremodeling_module.PlanarCut(
            entity,
            model_module.Vec3(center_mm[0], center_mm[1], center_mm[2] - half_side),
            model_module.Vec3(0, 0, 1),
        )

        # Cut +Z side
        entity = xcoremodeling_module.PlanarCut(
            entity,
            model_module.Vec3(center_mm[0], center_mm[1], center_mm[2] + half_side),
            model_module.Vec3(0, 0, -1),
        )

        # Clean up the mesh after planar cuts
        _cleanup_mesh(entity, xcoremodeling_module, logger)

        return entity, True

    except Exception as e:
        if logger:
            logger.warning(f"Mesh slicing failed: {e}. Using unsliced entity.")
        return entity, False


def _cleanup_mesh(entity, xcoremodeling_module, logger: logging.Logger | None = None) -> None:
    """Cleans up a mesh after slicing operations.

    Applies a 3-step cleanup pipeline:
    1. RemoveBackToBackTriangles - removes duplicate/overlapping triangles
    2. RepairTriangleMesh - fills holes and fixes self-intersections
    3. RemeshTriangleMesh - regenerates mesh with uniform edge length (skipped for speed)
    """
    try:
        xcoremodeling_module.RemoveBackToBackTriangles(entity)
    except Exception as e:
        if logger:
            logger.debug(f"RemoveBackToBackTriangles skipped: {e}")

    try:
        xcoremodeling_module.RepairTriangleMesh(
            [entity],
            fill_holes=True,
            repair_intersections=True,
            min_components_size=10,  # Remove small disconnected pieces
        )
    except Exception as e:
        if logger:
            logger.debug(f"RepairTriangleMesh skipped: {e}")

    # RemeshTriangleMesh is expensive - skip for now
    # The mesh quality from PlanarCut is usually sufficient for SAPD


def voxel_idx_to_mm(voxel_idx: list[int], grid_axes: tuple) -> list[float]:
    """Converts voxel indices to mm coordinates using grid axes.

    Args:
        voxel_idx: Voxel indices [i, j, k].
        grid_axes: Tuple of (x_axis, y_axis, z_axis) arrays in mm.

    Returns:
        Center coordinates in mm [x, y, z].
    """
    x_axis, y_axis, z_axis = grid_axes
    ix, iy, iz = voxel_idx
    return [
        float(x_axis[min(ix, len(x_axis) - 1)]),
        float(y_axis[min(iy, len(y_axis) - 1)]),
        float(z_axis[min(iz, len(z_axis) - 1)]),
    ]
