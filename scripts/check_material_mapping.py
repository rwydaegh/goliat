import os
import json

def check_consistency():
    """
    Checks for inconsistencies between the material name mapping and the extracted phantom tissues.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    material_mapping_path = os.path.join(base_dir, 'data', 'material_name_mapping.json')
    phantom_tissues_dir = os.path.join(base_dir, 'data', 'phantom_tissues')

    with open(material_mapping_path, 'r') as f:
        material_mapping = json.load(f)

    all_phantoms = list(material_mapping.keys())
    
    for phantom_name in all_phantoms:
        print(f"--- Checking phantom: {phantom_name} ---")
        
        # Load the ground truth tissues
        tissue_file_path = os.path.join(phantom_tissues_dir, f"{phantom_name}_tissues.json")
        if not os.path.exists(tissue_file_path):
            print(f"  - WARNING: Tissue file not found for '{phantom_name}'. Skipping.")
            continue
            
        with open(tissue_file_path, 'r') as f:
            ground_truth_tissues = set(json.load(f))

        # Get the tissues from the material mapping
        mapped_tissues = set(material_mapping[phantom_name].keys())
        # Remove the _tissue_groups key as it's not a tissue
        mapped_tissues.discard("_tissue_groups")

        # Find missing and extra tissues
        missing_tissues = ground_truth_tissues - mapped_tissues
        extra_tissues = mapped_tissues - ground_truth_tissues

        if not missing_tissues and not extra_tissues:
            print("  - OK: Material mapping is consistent with the phantom file.")
        else:
            if missing_tissues:
                print(f"  - Missing tissues in material_name_mapping.json:")
                for tissue in sorted(list(missing_tissues)):
                    print(f"    - {tissue}")
            if extra_tissues:
                print(f"  - Extra tissues in material_name_mapping.json (not in phantom file):")
                for tissue in sorted(list(extra_tissues)):
                    print(f"    - {tissue}")
        print("-" * (len(phantom_name) + 20))


if __name__ == "__main__":
    check_consistency()