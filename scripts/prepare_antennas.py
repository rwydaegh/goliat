# Python script to individually center each antenna model.

import os
import sys
import json
import s4l_v1
import s4l_v1.model as model
from s4l_v1.model import Vec3
import s4l_v1.document as document
from s4l_v1._api.application import run_application
import numpy as np
import XCoreModeling
import re
import logging

# --- 1. Set up Logging ---
logger = logging.getLogger(__name__)

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def center_antenna_and_export_sab(file_path, output_dir):
    """
    Opens an antenna .smash file, standardizes its name, centers it,
    conditionally rotates it, adds a final bounding box, and exports the antenna
    and its bounding box to a .sab file.
    """
    logger.info(f"Processing: {os.path.basename(file_path)}")
    document.Open(file_path)

    # --- 1. Identify Target Group and Standardize Name ---
    base_name = os.path.basename(file_path)
    freq_match = re.search(r'\d+', base_name)
    if not freq_match:
        logger.error(f"  - Error: Could not extract frequency from filename. Skipping.")
        document.Close()
        return
    
    freq_mhz = int(freq_match.group())
    freq_str = str(freq_mhz)

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
        logger.error(f"  - Error: Could not identify a unique antenna group. Skipping.")
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
    save_filename = f"{freq_mhz}MHz_centered.sab"
    save_path = os.path.join(output_dir, save_filename)
    
    entities_to_export = [antenna_group, bbox_entity]
    
    logger.info(f"  -> Exporting to: {os.path.basename(save_path)}")
    model.Export(entities_to_export, save_path)
    document.Close()

def main():
    run_application(disable_ui_plugins=True)
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    source_dir = os.path.join(project_root, 'data', 'antennas', 'downloaded_from_drive')
    centered_dir = os.path.join(project_root, 'data', 'antennas', 'centered')
    
    os.makedirs(centered_dir, exist_ok=True)
    
    files_to_process = [
        os.path.join(source_dir, f)
        for f in os.listdir(source_dir)
        if f.endswith('.smash')
    ]

    if not files_to_process:
        logger.warning(f"No .smash files found to process in '{source_dir}'.")
        return

    logger.info(f"Found {len(files_to_process)} files to process...")
    for file_path in files_to_process:
        try:
            center_antenna_and_export_sab(file_path, centered_dir)
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing {os.path.basename(file_path)}: {e}")
            if s4l_v1.document.IsOpen():
                s4l_v1.document.Close()

    logger.info("\nProcessing complete.")


if __name__ == "__main__":
    main()