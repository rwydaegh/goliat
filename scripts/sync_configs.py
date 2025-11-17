"""Sync config files from defaults to configs directory."""

import shutil
from pathlib import Path


def sync_configs():
    """Copy config files from defaults to configs (overwrites existing)."""
    repo_root = Path(__file__).parent.parent
    defaults_dir = repo_root / "goliat" / "config" / "defaults"
    configs_dir = repo_root / "configs"
    
    if not defaults_dir.exists():
        print(f"❌ Defaults directory not found: {defaults_dir}")
        return
    
    configs_dir.mkdir(exist_ok=True)
    
    synced_count = 0
    
    # Copy each config file (same logic as setup_configs)
    for config_file in defaults_dir.glob("*.json"):
        # Skip material_name_mapping.json - it goes to data/, not configs/
        if config_file.name == "material_name_mapping.json":
            continue
        
        target = configs_dir / config_file.name
        shutil.copy2(config_file, target)
        print(f"✓ Synced {config_file.name}")
        synced_count += 1
    
    print(f"\n✓ Synced {synced_count} config file(s) from defaults/ to configs/")


if __name__ == "__main__":
    sync_configs()


