"""
Plot 4: Cells per Skin Depth vs Grid Size
- Skin depth varies with frequency
- For accurate FDTD, need sufficient cells to resolve the skin depth
- Using skin tissue properties from IT'IS database
"""

import matplotlib.pyplot as plt
import numpy as np

try:
    import scienceplots
    plt.style.use("science")
except ImportError:
    plt.style.use("seaborn-v0_8-whitegrid")

# Constants
C = 299792458  # Speed of light (m/s)
MU_0 = 4 * np.pi * 1e-7  # Permeability of free space (H/m)
EPS_0 = 8.854187817e-12  # Permittivity of free space (F/m)

def calculate_skin_depth(freq_mhz, eps_r, sigma):
    """Calculate skin depth in mm for lossy dielectric."""
    omega = 2 * np.pi * freq_mhz * 1e6
    eps_complex = eps_r - 1j * sigma / (omega * EPS_0)
    k = omega * np.sqrt(MU_0 * EPS_0 * eps_complex)
    alpha = -np.imag(k)
    return 1 / alpha * 1000 if alpha > 0 else np.inf  # mm

# Skin tissue properties at different frequencies (from IT'IS database)
# Using representative values for skin tissue
skin_properties = {
    450: {"eps_r": 45.75, "sigma": 0.709},
    700: {"eps_r": 43.5, "sigma": 0.82},
    835: {"eps_r": 42.5, "sigma": 0.87},
    1450: {"eps_r": 40.5, "sigma": 1.05},
    2140: {"eps_r": 39.0, "sigma": 1.35},
    2450: {"eps_r": 38.5, "sigma": 1.46},
    3500: {"eps_r": 36.5, "sigma": 2.0},
    5200: {"eps_r": 34.0, "sigma": 3.0},
    5800: {"eps_r": 33.5, "sigma": 3.4},
    7000: {"eps_r": 32.0, "sigma": 4.5},
    9000: {"eps_r": 30.0, "sigma": 6.5},
    11000: {"eps_r": 28.5, "sigma": 8.5},
    13000: {"eps_r": 27.0, "sigma": 10.5},
    15000: {"eps_r": 26.0, "sigma": 12.5},
    26000: {"eps_r": 22.0, "sigma": 25.0},
}

# Grid sizes used in the study (from your terminal output)
grid_sizes_per_freq = {
    450: 2.5, 700: 2.5, 835: 2.5, 1450: 2.5,
    2140: 1.694, 2450: 1.482, 3500: 1.0, 5200: 1.0, 5800: 1.0,
    7000: 0.6, 9000: 0.5, 11000: 0.5, 13000: 0.45, 15000: 0.4, 26000: 0.3
}

# Calculate skin depths and cells per skin depth
frequencies = sorted(skin_properties.keys())
skin_depths = []
cells_per_skin_depth = []
grid_sizes_used = []

for freq in frequencies:
    props = skin_properties[freq]
    delta = calculate_skin_depth(freq, props["eps_r"], props["sigma"])
    skin_depths.append(delta)
    
    grid_size = grid_sizes_per_freq[freq]
    grid_sizes_used.append(grid_size)
    cells_per_skin_depth.append(delta / grid_size)

# Create grid size range for continuous plot
grid_sizes = np.linspace(0.2, 8.5, 200)

# Use 450 MHz skin depth as reference (worst case - largest skin depth)
skin_depth_450 = calculate_skin_depth(450, skin_properties[450]["eps_r"], skin_properties[450]["sigma"])
# Use 26 GHz skin depth (smallest skin depth - most challenging)
skin_depth_26000 = calculate_skin_depth(26000, skin_properties[26000]["eps_r"], skin_properties[26000]["sigma"])

print(f"Skin depth at 450 MHz: {skin_depth_450:.2f} mm")
print(f"Skin depth at 26 GHz: {skin_depth_26000:.2f} mm")

cells_per_skin_depth_450 = skin_depth_450 / grid_sizes
cells_per_skin_depth_26000 = skin_depth_26000 / grid_sizes

# Create a figure and axis object
fig, ax = plt.subplots(figsize=(6, 4))

# Define threshold for minimum cells per skin depth
# Typically need at least 3-5 cells per skin depth for accurate results
THRESHOLD_MIN = 3
THRESHOLD_GOOD = 5

# Plot curves for different frequencies
ax.plot(grid_sizes, cells_per_skin_depth_450, "-", color="blue", linewidth=1.5, 
        label=f"450 MHz ($\\delta$ = {skin_depth_450:.1f} mm)")
ax.plot(grid_sizes, cells_per_skin_depth_26000, "-", color="red", linewidth=1.5,
        label=f"26 GHz ($\\delta$ = {skin_depth_26000:.1f} mm)")

# Add horizontal threshold lines
ax.axhline(y=THRESHOLD_MIN, color="gray", linestyle="--", linewidth=1, alpha=0.7)
ax.axhline(y=THRESHOLD_GOOD, color="gray", linestyle=":", linewidth=1, alpha=0.7)

# Add annotations for thresholds
ax.text(0.3, THRESHOLD_MIN + 0.5, f"Minimum ({THRESHOLD_MIN} cells)", fontsize=7, color="gray")
ax.text(0.3, THRESHOLD_GOOD + 0.5, f"Recommended ({THRESHOLD_GOOD} cells)", fontsize=7, color="gray")

# Plot actual grid sizes used (as markers)
ax.scatter(grid_sizes_used, cells_per_skin_depth, color="black", s=30, zorder=5, 
           marker="o", label="Grid sizes used")

# Set the labels for the axes
ax.set_xlabel("Grid step size [mm]")
ax.set_ylabel("Cells per skin depth")

# Set y-axis limits
ax.set_ylim(bottom=0, top=100)

# Set x-axis limits and invert (to match other plots)
ax.set_xlim(left=grid_sizes.max() + 0.5, right=0)
ax.invert_xaxis()

# Add grid
ax.grid(True, which="major", axis="both", linestyle="--", alpha=0.5)

# Add legend
ax.legend(loc="upper left", fontsize=7)

# Tight layout
plt.tight_layout()

# Save the figure
plt.savefig("analysis/gridding_justification/skin_depth_cells_vs_grid_size.pdf")
plt.savefig("analysis/gridding_justification/skin_depth_cells_vs_grid_size.png", dpi=300)

print("Saved: skin_depth_cells_vs_grid_size.pdf and .png")

# Show the plot
plt.show()
