# Python script to individually center each antenna model.

import os
import json
import s4l_v1
import s4l_v1.model as model
from s4l_v1.model import Vec3
import s4l_v1.document as document
from s4l_v1._api.application import run_application
import numpy as np
import XCoreModeling
import re

def get_antenna_model_name(frequency_mhz, config):
    """ Determines the antenna model type (PIFA or IFA) based on the frequency. """
    for model_type, freqs in config.get("models", {}).items():
        if frequency_mhz in freqs:
            return model_type
    raise ValueError(f"Antenna model not defined for frequency: {frequency_mhz} MHz")

def center_antenna_and_export_sab(file_path, output_dir, antenna_config):
    """
    Opens an antenna .smash file, standardizes its name, centers it,
    conditionally rotates it, adds a final bounding box, and exports the antenna
    and its bounding box to a .sab file.
    """
    print(f"Processing: {os.path.basename(file_path)}")
    document.Open(file_path)

    # --- 1. Identify Target Group and Standardize Name ---
    base_name = os.path.basename(file_path)
    freq_match = re.search(r'\d+', base_name)
    if not freq_match:
        print(f"  - Error: Could not extract frequency from filename. Skipping.")
        document.Close()
        return
    
    freq_mhz = int(freq_match.group())
    freq_str = '2150' if freq_mhz == 2140 else str(freq_mhz)
    
    try:
        model_name = get_antenna_model_name(freq_mhz, antenna_config)
    except ValueError as e:
        print(f"  - Error: {e}. Skipping.")
        document.Close()
        return

    all_groups = [e for e in model.AllEntities() if isinstance(e, model.EntityGroup)]
    antenna_group = next((g for g in all_groups if g.Name == 'Antenna'), None)
    if not antenna_group:
        antenna_candidates = [g for g in all_groups if g.Name.startswith('Antenna')]
        if len(antenna_candidates) == 1:
            antenna_group = antenna_candidates[0]
    if not antenna_group:
        mhz_candidates = [g for g in all_groups if 'MHz' in g.Name]
        if len(mhz_candidates) == 1:
            antenna_group = mhz_candidates[0]

    if not antenna_group:
        print(f"  - Error: Could not identify a unique antenna group. Skipping.")
        document.Close()
        return
    
    antenna_group.Name = f"Antenna {freq_str} MHz"

    # --- 2. Center the Antenna ---
    bbox = model.GetBoundingBox(antenna_group.Entities)
    center_point = (np.array(bbox[0]) + np.array(bbox[1])) / 2.0
    
    translation_transform = XCoreModeling.Transform()
    translation_transform.Translation = Vec3(-center_point)
    antenna_group.ApplyTransform(translation_transform)

    # --- 3. Conditionally Rotate the Antenna ---
    if freq_str not in ['700', '835']:
        scale = model.Vec3(1, 1, 1)
        rotation = model.Vec3(np.deg2rad(90), 0, 0)
        translation = model.Vec3(0, 0, 0)
        rotation_transform = model.Transform(scale, rotation, translation)
        antenna_group.ApplyTransform(rotation_transform)

    # --- 4. Create Final Bounding Box ---
    final_bbox = model.GetBoundingBox(antenna_group.Entities)
    bbox_entity = XCoreModeling.CreateWireBlock(Vec3(final_bbox[0]), Vec3(final_bbox[1]))
    bbox_entity.Name = "Antenna bounding box"

    # --- 5. Export to .sab and Close ---
    save_filename = f"{model_name}_{freq_mhz}MHz_centered.sab"
    save_path = os.path.join(output_dir, save_filename)
    
    entities_to_export = [antenna_group, bbox_entity]
    
    print(f"  -> Exporting to: {os.path.basename(save_path)}")
    model.Export(entities_to_export, save_path)
    document.Close()

def main():
    run_application(disable_ui_plugins=True)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Load simulation config to get antenna model info
    config_path = os.path.join(base_dir, 'simulation_config.json')
    with open(config_path, 'r') as f:
        sim_config = json.load(f)
    antenna_config = sim_config.get('antenna_config', {})

    source_dir = os.path.join(base_dir, 'data', 'antennas', 'downloaded_from_drive')
    centered_dir = os.path.join(base_dir, 'data', 'antennas', 'centered')
    
    os.makedirs(centered_dir, exist_ok=True)
    
    files_to_process = [
        os.path.join(source_dir, f)
        for f in os.listdir(source_dir)
        if f.endswith('.smash')
    ]

    if not files_to_process:
        print(f"No .smash files found to process in '{source_dir}'.")
        return

    print(f"Found {len(files_to_process)} files to process...")
    for file_path in files_to_process:
        try:
            center_antenna_and_export_sab(file_path, centered_dir, antenna_config)
        except Exception as e:
            print(f"An unexpected error occurred while processing {os.path.basename(file_path)}: {e}")
            if s4l_v1.document.IsOpen():
                s4l_v1.document.Close()

    print("\nProcessing complete.")


if __name__ == "__main__":
    main()