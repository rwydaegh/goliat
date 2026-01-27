#!/usr/bin/env python3
"""
Script to zip all auto_induced directories into a single archive and upload to transfer.sh.

This script:
1. Starts from the root directory
2. Looks into the 'results' directory
3. Finds 'far_field' or 'farfield_*' folders containing phantom/frequency/auto_induced structure
4. Creates a single zip with nested directory structure: phantom/frequency/auto_induced/
5. Uploads the single zip to transfer.sh (files kept for 14 days, no auth needed)
"""

import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


def find_auto_induced_directories(root_path: Path) -> list[tuple[Path, str, str]]:
    """
    Find all auto_induced directories under results/farfield_*/phantom/freq/.
    
    Returns:
        List of tuples: (auto_induced_path, phantom_name, frequency)
    """
    results_dir = root_path / "results"
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return []
    
    auto_induced_dirs = []
    
    # Look for far_field or farfield_* directories
    farfield_patterns = ["far_field", "farfield_*"]
    farfield_dirs = []
    for pattern in farfield_patterns:
        farfield_dirs.extend(results_dir.glob(pattern))
    
    for farfield_dir in farfield_dirs:
        if not farfield_dir.is_dir():
            continue
        
        # Under farfield, look for phantom directories
        for phantom_dir in farfield_dir.iterdir():
            if not phantom_dir.is_dir():
                continue
            phantom_name = phantom_dir.name
            
            # Under phantom, look for frequency directories
            for freq_dir in phantom_dir.iterdir():
                if not freq_dir.is_dir():
                    continue
                frequency = freq_dir.name
                
                # Check for auto_induced directory
                auto_induced_path = freq_dir / "auto_induced"
                if auto_induced_path.exists() and auto_induced_path.is_dir():
                    auto_induced_dirs.append((auto_induced_path, phantom_name, frequency))
    
    return auto_induced_dirs


def create_combined_zip(auto_induced_dirs: list[tuple[Path, str, str]], output_path: Path) -> Path | None:
    """
    Create a single zip file containing all auto_induced directories with nested structure.
    
    Structure in zip: phantom/frequency/auto_induced/...
    
    Args:
        auto_induced_dirs: List of (auto_induced_path, phantom_name, frequency) tuples
        output_path: Path for the output zip file
        
    Returns:
        Path to the created zip file, or None if failed
    """
    try:
        print(f"Creating combined zip at {output_path}...")
        print(f"This may take a while for large directories...")
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for auto_induced_path, phantom_name, frequency in auto_induced_dirs:
                print(f"  Adding: {phantom_name}/{frequency}/auto_induced/")
                
                # Walk through all files in auto_induced directory
                for file_path in auto_induced_path.rglob('*'):
                    if file_path.is_file():
                        # Create archive path: phantom/frequency/auto_induced/relative_path
                        relative_to_auto = file_path.relative_to(auto_induced_path)
                        archive_path = Path(phantom_name) / frequency / "auto_induced" / relative_to_auto
                        zipf.write(file_path, archive_path)
        
        print(f"Created zip: {output_path}")
        print(f"Zip size: {output_path.stat().st_size / (1024*1024):.2f} MB")
        return output_path
        
    except Exception as e:
        print(f"Error creating zip: {e}")
        return None


def upload_to_transfer_sh(zip_path: Path) -> str | None:
    """
    Upload a zip file to transfer.sh.
    
    transfer.sh keeps files for 14 days and requires no authentication.
    
    Args:
        zip_path: Path to the zip file
        
    Returns:
        Download URL if successful, None otherwise
    """
    import requests
    
    file_size_mb = zip_path.stat().st_size / (1024*1024)
    print(f"Uploading {zip_path.name} ({file_size_mb:.2f} MB) to transfer.sh...")
    
    try:
        # Upload using requests
        with open(zip_path, 'rb') as f:
            response = requests.put(
                f"https://transfer.sh/{zip_path.name}",
                data=f,
                headers={'Max-Days': '14'}
            )
        
        if response.status_code == 200:
            download_url = response.text.strip()
            print(f"Upload successful!")
            print(f"Download URL: {download_url}")
            return download_url
        else:
            print(f"Upload failed with status {response.status_code}: {response.text}")
            
    except ImportError:
        # Fallback to curl if requests not available
        print("requests library not available, trying curl...")
        try:
            result = subprocess.run(
                ["curl", "--upload-file", str(zip_path), f"https://transfer.sh/{zip_path.name}"],
                capture_output=True,
                text=True,
                check=True
            )
            download_url = result.stdout.strip()
            print(f"Upload successful!")
            print(f"Download URL: {download_url}")
            return download_url
        except FileNotFoundError:
            print("curl not found")
        except subprocess.CalledProcessError as e:
            print(f"curl upload failed: {e.stderr}")
    except Exception as e:
        print(f"Upload failed: {e}")
    
    return None


def main():
    """Main function to find, zip, and upload auto_induced directories."""
    # Start from the root (current working directory or script location)
    root_path = Path.cwd()
    print(f"Starting from root: {root_path}")
    
    # Find all auto_induced directories
    auto_induced_dirs = find_auto_induced_directories(root_path)
    
    if not auto_induced_dirs:
        print("No auto_induced directories found.")
        return
    
    print(f"Found {len(auto_induced_dirs)} auto_induced directories:")
    for auto_induced_path, phantom_name, frequency in auto_induced_dirs:
        print(f"  - {phantom_name}/{frequency}/auto_induced")
    
    # Create output zip path
    output_zip = root_path / "all_auto_induced.zip"
    
    # Check if zip already exists
    if output_zip.exists():
        print(f"\nZip already exists: {output_zip}")
        response = input("Re-create zip? (y/N): ").strip().lower()
        if response != 'y':
            print("Using existing zip file.")
        else:
            output_zip.unlink()
            zip_path = create_combined_zip(auto_induced_dirs, output_zip)
            if not zip_path:
                return
    else:
        zip_path = create_combined_zip(auto_induced_dirs, output_zip)
        if not zip_path:
            return
        output_zip = zip_path
    
    # Upload to transfer.sh
    print("\n" + "="*60)
    url = upload_to_transfer_sh(output_zip)
    
    if url:
        print("\n" + "="*60)
        print("DOWNLOAD URL (valid for 14 days):")
        print("="*60)
        print(url)
        print("="*60)


if __name__ == "__main__":
    main()
