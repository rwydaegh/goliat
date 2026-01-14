# Phantom Cross-Section Data

Good news! You now have access to pre-computed **projected cross-sectional area patterns** for the ViP (Virtual Population) phantoms. This data represents how the "target area" of a human body varies depending on the viewing direction — essentially an "antenna pattern" for body silhouettes.

## What This Data Represents

For each phantom, we computed the **projected cross-sectional area** (in m²) for 2592 viewing directions uniformly sampled across a sphere:
- 36 polar angles (θ from 0° to 180°)
- 72 azimuthal angles (φ from 0° to 360°)

The cross-sectional area is the **convex hull area** of all mesh vertices projected onto a plane perpendicular to the viewing direction. This tells you: "If electromagnetic waves come from this direction, how much body surface area do they 'see'?"

## Available Phantoms

| Phantom | Description | Min Area (m²) | Max Area (m²) | Ratio |
|---------|-------------|---------------|---------------|-------|
| **Duke** | Adult male, 34 years | 0.114 | 0.762 | 6.7× |
| **Ella** | Adult female, 26 years | 0.110 | 0.653 | 5.9× |
| **Eartha** | Adult female, 8 years old | 0.076 | 0.476 | 6.3× |
| **Thelonious** | Child male, 6 years old | 0.055 | 0.339 | 6.1× |

## File Structure

```
data/phantom_skins/
├── README.md                              # This file
├── duke/
│   ├── raw.stl                            # Original mesh from Sim4Life (~500 MB)
│   ├── reduced.stl                        # Optimized mesh (~2.7 MB)
│   └── cross_section_pattern.pkl          # Pre-computed cross-section data
├── eartha/
│   ├── raw.stl, reduced.stl, cross_section_pattern.pkl
├── ella/
│   ├── raw.stl, reduced.stl, cross_section_pattern.pkl
└── thelonious/
    ├── raw.stl, reduced.stl, cross_section_pattern.pkl
```

**Note**: Only `.pkl` files are tracked in git. The `.stl` files are gitignored (too large).

## How to Load the Data

```python
import json
import numpy as np

with open("data/phantom_skins/duke/cross_section_pattern.json") as f:
    data = json.load(f)

# Available keys:
# - data["theta"]      : (36, 72) list of polar angles in radians
# - data["phi"]        : (36, 72) list of azimuthal angles in radians
# - data["areas"]      : (36, 72) list of cross-sectional areas in m²
# - data["stats"]      : dict with min, max, mean, ratio
# - data["bounding_box"]: [x, y, z] extents of mesh
# - data["phantom_name"]: "duke", "ella", etc.
# - data["units"]      : "m²"

# Convert to numpy arrays for numerical operations
areas = np.array(data["areas"])
```

## Coordinate System

- **θ (theta)**: Polar angle from +Z axis (0° = top of head, 90° = horizontal, 180° = bottom)
- **φ (phi)**: Azimuthal angle from +X axis in XY plane (0° = front, 90° = left side, 180° = back)

## Use Cases

1. **Far-field exposure assessment**: Weight SAR results by the cross-sectional area for each incident direction
2. **Antenna pattern normalization**: Convert field strength to power density using the effective target area
3. **Worst-case direction finding**: Identify which viewing angles have maximum/minimum exposure area
4. **Multi-phantom comparison**: Compare body sizes across different phantoms

## Regenerating Visualizations

The PNG visualizations are not tracked in git (they're regenerable). To recreate them:

```bash
python scripts/batch_cross_section_analysis.py --force
```

Or for a single phantom:

```bash
python scripts/visualize_cross_section_pattern.py data/phantom_skins/duke/reduced.stl -o results/duke_pattern.png
```

## How This Was Computed

1. **Mesh reduction**: Raw Sim4Life phantom skin meshes (200-500 MB, 5-10M faces) were reduced using Blender's Remesh (1mm voxel) and Decimate (30% ratio) modifiers → 1-8 MB, 20-160K faces
2. **Direction sampling**: 2592 unit vectors uniformly sampling a sphere
3. **Projection**: For each direction, project all mesh vertices onto the perpendicular plane
4. **Convex hull**: Compute the 2D convex hull area of the projected points
5. **Serialization**: Store all data in a pickle file for fast reuse
