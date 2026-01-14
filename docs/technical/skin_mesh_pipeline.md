# Skin Mesh Extraction Pipeline

This document describes the unified skin mesh extraction pipeline that converts Sim4Life phantom voxel data into optimized 3D meshes.

## Overview

The pipeline extracts tissue voxels from Sim4Life `_Input.h5` files and generates optimized STL meshes suitable for visualization, 3D printing, or further processing. It runs entirely in **Blender Python**.

### Workflow

1. **Extract tissue voxels** from H5 file (e.g., "Skin")
2. **Morphological processing** (dilate-erode) to connect thin tissue layers
3. **Marching cubes** mesh generation
4. **Trimesh cleanup** (component filtering, hole filling)
5. **Blender optimization** (Remesh + Decimate modifiers)
6. **Scale** (meters → millimeters) and export STL

## Prerequisites

### Blender Installation

- **Blender 4.x** (tested with 4.4): `C:\Program Files\Blender Foundation\Blender 4.4\blender.exe`

### Python Dependencies

Dependencies (`h5py`, `scipy`, `scikit-image`, `trimesh`) are **auto-installed** to `~/.blender_packages` on first run.

If auto-install fails, manually install using a working Python:
```bash
python -m pip install --target "C:/Users/<username>/.blender_packages" h5py scipy scikit-image trimesh --python-version 3.11 --platform win_amd64 --only-binary :all:
```

## Usage

### Quick Start

```bash
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python scripts/skin_mesh_pipeline.py -- configs/skin_mesh_config.json
```

### With Overrides

```bash
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python scripts/skin_mesh_pipeline.py -- configs/skin_mesh_config.json --h5-path path/to/Input.h5 --output-dir results/my_mesh --tissue skin
```

## Configuration

All parameters are specified in `configs/skin_mesh_config.json`:

```json
{
    "input": {
        "h5_path": "path/to/Input.h5"
    },
    "output": {
        "base_directory": "data/phantom_skins",
        "phantom_name": "thelonious",
        "mesh_filename": "reduced.stl",
        "save_voxel_pickle": true,
        "save_blend_file": true
    },
    "tissue_extraction": {
        "tissue_keyword": "skin"
    },
    "morphological_processing": {
        "enabled": true,
        "dilate_iterations": 2,
        "erode_iterations": 1
    },
    "marching_cubes": {
        "smooth_sigma": 0.8
    },
    "mesh_processing": {
        "min_component_fraction": 0.001,
        "fill_holes": true
    },
    "blender_optimization": {
        "enabled": true,
        "remesh": {
            "voxel_size_m": 0.001,
            "adaptivity": 0.3
        },
        "decimate": {
            "ratio": 0.3
        },
        "scale": {
            "factor": 1000
        }
    }
}
```

> **Note**: Output will be saved to `base_directory/phantom_name/` (e.g., `data/phantom_skins/thelonious/`)

## Input H5 File Requirements

The pipeline requires a Sim4Life `_Input.h5` file containing voxelized phantom data. To generate one:

1. Use a GOLIAT far-field config with `only_write_input_file: true`
2. **Use 1.0 mm gridding** for best mesh quality:

```json
{
    "gridding_parameters": {
        "global_gridding_per_frequency": {
            "450": 1.0
        }
    }
}
```

> **Important**: Finer voxel resolution (1.0 mm) produces better final meshes than coarser resolution (1.5 mm), even though it seems counterintuitive.

## Blender Optimization Details

### Remesh Modifier (Voxel Mode)

Creates uniform mesh topology from the marching cubes output.

| Setting | Default | Description |
|---------|---------|-------------|
| `voxel_size_m` | 0.001 (1mm) | Voxel resolution for remeshing |
| `adaptivity` | 0.3 | Allows larger faces in flat areas |

### Decimate Modifier (Collapse)

Reduces polygon count while preserving shape.

| Setting | Default | Description |
|---------|---------|-------------|
| `ratio` | 0.3 | Keep 30% of faces |

### Scale

Converts from Sim4Life units (meters) to millimeters.

## Output Files

| File | Description |
|------|-------------|
| `skin_mesh.stl` | Optimized mesh (~1-2 MB for skin) |
| `skin_voxels.pkl` | Voxel data for reprocessing |
| `*_unapplied.blend` | Blender file with modifiers NOT applied (for debugging) |

## Expected Results

With **1.0 mm input resolution**:

| Metric | Value |
|--------|-------|
| Raw mesh vertices | ~2M |
| Raw mesh faces | ~4.2M |
| Final mesh faces | ~26K |
| Final STL size | ~1.3 MB |

## The Thin Skin Challenge

Human skin in anatomical phantoms is typically only 1-2 mm thick. When voxelized, this creates problems:

- Skin may be only **1 voxel thick** in many places
- Small gaps appear between voxels, creating **disconnected regions**
- Marching cubes produces **thousands of small mesh components**

### Solution: Dilate-Erode-Middle

1. **Dilate** the skin voxels by N iterations (thickens the layer)
2. **Erode** back by N/2 iterations (finds the "middle" of the thickened layer)
3. **Gaussian smooth** before marching cubes (creates smooth surface)
4. **Blender Remesh** creates uniform, watertight topology

This produces a **single connected, watertight mesh** while preserving the skin's shape.

## Troubleshooting

### "ModuleNotFoundError" in Blender

The auto-install failed. Manually install packages (see Prerequisites).

### Final mesh is too large (>3 MB)

Check your input H5 file resolution. Use **1.0 mm** gridding instead of 1.5 mm.

### Mesh has holes or artifacts

- Increase `dilate_iterations` (try 3)
- Ensure `fill_holes` is enabled
- Check input H5 for tissue coverage issues

### Blender takes too long

The Remesh modifier is compute-intensive for dense meshes. Expected time: 2-5 minutes for a full phantom skin mesh.

## Files

| File | Purpose |
|------|---------|
| `scripts/skin_mesh_pipeline.py` | Main unified pipeline script |
| `configs/skin_mesh_config.json` | Default configuration |
| `configs/skin_voxel_4phantoms_1mm.json` | GOLIAT config for generating 1mm H5 files |
| `goliat/utils/skin_voxel_utils.py` | Core voxel extraction utilities |

## Change History

- **2026-01-11**: Created unified `skin_mesh_pipeline.py` replacing:
  - `extract_skin_to_mesh.py` (original dev script)
  - `voxel_tissue_to_mesh.py` (intermediate script)
  - `blender_optimize_mesh.py` (Blender-only optimization)
