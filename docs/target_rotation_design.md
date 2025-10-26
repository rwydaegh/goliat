# Target Rotation Feature: Design Document

## Overview

This document outlines the design and implementation strategy for adding a "target rotation" feature to GOLIAT's near-field placement system. This feature addresses the computational gridding challenge when the phone is placed in complex orientations.

## Problem Statement

### Current Situation
In the `by_cheek` scenario, the phone undergoes multiple rotations and translations:
1. **Stand-up rotation**: 90° around X-axis to orient phone upright
2. **Z-rotation for cheek alignment**: -90° around Z-axis to align with YZ plane
3. **Base rotation**: Calculated angle to align phone perpendicular to ear-mouth line
4. **Orientation twists**: Additional user-defined rotations (e.g., tilt_up, tilt_down)

The final orientation is often complex and tilted in all three axes, making orthogonal non-uniform gridding inefficient.

### Challenge
The phone model is "simple" (boxy), but when rotated arbitrarily in 3D space, it requires very fine gridding across the entire domain. Since the phone gets gridded much more densely than the phantom, this significantly increases computational cost.

## Proposed Solution

### Core Concept
Instead of gridding a rotated phone in an aligned domain, we:
1. Keep the phone in its complex rotated orientation (as originally placed)
2. Extract the **phone's rotation** `R_phone` from its final transformation
3. Apply `R_phone` to the **Grid entity** to align the computational grid with the phone

**Key Insight**: In Sim4Life, there is an entity called "Grid" that controls how the FDTD grid is constructed. The Grid entity starts at identity (0,0,0 rotation and translation). By rotating this Grid entity to match the phone's orientation, we align the computational grid with the phone's plane. This makes the phone appear axis-aligned from the grid's perspective, enabling efficient orthogonal non-uniform gridding, while keeping all other entities (phone, phantom, sensors) in their original positions.

### Mathematical Foundation

#### Rotation Composition
Transformations in 3D are represented by 4x4 homogeneous transformation matrices. When composing transformations in Sim4Life, the transformations are *pre-multiplied* onto the existing transformation:
```
T_final = T_n * T_(n-1) * ... * T_2 * T_1
```
Applied from right to left: T_1 is applied first, then T_2, etc.

#### Extracting the Phone's Rotation
After all placement transformations, the phone's final transformation matrix contains both rotation and translation. We extract the full transformation:
```
R_phone = final_transform
```

For `by_cheek` with orientation `cheek_up` (base rotation + 15° Z + 10° X):
```
R_phone = Translation(final_pos) * Rot_X(10°) * Rot_Z(15°) * Rot_Z(-90°) * Rot_X(90°) * ...
```

This represents the phone's complete orientation and position in 3D space.

#### Application Strategy
1. **Phone**: Remains in its original rotated position (no additional transformation)
   - All placement transformations have already been applied
   - The phone is in its final complex orientation
2. **Grid entity**: Gets `R_phone` applied
   - The Grid starts at identity (0,0,0 rotation and translation)
   - Applying `R_phone` rotates the Grid to match the phone's orientation
   - This aligns the computational grid with the phone's plane
   - From the grid's perspective, the phone now appears axis-aligned
3. **Other entities**: Remain unchanged
   - Phantom, sensors, and bboxes stay in their original positions
   - All relative positioning is automatically maintained

## Implementation Plan

### 1. Configuration Schema

Add to `placement_scenarios` in config:

```json
{
  "placement_scenarios": {
    "by_cheek": {
      "target_rotation": {
        "enabled": true
      }
    }
  }
}
```

**Note**: No additional configuration needed. The feature simply rotates the Grid to match the phone's orientation.

### 2. Code Changes in `placement_setup.py`

#### Step 1: Extract Phone's Transformation
After composing `final_transform` for the phone and applying it, we have the phone's complete transformation:

```python
# After all phone transformations are applied
R_phone = final_transform  # This is the phone's complete transformation
```

#### Step 2: Apply to Grid Entity Only
```python
def _apply_target_rotation(self, phone_entities, final_transform, target_rotation_config):
    """Rotate the Grid entity to align computational grid with the phone's orientation."""
    
    # Extract phone's transformation (already includes all rotations and translations)
    R_phone = final_transform
    
    # Get the Grid entity that controls FDTD gridding
    grid_entity = self._get_grid_entity()
    
    if grid_entity:
        # Apply phone's transformation to Grid
        # Grid starts at (0,0,0), so this aligns it with the phone
        grid_entity.ApplyTransform(R_phone)
        self._log("Grid entity rotated to align with phone orientation.", log_type="success")
    else:
        self._log("Warning: Grid entity not found.", log_type="warning")
```

**Note**: The phone itself is NOT modified by this feature. It remains in its original rotated position. Only the Grid is rotated.

### 3. Helper Functions Needed

#### Extract Rotation from Transform
```python
def _extract_rotation_from_transform(self, transform):
    """Extract only the rotation component from a Transform."""
    # XCoreMath.Transform has a GetRotation() method
    # If not, we need to decompose the 4x4 matrix
    # For now, assume it exists:
    return transform.GetRotation()
```


#### Get Grid Entity
```python
def _get_grid_entity(self):
    """Get the Grid entity that controls FDTD gridding in Sim4Life."""
    all_entities = self.model.AllEntities()
    
    for e in all_entities:
        if hasattr(e, "Name") and e.Name == "Grid":
            return e
    
    return None
```

## Testing Strategy

### 1. Unit Tests
- Test Euler angle conversion
- Test rotation composition and inversion
- Test entity filtering

### 2. Integration Tests
- Run a `by_cheek` simulation with target rotation enabled
- Verify phone remains in its original rotated position (not modified)
- Verify Grid entity is rotated to match phone orientation
- Verify phantom and other entities remain in original positions
- Check that the computational grid is now aligned with the phone's plane
- Verify improved gridding efficiency (fewer cells needed)
- Check that simulation results are equivalent to original setup

### 3. Validation
- Compare SAR results with/without target rotation
- Verify computational efficiency improvement
- Visual inspection of scene setup in Sim4Life

## Edge Cases and Considerations

### 1. Free-Space Mode
Target rotation should be disabled for free-space simulations (no phantom to rotate).

### 2. Multiple Placements
Currently only applicable to `by_cheek`. Could be extended to other scenarios if needed.

### 3. Existing Simulations
Feature should be opt-in via config to maintain backward compatibility.

### 4. No Phone Modification
The phone entities are **not modified** by this feature. They remain in their original rotated positions as determined by the placement logic.

### 5. Grid Entity Existence
The Grid entity must exist in the Sim4Life model for this feature to work. If not found, a warning should be logged but the simulation should continue normally with the phone in its original orientation.

### 6. Order of Operations
Simple and straightforward:
1. Complete all phone placement transformations (as usual)
2. Extract the phone's final transformation
3. Apply the same transformation to the Grid entity
4. Done - phone stays where it is, grid is now aligned

## Future Enhancements

1. **Gridding integration**: Automatically adjust gridding parameters when target rotation is active to take full advantage of the aligned grid
2. **Multi-scenario support**: Extend to `front_of_eyes`, `by_belly`, etc. if those scenarios also have complex phone rotations
3. **Rotation visualization**: Tool to visualize the Grid rotation in 3D to confirm alignment
4. **Performance metrics**: Track and report gridding efficiency improvements (cell count reduction, memory usage, etc.)

## References

- Current implementation: [`src/setups/placement_setup.py`](../src/setups/placement_setup.py:1)
- Configuration: [`configs/todays_near_field_config.json`](../configs/todays_near_field_config.json:1)
- XCoreMath API: Sim4Life documentation

---

*This design document should be reviewed and approved before implementation begins.*