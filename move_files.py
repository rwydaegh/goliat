import os
import glob
import shutil

# Create destination directories if they don't exist
os.makedirs("analysis/cpw/data", exist_ok=True)

# Move all .pkl files
for pkl_file in glob.glob("analysis/*.pkl"):
    shutil.move(pkl_file, "analysis/cpw/data/")

# Move the config file
if os.path.exists("configs/all_freq_setup_config.json"):
    shutil.move("configs/all_freq_setup_config.json", "analysis/cpw/all_freq_setup_config.json")

# Clean up empty directories if necessary
if os.path.exists("analysis") and not os.listdir("analysis"):
    os.rmdir("analysis")

print("Files moved successfully.")