import os
import platform
import subprocess
import sys

def inspect_environment():
    """
    This script is intended to be run on the oSPARC platform by a python-runner.
    It inspects the environment and prints out details.
    """
    print("--- Inspecting oSPARC Container Environment ---")

    # --- Python Information ---
    print("\n--- Python Information ---")
    print(f"Python Version: {sys.version}")
    print(f"Python Executable: {sys.executable}")

    # --- OS Information ---
    print("\n--- OS Information ---")
    print(f"Platform: {platform.platform()}")
    print(f"System: {platform.system()}")
    print(f"Release: {platform.release()}")
    print(f"Version: {platform.version()}")
    print(f"Machine: {platform.machine()}")
    print(f"Processor: {platform.processor()}")

    # --- CPU Information ---
    print("\n--- CPU Information ---")
    try:
        cpu_info = subprocess.check_output(["lscpu"]).decode()
        print(cpu_info)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        print(f"Could not run lscpu: {e}")

    # --- RAM Information ---
    print("\n--- RAM Information ---")
    try:
        mem_info = subprocess.check_output(["free", "-h"]).decode()
        print(mem_info)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        print(f"Could not run free: {e}")

    # --- GPU Information ---
    print("\n--- GPU Information ---")
    try:
        nvidia_smi_output = subprocess.check_output(["nvidia-smi"], stderr=subprocess.STDOUT).decode()
        print(nvidia_smi_output)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        print(f"Could not run nvidia-smi: {e}")

    # --- Environment Variables ---
    print("\n--- Environment Variables ---")
    for key, value in sorted(os.environ.items()):
        print(f"{key}={value}")

    # --- Licensing Information ---
    print("\n--- Licensing Information ---")
    speag_license_file = os.environ.get("SPEAG_LICENSE_FILE")
    vendor_speag_license_file = os.environ.get("VENDOR_SPEAG_LICENSE_FILE")
    if speag_license_file:
        print(f"SPEAG_LICENSE_FILE: {speag_license_file}")
    if vendor_speag_license_file:
        print(f"VENDOR_SPEAG_LICENSE_FILE: {vendor_speag_license_file}")
    if not speag_license_file and not vendor_speag_license_file:
        print("No SPEAG license environment variables found.")


    print("\n--- Script finished successfully ---")

if __name__ == "__main__":
    inspect_environment()