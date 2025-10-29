# Setup Phase Analysis: Detailed Breakdown with Actual Timings

## Current State

Currently, the entire setup phase is wrapped in a single `BaseStudy.subtask("setup_simulation")`, which provides only one timing measurement for the entire process.

**From actual logs**: Total setup time = ~62s (44s for setup_simulation subtask + 18s for project saves)

---

## Actual Timing Breakdown (from real near-field log)

Based on a real `front_of_eyes_center_vertical` setup at 700MHz:

| Step | Duration | Cumulative | Notes |
|------|----------|------------|-------|
| Project creation & initialization | 0.1s | 0.1s | Fast |
| **Phantom import** | **~8s** | **8.1s** | `.sab` file import |
| Bounding boxes | <0.1s | 8.1s | Very fast |
| Antenna placement | <0.1s | 8.1s | Very fast (no CAD import!) |
| Simulation bbox | <0.1s | 8.1s | Very fast |
| Simulation entity | <0.1s | 8.1s | Very fast |
| Add point sensors | <0.1s | 8.1s | Very fast |
| **Material assignment** | **~7.5s** | **15.6s** | Database lookups + locking |
| Gridding setup | <0.1s | 15.6s | Very fast |
| Boundary conditions | <0.1s | 15.6s | Very fast |
| Source and sensors | <0.1s | 15.6s | Very fast |
| **Voxelization** | **~27s** | **42.6s** | **SLOWEST STEP** |
| **Project save #1** | **~8s** | **50.6s** | During voxelization |
| **Project save #2** | **~19s** | **69.6s** | After setup complete |

### Key Observations:

1. **Voxelization is the clear winner**: ~27s (60% of internal setup time)
2. **Project saves are expensive**: ~27s total (19s + 8s)
3. **Phantom import**: ~8s (depends on file size)
4. **Material assignment**: ~7.5s (database + file locking)
5. **Everything else**: <1s combined

---

## Recommended Subtask Breakdown with Proposed Log Messages

### For Near-Field (6 subtasks):

```
    - Load phantom...
      - Subtask 'setup_load_phantom' done in 8.0s
    
    - Configure scene (bounding boxes, antenna placement, simulation entity, point sensors)...
      - Subtask 'setup_configure_scene' done in 1.0s
    
    - Assign materials...
      - Subtask 'setup_materials' done in 7.5s
    
    - Configure solver (gridding, boundaries, source/sensors)...
      - Subtask 'setup_solver' done in 0.5s
    
    - Voxelize simulation...
      - Subtask 'setup_voxelize' done in 27.0s
    
    - Save project...
      - Subtask 'setup_save_project' done in 27.0s
```

**Total**: ~71s (includes all project operations)

### For Far-Field (6 subtasks):

```
    - Load phantom...
      - Subtask 'setup_load_phantom' done in 8.0s
    
    - Configure scene (simulation bbox, plane wave source)...
      - Subtask 'setup_configure_scene' done in 0.5s
    
    - Assign materials...
      - Subtask 'setup_materials' done in 7.5s
    
    - Configure solver (gridding, boundaries, point sensors)...
      - Subtask 'setup_solver' done in 0.5s
    
    - Voxelize simulation...
      - Subtask 'setup_voxelize' done in 27.0s
    
    - Save project...
      - Subtask 'setup_save_project' done in 27.0s
```

**Total**: ~71s (similar to near-field)

---

## Implementation Details

### Subtask Descriptions:

1. **`setup_load_phantom`** (~8s)
   - Log: `"    - Load phantom..."`
   - Checks if phantom exists, imports `.sab` if needed

2. **`setup_configure_scene`** (~1s for near-field, ~0.5s for far-field)
   - Log: 
     - Near-field: `"    - Configure scene (bounding boxes, antenna placement, simulation entity, point sensors)..."`
     - Far-field: `"    - Configure scene (simulation bbox, plane wave source)..."`
   - **Groups**: All fast scene setup operations

3. **`setup_materials`** (~7.5s)
   - Log: `"    - Assign materials..."`
   - Assigns materials to phantom tissues and antenna components

4. **`setup_solver`** (~0.5s)
   - Log: `"    - Configure solver (gridding, boundaries, source/sensors)..."`
   - **Groups**: All fast solver configuration operations

5. **`setup_voxelize`** (~27s) ⚠️
   - Log: `"    - Voxelize simulation..."`
   - The computational bottleneck

6. **`setup_save_project`** (~27s) ⚠️
   - Log: `"    - Save project..."`
   - The I/O bottleneck (includes both saves)

---

## Summary

**The 3 real bottlenecks:**
1. 🐌 **Voxelization**: ~27s (43% - grid compute)
2. 🐌 **Project saves**: ~27s (43% - I/O)
3. 🐌 **Phantom import**: ~8s (13% - first time only)

**Everything else** (<10s total):
- Material assignment: ~7.5s
- All other operations: <2s combined

This breakdown gives users clear visibility into what's happening during setup while keeping the subtask count manageable (6 subtasks instead of 14).