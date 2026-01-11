#!/usr/bin/env python
"""
Unified skin mesh extraction pipeline for Blender Python.

This script performs the complete workflow:
1. Extract tissue voxels from Sim4Life _Input.h5
2. Apply morphological processing (dilate-erode)
3. Generate mesh via marching cubes
4. Apply Blender modifiers (Remesh, Decimate)
5. Scale and export optimized STL

IMPORTANT: This script runs with Blender's embedded Python, NOT Sim4Life Python.
Dependencies (h5py, scipy, scikit-image, trimesh) are auto-installed on first run.

Usage:
    "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" --background --python scripts/skin_mesh_pipeline.py -- configs/skin_mesh_config.json

    # Or with command-line overrides:
    "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe" --background --python scripts/skin_mesh_pipeline.py -- configs/skin_mesh_config.json --h5-path path/to/Input.h5 --output-dir results/my_mesh
"""

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Dependency checking - these need to be installed in Blender's Python
# ---------------------------------------------------------------------------


def ensure_dependencies():
    """
    Check for required dependencies and auto-install if missing.

    Uses a custom target directory to avoid corrupted system pip metadata.
    """
    required = {
        "h5py": "h5py",
        "scipy": "scipy",
        "skimage": "scikit-image",
        "trimesh": "trimesh",
    }

    # First, add custom package directory to path if it exists
    custom_packages = Path.home() / ".blender_packages"
    if custom_packages.exists():
        sys.path.insert(0, str(custom_packages))

    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if not missing:
        return  # All dependencies available

    print(f"\n{'=' * 60}")
    print(f"Installing missing dependencies: {', '.join(missing)}")
    print(f"{'=' * 60}")

    import subprocess

    # Install to custom target directory to bypass corrupted system pip
    custom_packages.mkdir(parents=True, exist_ok=True)

    install_cmd = [sys.executable, "-m", "pip", "install", "--target", str(custom_packages), "--upgrade", *missing]

    print(f"Installing to: {custom_packages}")

    try:
        result = subprocess.run(
            install_cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes for large packages like scipy
        )

        if result.returncode == 0:
            # Add to path for immediate use
            sys.path.insert(0, str(custom_packages))
            print("Dependencies installed successfully!")
            print("=" * 60 + "\n")
            return
        else:
            print(f"pip output: {result.stderr[:500]}")
            raise subprocess.CalledProcessError(result.returncode, install_cmd)

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"Installation failed: {e}")

        # Try alternative: use Python's http to download and extract wheels directly
        print("\nAttempting alternative installation via wheel download...")
        try:
            install_via_wheel_download(missing, custom_packages)
            sys.path.insert(0, str(custom_packages))
            print("Dependencies installed successfully (via wheel download)!")
            print("=" * 60 + "\n")
            return
        except Exception as wheel_error:
            print(f"Wheel download also failed: {wheel_error}")

    # All methods failed
    print("\nERROR: Failed to install dependencies")
    print("Your Blender pip installation may be corrupted.")
    print("\nManual workaround:")
    print("1. Use a different Python (e.g., system Python) to install packages:")
    print(f'   python -m pip install --target "{custom_packages}" {" ".join(missing)}')
    print("2. Re-run this script")
    sys.exit(1)


def install_via_wheel_download(packages: list, target_dir: Path):
    """
    Alternative installer that downloads wheels directly using urllib.
    This bypasses pip entirely when pip is broken.
    """
    import urllib.request
    import zipfile
    import tempfile

    # PyPI JSON API URLs for each package
    pypi_api = "https://pypi.org/pypi/{}/json"

    for package in packages:
        print(f"  Downloading {package}...")

        # Get package info from PyPI
        with urllib.request.urlopen(pypi_api.format(package)) as response:
            import json

            data = json.loads(response.read())

        # Find compatible wheel
        python_version = f"cp{sys.version_info.major}{sys.version_info.minor}"
        wheel_url = None

        for url_info in data["urls"]:
            filename = url_info["filename"]
            if filename.endswith(".whl"):
                # Check python version and platform compatibility
                if python_version in filename or "py3" in filename:
                    if "win" in filename.lower() or "any" in filename.lower():
                        wheel_url = url_info["url"]
                        break

        if not wheel_url:
            raise ValueError(f"No compatible wheel found for {package}")

        # Download and extract wheel
        with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as tmp:
            urllib.request.urlretrieve(wheel_url, tmp.name)

            with zipfile.ZipFile(tmp.name, "r") as zf:
                zf.extractall(target_dir)

            Path(tmp.name).unlink()

        print(f"  Installed {package}")


# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    with open(config_path, "r") as f:
        config = json.load(f)
    return config


def get_nested(d: Dict, *keys, default=None):
    """Get nested dictionary value with default."""
    for key in keys:
        if isinstance(d, dict) and key in d:
            d = d[key]
        else:
            return default
    return d


# ---------------------------------------------------------------------------
# Step 1: Voxel extraction from H5 (adapted from skin_voxel_utils.py)
# ---------------------------------------------------------------------------


def extract_tissue_voxels(
    input_h5_path: str,
    tissue_keywords: list[str],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
    """
    Extract tissue voxel mask and grid axes from a Sim4Life _Input.h5 file.

    Returns:
        Tuple of (tissue_mask, axis_x, axis_y, axis_z, tissue_map)
    """
    import h5py

    def build_uuid_material_map(f) -> Dict[str, str]:
        """Build mapping from UUID string to material name."""
        uuid_to_name = {}

        def visitor(name: str, obj):
            if hasattr(obj, "attrs") and "material_name" in obj.attrs:
                mat_name = obj.attrs["material_name"]
                if isinstance(mat_name, bytes):
                    mat_name = mat_name.decode("utf-8")
                parts = name.split("/")
                if len(parts) >= 3:
                    uuid_str = parts[2]
                    uuid_to_name[uuid_str] = mat_name

        f.visititems(visitor)
        return uuid_to_name

    def build_voxel_id_map(id_map: np.ndarray, uuid_to_name: Dict[str, str]) -> Dict[int, str]:
        """Map voxel IDs to tissue names via UUID lookup."""
        voxel_id_to_name = {}
        for i in range(len(id_map)):
            h = "".join(f"{b:02x}" for b in id_map[i])
            uuid_str = f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"
            if uuid_str in uuid_to_name:
                voxel_id_to_name[i] = uuid_to_name[uuid_str]
        return voxel_id_to_name

    with h5py.File(input_h5_path, "r") as f:
        uuid_to_name = build_uuid_material_map(f)

        for mesh_key in f["Meshes"].keys():
            mesh = f[f"Meshes/{mesh_key}"]
            if "voxels" not in mesh:
                continue

            voxels = mesh["voxels"][:]
            id_map = mesh["id_map"][:]
            axis_x = mesh["axis_x"][:]
            axis_y = mesh["axis_y"][:]
            axis_z = mesh["axis_z"][:]

            voxel_id_to_name = build_voxel_id_map(id_map, uuid_to_name)

            # Find matching tissue IDs
            tissue_ids = []
            for voxel_id, name in voxel_id_to_name.items():
                name_lower = name.lower()
                if any(kw.lower() in name_lower for kw in tissue_keywords):
                    tissue_ids.append(voxel_id)

            tissue_mask = np.isin(voxels, tissue_ids)
            return tissue_mask, axis_x, axis_y, axis_z, voxel_id_to_name

    raise ValueError(f"No mesh with voxel data found in {input_h5_path}")


# ---------------------------------------------------------------------------
# Step 2: Morphological processing
# ---------------------------------------------------------------------------


def dilate_erode_process(
    mask: np.ndarray,
    dilate_iterations: int = 2,
    erode_iterations: int = 1,
) -> np.ndarray:
    """Apply dilate-erode morphological processing to connect thin regions."""
    from scipy import ndimage

    # 18-connectivity structuring element
    struct = ndimage.generate_binary_structure(3, 2)

    dilated = ndimage.binary_dilation(mask, structure=struct, iterations=dilate_iterations)

    if erode_iterations > 0:
        processed = ndimage.binary_erosion(dilated, structure=struct, iterations=erode_iterations)
    else:
        processed = dilated

    return processed


def apply_gaussian_smoothing(mask: np.ndarray, sigma: float = 0.8) -> np.ndarray:
    """Apply Gaussian smoothing for smoother mesh surfaces."""
    from scipy import ndimage

    return ndimage.gaussian_filter(mask.astype(np.float32), sigma=sigma)


# ---------------------------------------------------------------------------
# Step 3: Marching cubes mesh generation
# ---------------------------------------------------------------------------


def voxels_to_mesh(
    mask: np.ndarray,
    axis_x: np.ndarray,
    axis_y: np.ndarray,
    axis_z: np.ndarray,
    smooth_sigma: float = 0.8,
) -> Tuple[np.ndarray, np.ndarray]:
    """Convert voxel mask to mesh using marching cubes."""
    from skimage import measure

    dx = np.mean(np.diff(axis_x))
    dy = np.mean(np.diff(axis_y))
    dz = np.mean(np.diff(axis_z))
    spacing = (dx, dy, dz)

    if smooth_sigma > 0:
        volume = apply_gaussian_smoothing(mask, sigma=smooth_sigma)
    else:
        volume = mask.astype(np.float32)

    verts, faces, normals, values = measure.marching_cubes(volume, level=0.5, spacing=spacing)

    origin = np.array([axis_x[0], axis_y[0], axis_z[0]])
    verts_world = verts + origin

    return verts_world, faces


def process_mesh_trimesh(
    verts: np.ndarray,
    faces: np.ndarray,
    min_component_fraction: float = 0.001,
    fill_holes: bool = True,
):
    """Process mesh with trimesh: filter components, fill holes."""
    import trimesh

    mesh = trimesh.Trimesh(vertices=verts, faces=faces)

    components = mesh.split(only_watertight=False)

    if len(components) > 1 and min_component_fraction > 0:
        min_faces = len(mesh.faces) * min_component_fraction
        large_components = [c for c in components if len(c.faces) >= min_faces]
        print(f"  Components: {len(components)} -> {len(large_components)} (threshold: {min_faces:.0f} faces)")
        if len(large_components) > 0:
            mesh = trimesh.util.concatenate(large_components)

    mesh.fix_normals()

    if fill_holes:
        try:
            initial = len(mesh.faces)
            trimesh.repair.fill_holes(mesh)
            added = len(mesh.faces) - initial
            if added > 0:
                print(f"  Filled holes: added {added} faces")
        except Exception as e:
            print(f"  Hole filling skipped: {e}")

    mesh.merge_vertices()
    mesh.remove_unreferenced_vertices()

    return mesh


# ---------------------------------------------------------------------------
# Step 4: Blender optimization
# ---------------------------------------------------------------------------


def optimize_mesh_blender(
    verts: np.ndarray,
    faces: np.ndarray,
    config: Dict[str, Any],
) -> Any:
    """Apply Blender modifiers to optimize mesh."""
    import bpy
    import bmesh

    # Create new mesh and object
    mesh_data = bpy.data.meshes.new("SkinMesh")
    obj = bpy.data.objects.new("SkinMesh", mesh_data)

    # Link to scene
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Create mesh from vertices and faces
    bm = bmesh.new()
    for v in verts:
        bm.verts.new(v)

    bm.verts.ensure_lookup_table()
    for f in faces:
        try:
            bm.faces.new([bm.verts[i] for i in f])
        except ValueError:
            pass  # Skip duplicate faces

    bm.to_mesh(mesh_data)
    bm.free()

    print(f"  Created Blender mesh: {len(mesh_data.vertices):,} vertices, {len(mesh_data.polygons):,} faces")

    blender_cfg = config.get("blender_optimization", {})

    # Remesh modifier
    remesh_cfg = blender_cfg.get("remesh", {})
    if remesh_cfg.get("enabled", True):
        remesh_mod = obj.modifiers.new(name="Remesh", type="REMESH")
        remesh_mod.mode = remesh_cfg.get("mode", "VOXEL")
        remesh_mod.voxel_size = remesh_cfg.get("voxel_size_m", 0.001)
        remesh_mod.adaptivity = remesh_cfg.get("adaptivity", 0.3)
        remesh_mod.use_smooth_shade = False
        print(f"  Remesh: mode={remesh_mod.mode}, voxel_size={remesh_mod.voxel_size * 1000:.2f}mm, adaptivity={remesh_mod.adaptivity}")

    # Decimate modifier
    decimate_cfg = blender_cfg.get("decimate", {})
    if decimate_cfg.get("enabled", True):
        decimate_mod = obj.modifiers.new(name="Decimate", type="DECIMATE")
        decimate_mod.decimate_type = decimate_cfg.get("mode", "COLLAPSE")
        decimate_mod.ratio = decimate_cfg.get("ratio", 0.3)
        print(f"  Decimate: mode={decimate_mod.decimate_type}, ratio={decimate_mod.ratio}")

    # Save .blend file BEFORE applying modifiers (for debugging)
    output_cfg = config.get("output", {})
    if output_cfg.get("save_blend_file", False):
        blend_name = output_cfg.get("blend_filename", "skin_mesh.blend")
        # Save with _unapplied suffix so user can tweak
        blend_path = Path(output_cfg.get("directory", ".")) / blend_name.replace(".blend", "_unapplied.blend")
        if not blend_path.is_absolute():
            blend_path = Path(__file__).parent.parent / blend_path
        blend_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
        print(f"  Saved .blend (modifiers NOT applied): {blend_path}")

    # Apply modifiers
    print("  Applying modifiers...")
    for mod in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)

    print(f"  After modifiers: {len(mesh_data.vertices):,} vertices, {len(mesh_data.polygons):,} faces")

    # Scale
    scale_cfg = blender_cfg.get("scale", {})
    if scale_cfg.get("enabled", True):
        factor = scale_cfg.get("factor", 1000)
        obj.scale = (factor, factor, factor)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        print(f"  Scaled by {factor}x")

    return obj


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def get_script_args():
    """Parse arguments passed after '--' in the Blender command line."""
    try:
        idx = sys.argv.index("--")
        script_args = sys.argv[idx + 1 :]
    except ValueError:
        script_args = []

    parser = argparse.ArgumentParser(
        description="Unified skin mesh extraction pipeline (runs in Blender Python)",
    )
    parser.add_argument("config", help="Path to config JSON file")
    parser.add_argument("--h5-path", help="Override: Input H5 file path")
    parser.add_argument("--output-dir", help="Override: Output directory")
    parser.add_argument("--tissue", help="Override: Tissue keyword")

    return parser.parse_args(script_args)


def main():
    # Auto-install missing dependencies (canonical Blender approach)
    ensure_dependencies()

    import bpy

    args = get_script_args()

    # Resolve config path relative to script location
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = project_root / config_path

    print(f"\n{'=' * 60}")
    print("Skin Mesh Pipeline (Blender Python)")
    print(f"{'=' * 60}")
    print(f"Config: {config_path}")

    config = load_config(config_path)

    # Resolve paths with command-line overrides
    h5_path = args.h5_path or get_nested(config, "input", "h5_path")
    h5_path = Path(h5_path)
    if not h5_path.is_absolute():
        h5_path = project_root / h5_path

    output_dir = Path(args.output_dir or get_nested(config, "output", "directory", default="results/skin_mesh"))
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    tissue_keyword = args.tissue or get_nested(config, "tissue_extraction", "tissue_keyword", default="skin")

    print(f"H5 Input: {h5_path}")
    print(f"Output dir: {output_dir}")
    print(f"Tissue: {tissue_keyword}")

    # Step 1: Extract voxels
    print(f"\n{'=' * 60}")
    print("Step 1: Extract Tissue Voxels")
    print(f"{'=' * 60}")

    tissue_mask, axis_x, axis_y, axis_z, tissue_map = extract_tissue_voxels(str(h5_path), [tissue_keyword])

    matching = [n for n in tissue_map.values() if tissue_keyword.lower() in n.lower()]
    print(f"Matched tissues: {matching}")
    print(f"Grid shape: {tissue_mask.shape}")
    print(f"Tissue voxels: {np.sum(tissue_mask):,}")

    dx = np.mean(np.diff(axis_x)) * 1000
    dy = np.mean(np.diff(axis_y)) * 1000
    dz = np.mean(np.diff(axis_z)) * 1000
    print(f"Mean voxel size: {dx:.2f} x {dy:.2f} x {dz:.2f} mm")

    # Step 2: Morphological processing
    print(f"\n{'=' * 60}")
    print("Step 2: Morphological Processing")
    print(f"{'=' * 60}")

    morph_cfg = config.get("morphological_processing", {})
    if morph_cfg.get("enabled", True):
        dilate_iter = morph_cfg.get("dilate_iterations", 2)
        erode_iter = morph_cfg.get("erode_iterations", 1)
        print(f"Dilate: {dilate_iter}, Erode: {erode_iter}")

        processed_mask = dilate_erode_process(tissue_mask, dilate_iter, erode_iter)
        print(f"Voxels after processing: {np.sum(processed_mask):,}")
    else:
        print("Skipping (disabled in config)")
        processed_mask = tissue_mask

    # Save pickle (optional)
    output_cfg = config.get("output", {})
    if output_cfg.get("save_voxel_pickle", True):
        pickle_name = output_cfg.get("pickle_filename", f"{tissue_keyword}_voxels.pkl")
        pickle_path = output_dir / pickle_name
        pickle_data = {
            "mask": processed_mask,
            "mask_original": tissue_mask,
            "axis_x": axis_x,
            "axis_y": axis_y,
            "axis_z": axis_z,
            "tissue_map": tissue_map,
            "source_file": str(h5_path),
            "config": config,
        }
        with open(pickle_path, "wb") as f:
            pickle.dump(pickle_data, f)
        print(f"Saved pickle: {pickle_path}")

    # Step 3: Marching cubes
    print(f"\n{'=' * 60}")
    print("Step 3: Marching Cubes Mesh Generation")
    print(f"{'=' * 60}")

    mc_cfg = config.get("marching_cubes", {})
    smooth_sigma = mc_cfg.get("smooth_sigma", 0.8)
    print(f"Smooth sigma: {smooth_sigma}")

    verts, faces = voxels_to_mesh(processed_mask, axis_x, axis_y, axis_z, smooth_sigma)
    print(f"Raw mesh: {len(verts):,} vertices, {len(faces):,} faces")

    # Step 4: Trimesh processing
    print(f"\n{'=' * 60}")
    print("Step 4: Trimesh Processing")
    print(f"{'=' * 60}")

    mesh_cfg = config.get("mesh_processing", {})
    trimesh_mesh = process_mesh_trimesh(
        verts,
        faces,
        min_component_fraction=mesh_cfg.get("min_component_fraction", 0.001),
        fill_holes=mesh_cfg.get("fill_holes", True),
    )
    print(f"After trimesh: {len(trimesh_mesh.vertices):,} vertices, {len(trimesh_mesh.faces):,} faces")
    print(f"Watertight: {trimesh_mesh.is_watertight}")

    # Step 5: Blender optimization
    print(f"\n{'=' * 60}")
    print("Step 5: Blender Optimization")
    print(f"{'=' * 60}")

    # Clear Blender scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    blender_cfg = config.get("blender_optimization", {})
    if blender_cfg.get("enabled", True):
        obj = optimize_mesh_blender(
            np.array(trimesh_mesh.vertices),
            np.array(trimesh_mesh.faces),
            config,
        )

        # Export from Blender
        mesh_name = output_cfg.get("mesh_filename", f"{tissue_keyword}_mesh.stl")
        stl_path = output_dir / mesh_name

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        bpy.ops.wm.stl_export(
            filepath=str(stl_path),
            export_selected_objects=True,
            ascii_format=False,
        )
    else:
        print("Blender optimization disabled, exporting via trimesh")

        # Apply scale if configured
        scale_cfg = blender_cfg.get("scale", {})
        if scale_cfg.get("enabled", True):
            factor = scale_cfg.get("factor", 1000)
            trimesh_mesh.vertices *= factor

        mesh_name = output_cfg.get("mesh_filename", f"{tissue_keyword}_mesh.stl")
        stl_path = output_dir / mesh_name
        trimesh_mesh.export(str(stl_path), file_type="stl")

    print(f"\nExported: {stl_path}")
    print(f"File size: {stl_path.stat().st_size / 1024 / 1024:.2f} MB")

    # Save .blend file for inspection if requested
    if output_cfg.get("save_blend_file", False) and blender_cfg.get("enabled", True):
        blend_name = output_cfg.get("blend_filename", "skin_mesh.blend")
        blend_path = output_dir / blend_name
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
        print(f"Saved .blend file: {blend_path}")

    # Summary
    print(f"\n{'=' * 60}")
    print("COMPLETE!")
    print(f"{'=' * 60}")
    print(f"Output directory: {output_dir}")
    print(f"  - {stl_path.name}")
    if output_cfg.get("save_voxel_pickle", True):
        print(f"  - {pickle_name}")


if __name__ == "__main__":
    main()
