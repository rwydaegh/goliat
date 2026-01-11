# Skin Mesh vs Voxel Approach for Air-Based Focus Search

**Date**: January 2026  
**Context**: Evaluating whether the STL skin mesh from `skin_mesh_pipeline` could speed up or improve the auto-induced air-based focus search.

## Conclusion: Voxel-based approach is preferred

The STL mesh (~1 MB per phantom) does **not add significant value** for the air-based focus search.

## Reasoning

### What we need:
1. Find valid air focus points (air voxels near skin)
2. Sample ~100 air points randomly
3. For each sample: compute hotspot score = mean(|E_combined|²) over skin voxels in a cube

### Why voxel-based works better:

| Aspect | Voxel Approach | Mesh Approach |
|--------|----------------|---------------|
| **Speed** | Fast (scipy binary_dilation, seconds) | Would require mesh loading + distance queries |
| **Coordinate system** | Same as E-field data (`_Output.h5`) | Would need to map mesh coords back to voxel indices |
| **Complexity** | Simple boolean operations | Additional mesh processing code |
| **Accuracy** | Exact match to simulation grid | Interpolation/snapping required |

### Where mesh WOULD be useful:
- Visualization of results
- 3D printing
- Generating sample points at exact offset from skin surface (along normals)
- Geometric queries (ray casting, surface distance)

### Decision:
Continue with **binary dilation of skin mask** to find air voxels near skin. This is:
- Already fast
- Consistent with the field grid
- Simpler to implement and maintain

The STL mesh remains available for other use cases but is not needed for focus point search.
