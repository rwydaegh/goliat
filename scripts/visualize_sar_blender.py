"""
Blender script to visualize SAR (Specific Absorption Rate) data on a 3D phantom model.

This script:
1. Imports an STL model of the Thelonious phantom
2. Creates colored cubes at peak SAR locations for each frequency
3. Uses animation frames to show different frequencies
4. Adds a 3D colorbar legend

Usage:
    "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python scripts/visualize_sar_blender.py

Or to keep Blender open for inspection:
    "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --python scripts/visualize_sar_blender.py
"""

import bpy
import json
import math
from pathlib import Path
from mathutils import Vector


# =============================================================================
# Configuration
# =============================================================================

# Get the script directory to find relative paths
SCRIPT_DIR = Path(__file__).parent.parent  # Go up from scripts/ to project root

# Paths (relative to project root)
STL_PATH = SCRIPT_DIR / "data" / "phantom_skins" / "thelonious" / "reduced.stl"
SAR_DATA_PATH = SCRIPT_DIR / "results" / "thelonious_FR3"
OUTPUT_BLEND_PATH = SCRIPT_DIR / "results" / "thelonious_FR3" / "sar_visualization.blend"

# Frequencies to visualize (in MHz)
FREQUENCIES = [7000, 9000, 11000, 13000, 15000, 26000]

# Visualization settings
PHANTOM_COLOR = (0.8, 0.75, 0.7, 0.3)  # Skin-like color with transparency
PHANTOM_ROUGHNESS = 0.5

# Colormap for SAR values (blue to red, like jet colormap)
COLORMAP = [
    (0.0, (0.0, 0.0, 0.5, 1.0)),  # Dark blue
    (0.25, (0.0, 0.5, 1.0, 1.0)),  # Light blue
    (0.5, (0.0, 1.0, 0.0, 1.0)),  # Green
    (0.75, (1.0, 1.0, 0.0, 1.0)),  # Yellow
    (1.0, (1.0, 0.0, 0.0, 1.0)),  # Red
]


# =============================================================================
# Helper Functions
# =============================================================================


def clear_scene():
    """Remove all objects from the scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    # Also clear orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


def load_sar_data():
    """Load SAR data from all frequency folders."""
    sar_data = []

    for freq in FREQUENCIES:
        freq_folder = SAR_DATA_PATH / f"{freq}MHz" / "environmental_x_neg_theta"
        sar_file = freq_folder / "sar_results.json"

        if sar_file.exists():
            with open(sar_file, "r") as f:
                data = json.load(f)

            peak_details = data.get("peak_sar_details", {})
            sar_data.append(
                {
                    "frequency_mhz": freq,
                    "frequency_ghz": freq / 1000,
                    "peak_sar": data.get("peak_sar_10g_W_kg", 0),
                    "location": peak_details.get("PeakLocation", [0, 0, 0]),
                    "cube_side": peak_details.get("PeakCubeSideLength", 0.02),
                    "whole_body_sar": data.get("whole_body_sar", 0),
                }
            )
            print(f"Loaded SAR data for {freq} MHz: peak={data.get('peak_sar_10g_W_kg', 0):.2e} W/kg")
        else:
            print(f"Warning: SAR file not found for {freq} MHz: {sar_file}")

    return sar_data


def interpolate_color(value, vmin, vmax):
    """Interpolate color from colormap based on normalized value."""
    if vmax == vmin:
        t = 0.5
    else:
        t = (value - vmin) / (vmax - vmin)
    t = max(0.0, min(1.0, t))  # Clamp to [0, 1]

    # Find the two colormap entries to interpolate between
    for i in range(len(COLORMAP) - 1):
        t1, c1 = COLORMAP[i]
        t2, c2 = COLORMAP[i + 1]
        if t1 <= t <= t2:
            # Linear interpolation
            local_t = (t - t1) / (t2 - t1)
            return tuple(c1[j] + local_t * (c2[j] - c1[j]) for j in range(4))

    return COLORMAP[-1][1]


def create_material(name, color, emission_strength=0.0):
    """Create a material with the given color."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear default nodes
    nodes.clear()

    # Create nodes
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)

    if emission_strength > 0:
        # Use emission for glowing effect
        emission = nodes.new("ShaderNodeEmission")
        emission.location = (0, 0)
        emission.inputs["Color"].default_value = color
        emission.inputs["Strength"].default_value = emission_strength
        links.new(emission.outputs["Emission"], output.inputs["Surface"])
    else:
        # Use principled BSDF
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = PHANTOM_ROUGHNESS

        # Handle transparency
        if color[3] < 1.0:
            mat.blend_method = "BLEND"
            bsdf.inputs["Alpha"].default_value = color[3]

        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    return mat


def import_stl(filepath):
    """Import an STL file and return the created object."""
    print(f"Importing STL from: {filepath}")

    # Import STL
    bpy.ops.wm.stl_import(filepath=str(filepath))

    # Get the imported object (should be the active one)
    obj = bpy.context.active_object

    if obj is None:
        # Try to find it by looking for mesh objects
        for o in bpy.context.scene.objects:
            if o.type == "MESH":
                obj = o
                break

    if obj:
        obj.name = "Thelonious_Phantom"
        print(f"Imported phantom with {len(obj.data.vertices)} vertices")

    return obj


def create_sar_cube(location, size, name, material):
    """Create a cube at the given location with the given size."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    cube = bpy.context.active_object
    cube.name = name
    cube.scale = (size, size, size)

    # Apply material
    cube.data.materials.append(material)

    return cube


def create_colorbar(sar_data, position, height=0.3, width=0.03, num_segments=20):
    """Create a 3D colorbar showing the SAR value scale."""
    # Get min/max SAR values
    sar_values = [d["peak_sar"] for d in sar_data]
    vmin, vmax = min(sar_values), max(sar_values)

    colorbar_objects = []

    # Create colorbar segments
    segment_height = height / num_segments
    for i in range(num_segments):
        # Calculate position and color
        t = i / (num_segments - 1)
        value = vmin + t * (vmax - vmin)
        color = interpolate_color(value, vmin, vmax)

        # Create segment
        z_pos = position[2] + i * segment_height
        loc = (position[0], position[1], z_pos)

        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        segment = bpy.context.active_object
        segment.name = f"Colorbar_Segment_{i}"
        segment.scale = (width, width * 0.5, segment_height * 0.5)

        # Create and apply material
        mat = create_material(f"Colorbar_Mat_{i}", color, emission_strength=0.5)
        segment.data.materials.append(mat)

        colorbar_objects.append(segment)

    # Create text labels - rotated to stand upright (facing +X direction)
    # Scale text size proportionally to colorbar size
    text_scale = height / 0.3  # Relative to default height of 0.3
    labels = [
        (vmin, position[2] - 0.02 * text_scale, f"{vmin:.2e}"),
        ((vmin + vmax) / 2, position[2] + height / 2, f"{(vmin + vmax) / 2:.2e}"),
        (vmax, position[2] + height + 0.02 * text_scale, f"{vmax:.2e}"),
    ]

    for value, z, text in labels:
        bpy.ops.object.text_add(location=(position[0] + width * 2, position[1], z))
        text_obj = bpy.context.active_object
        text_obj.data.body = text
        text_obj.data.size = 0.015 * text_scale  # Scale text size
        text_obj.name = f"Colorbar_Label_{text}"
        # Rotate text to stand upright along Z axis, facing outward (+X)
        text_obj.rotation_euler = (math.pi / 2, 0, 0)  # Rotate 90° around X to stand up
        colorbar_objects.append(text_obj)

    # Add title - also rotated to stand upright
    bpy.ops.object.text_add(location=(position[0], position[1], position[2] + height + 0.05 * text_scale))
    title = bpy.context.active_object
    title.data.body = "Peak SAR\n(W/kg)"
    title.data.size = 0.018 * text_scale  # Scale text size
    title.name = "Colorbar_Title"
    # Rotate title to stand upright along Z axis
    title.rotation_euler = (math.pi / 2, 0, 0)
    colorbar_objects.append(title)

    # Parent all colorbar objects to an empty
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=position)
    colorbar_parent = bpy.context.active_object
    colorbar_parent.name = "Colorbar"

    for obj in colorbar_objects:
        obj.parent = colorbar_parent

    return colorbar_parent


def setup_lighting():
    """Set up scene lighting."""
    # Add sun light
    bpy.ops.object.light_add(type="SUN", location=(2, -2, 3))
    sun = bpy.context.active_object
    sun.name = "Sun"
    sun.data.energy = 3

    # Add fill light
    bpy.ops.object.light_add(type="AREA", location=(-2, 2, 2))
    fill = bpy.context.active_object
    fill.name = "Fill_Light"
    fill.data.energy = 100
    fill.data.size = 2


def setup_camera(phantom_obj):
    """Set up camera to view the phantom."""
    # Get phantom bounding box
    bbox = [phantom_obj.matrix_world @ Vector(corner) for corner in phantom_obj.bound_box]
    center = sum(bbox, Vector()) / 8

    # Calculate camera distance
    max_dim = max(
        max(v.x for v in bbox) - min(v.x for v in bbox),
        max(v.y for v in bbox) - min(v.y for v in bbox),
        max(v.z for v in bbox) - min(v.z for v in bbox),
    )

    # Position camera
    cam_distance = max_dim * 2
    cam_location = (center.x + cam_distance * 0.7, center.y - cam_distance * 0.7, center.z + cam_distance * 0.3)

    bpy.ops.object.camera_add(location=cam_location)
    camera = bpy.context.active_object
    camera.name = "Camera"

    # Point camera at center
    direction = Vector(center) - Vector(cam_location)
    rot_quat = direction.to_track_quat("-Z", "Y")
    camera.rotation_euler = rot_quat.to_euler()

    # Set as active camera
    bpy.context.scene.camera = camera

    return camera


def create_frequency_label(freq_ghz, position):
    """Create a text label showing the current frequency."""
    bpy.ops.object.text_add(location=position)
    text_obj = bpy.context.active_object
    text_obj.data.body = f"{freq_ghz:.0f} GHz"
    text_obj.data.size = 0.05
    text_obj.data.align_x = "CENTER"
    text_obj.name = "Frequency_Label"

    # Rotate text to stand upright along Z axis
    text_obj.rotation_euler = (math.pi / 2, 0, 0)

    # Create material
    mat = create_material("Freq_Label_Mat", (1, 1, 1, 1))
    text_obj.data.materials.append(mat)

    return text_obj


def setup_animation(sar_cubes, freq_labels, num_frames_per_freq=30):
    """Set up animation with each frequency on separate frames."""
    scene = bpy.context.scene

    total_frames = len(FREQUENCIES) * num_frames_per_freq
    scene.frame_start = 1
    scene.frame_end = total_frames

    for i, (cube, label) in enumerate(zip(sar_cubes, freq_labels)):
        start_frame = i * num_frames_per_freq + 1
        end_frame = (i + 1) * num_frames_per_freq

        # Hide cube before its frame range
        cube.hide_viewport = True
        cube.hide_render = True
        cube.keyframe_insert(data_path="hide_viewport", frame=1)
        cube.keyframe_insert(data_path="hide_render", frame=1)

        # Show cube during its frame range
        cube.hide_viewport = False
        cube.hide_render = False
        cube.keyframe_insert(data_path="hide_viewport", frame=start_frame)
        cube.keyframe_insert(data_path="hide_render", frame=start_frame)

        # Hide cube after its frame range
        if i < len(FREQUENCIES) - 1:
            cube.hide_viewport = True
            cube.hide_render = True
            cube.keyframe_insert(data_path="hide_viewport", frame=end_frame + 1)
            cube.keyframe_insert(data_path="hide_render", frame=end_frame + 1)

        # Same for labels
        label.hide_viewport = True
        label.hide_render = True
        label.keyframe_insert(data_path="hide_viewport", frame=1)
        label.keyframe_insert(data_path="hide_render", frame=1)

        label.hide_viewport = False
        label.hide_render = False
        label.keyframe_insert(data_path="hide_viewport", frame=start_frame)
        label.keyframe_insert(data_path="hide_render", frame=start_frame)

        if i < len(FREQUENCIES) - 1:
            label.hide_viewport = True
            label.hide_render = True
            label.keyframe_insert(data_path="hide_viewport", frame=end_frame + 1)
            label.keyframe_insert(data_path="hide_render", frame=end_frame + 1)

    # Set to first frame
    scene.frame_set(1)


# =============================================================================
# Main Script
# =============================================================================


def main():
    print("=" * 60)
    print("SAR Visualization Script for Blender")
    print("=" * 60)

    # Clear existing scene
    print("\nClearing scene...")
    clear_scene()

    # Load SAR data
    print("\nLoading SAR data...")
    sar_data = load_sar_data()

    if not sar_data:
        print("ERROR: No SAR data found!")
        return

    # Get min/max for color scaling
    sar_values = [d["peak_sar"] for d in sar_data]
    vmin, vmax = min(sar_values), max(sar_values)
    print(f"SAR range: {vmin:.2e} to {vmax:.2e} W/kg")

    # Import phantom STL
    print(f"\nImporting phantom from: {STL_PATH}")
    if not STL_PATH.exists():
        print(f"ERROR: STL file not found: {STL_PATH}")
        return

    phantom = import_stl(STL_PATH)

    if phantom:
        # Apply phantom material
        phantom_mat = create_material("Phantom_Material", PHANTOM_COLOR)
        phantom.data.materials.append(phantom_mat)

        # Enable smooth shading
        bpy.ops.object.shade_smooth()

    # Create SAR cubes for each frequency
    print("\nCreating SAR visualization cubes...")
    sar_cubes = []
    freq_labels = []

    for i, data in enumerate(sar_data):
        freq = data["frequency_mhz"]
        freq_ghz = data["frequency_ghz"]
        location = data["location"]
        cube_size = data["cube_side"]
        peak_sar = data["peak_sar"]

        # Get color based on SAR value
        color = interpolate_color(peak_sar, vmin, vmax)

        # Create material with emission for visibility
        mat_name = f"SAR_Mat_{freq}MHz"
        mat = create_material(mat_name, color, emission_strength=2.0)

        # Create cube
        cube_name = f"SAR_Cube_{freq}MHz"
        cube = create_sar_cube(location, cube_size, cube_name, mat)
        sar_cubes.append(cube)

        print(
            f"  {freq_ghz:.0f} GHz: SAR={peak_sar:.2e} W/kg, "
            f"loc=({location[0]:.3f}, {location[1]:.3f}, {location[2]:.3f}), "
            f"cube_size={cube_size:.4f}m"
        )

        # Create frequency label near the cube
        label_pos = (location[0] + cube_size * 2, location[1], location[2] + cube_size)
        label = create_frequency_label(freq_ghz, label_pos)
        freq_labels.append(label)

    # Create colorbar
    print("\nCreating colorbar...")
    if phantom:
        bbox = [phantom.matrix_world @ Vector(corner) for corner in phantom.bound_box]
        # Use absolute max X to place colorbar on the positive X side of the phantom
        max_x = max(v.x for v in bbox)
        min_x = min(v.x for v in bbox)
        # Place colorbar on the side with larger absolute X, plus offset, then subtract 0.5m
        colorbar_x = max(abs(max_x), abs(min_x)) + 0.15 - 0.5
        colorbar_y = (min(v.y for v in bbox) + max(v.y for v in bbox)) / 2
        # Place colorbar at mid-height of phantom for better visibility, then add 1m
        min_z = min(v.z for v in bbox)
        max_z = max(v.z for v in bbox)
        colorbar_z = (min_z + max_z) / 2 - 0.15 + 1.0  # Start slightly below center, +1m offset
        print(
            f"  Phantom bbox: X=[{min_x:.3f}, {max_x:.3f}], Y=[{min(v.y for v in bbox):.3f}, {max(v.y for v in bbox):.3f}], Z=[{min_z:.3f}, {max_z:.3f}]"
        )
        print(f"  Colorbar position: ({colorbar_x:.3f}, {colorbar_y:.3f}, {colorbar_z:.3f})")
    else:
        colorbar_x, colorbar_y, colorbar_z = 0.3, 0, -0.5

    # Create colorbar with 2x size (height=0.6 instead of 0.3, width=0.06 instead of 0.03)
    create_colorbar(sar_data, (colorbar_x, colorbar_y, colorbar_z), height=0.6, width=0.06)

    # Set up animation
    print("\nSetting up animation...")
    setup_animation(sar_cubes, freq_labels)

    # Set up lighting
    print("\nSetting up lighting...")
    setup_lighting()

    # Set up camera
    print("\nSetting up camera...")
    if phantom:
        setup_camera(phantom)

    # Configure render settings
    print("\nConfiguring render settings...")
    bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    # Note: Bloom is now handled differently in EEVEE Next (Blender 4.x)
    # It's controlled via compositor or view layer settings
    bpy.context.scene.render.film_transparent = True

    # Save the blend file
    print(f"\nSaving blend file to: {OUTPUT_BLEND_PATH}")
    OUTPUT_BLEND_PATH.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND_PATH))

    print("\n" + "=" * 60)
    print("SAR Visualization Complete!")
    print("=" * 60)
    print(f"\nBlend file saved to: {OUTPUT_BLEND_PATH}")
    print(f"Animation frames: 1 to {bpy.context.scene.frame_end}")
    print("  - Each frequency shown for 30 frames")
    print("  - Use timeline to scrub through frequencies")
    print("\nTo render animation:")
    print("  1. Open the .blend file in Blender")
    print("  2. Go to Output Properties and set output path")
    print("  3. Render > Render Animation (Ctrl+F12)")


if __name__ == "__main__":
    main()
