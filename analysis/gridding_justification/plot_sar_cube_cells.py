"""
Plot 3: Cells along 10g SAR cube side length vs Grid Size
- 10g SAR cube has a side length that depends on tissue density
- For muscle/skin-like tissue (density ~1000 kg/m³), 10g ≈ 10 cm³
- Side length = (10 cm³)^(1/3) ≈ 21.5 mm
- Number of cells along one side = side_length / grid_step
"""

import matplotlib.pyplot as plt
import numpy as np

try:
    import scienceplots
    plt.style.use("science")
except ImportError:
    plt.style.use("seaborn-v0_8-whitegrid")

# 10g SAR cube parameters
# For tissue with density ~1000 kg/m³ (close to water/muscle)
# 10g = 0.01 kg, Volume = mass/density = 0.01/1000 = 1e-5 m³ = 10 cm³
# Side length = (10 cm³)^(1/3) = (10)^(1/3) cm ≈ 2.154 cm = 21.54 mm
TISSUE_DENSITY = 1000  # kg/m³
MASS_10G = 0.01  # kg
VOLUME_10G = MASS_10G / TISSUE_DENSITY  # m³
SIDE_LENGTH_M = VOLUME_10G ** (1/3)  # m
SIDE_LENGTH_MM = SIDE_LENGTH_M * 1000  # mm

print(f"10g SAR cube side length: {SIDE_LENGTH_MM:.2f} mm")

# Create grid size range
grid_sizes = np.linspace(0.2, 8.5, 200)

# Number of cells along one side
cells_per_side = SIDE_LENGTH_MM / grid_sizes

# Create a figure and axis object
fig, ax = plt.subplots(figsize=(6, 4))

# Define thresholds for cell count
# At least 3-5 cells per side is typically considered minimum for meaningful averaging
THRESHOLD_MIN_CELLS = 5  # Minimum cells for reliable SAR averaging
THRESHOLD_GOOD_CELLS = 10  # Good resolution

# Find corresponding grid sizes
grid_at_min = SIDE_LENGTH_MM / THRESHOLD_MIN_CELLS  # ~4.3 mm
grid_at_good = SIDE_LENGTH_MM / THRESHOLD_GOOD_CELLS  # ~2.15 mm

# Add shaded regions
# Red region: too few cells (< 5 cells, grid > 4.3mm)
ax.axvspan(grid_at_min, grid_sizes.max() + 1, facecolor="red", alpha=0.15, label=f"< {THRESHOLD_MIN_CELLS} cells")
# Orange region: marginal (5-10 cells)
ax.axvspan(grid_at_good, grid_at_min, facecolor="orange", alpha=0.15, label=f"{THRESHOLD_MIN_CELLS}-{THRESHOLD_GOOD_CELLS} cells")
# Green region: good (> 10 cells)
ax.axvspan(0, grid_at_good, facecolor="green", alpha=0.15, label=f"> {THRESHOLD_GOOD_CELLS} cells")

# Add horizontal lines at thresholds
ax.axhline(y=THRESHOLD_MIN_CELLS, color="red", linestyle="--", linewidth=1, alpha=0.7)
ax.axhline(y=THRESHOLD_GOOD_CELLS, color="orange", linestyle="--", linewidth=1, alpha=0.7)

# Plot with BLACK line
ax.plot(
    grid_sizes,
    cells_per_side,
    "-",
    color="black",
    linewidth=1.5,
)

# Add annotations
ax.annotate(
    f"{THRESHOLD_MIN_CELLS} cells",
    xy=(7, THRESHOLD_MIN_CELLS),
    xytext=(7.5, THRESHOLD_MIN_CELLS + 5),
    fontsize=8,
    arrowprops=dict(arrowstyle="->", color="red", alpha=0.7),
    ha="left",
    color="red",
)

ax.annotate(
    f"{THRESHOLD_GOOD_CELLS} cells",
    xy=(4, THRESHOLD_GOOD_CELLS),
    xytext=(5, THRESHOLD_GOOD_CELLS + 8),
    fontsize=8,
    arrowprops=dict(arrowstyle="->", color="orange", alpha=0.7),
    ha="left",
    color="darkorange",
)

# Set the labels for the axes
ax.set_xlabel("Grid step size [mm]")
ax.set_ylabel("Cells per 10g SAR cube side")

# Set y-axis limits
ax.set_ylim(bottom=0, top=120)

# Set x-axis limits and invert (to match other plots)
ax.set_xlim(left=grid_sizes.max() + 0.5, right=0)
ax.invert_xaxis()

# Add grid
ax.grid(True, which="major", axis="both", linestyle="--", alpha=0.5)

# Add note about cube size
ax.text(
    0.98, 0.98,
    f"10g cube side: {SIDE_LENGTH_MM:.1f} mm\n(tissue density: {TISSUE_DENSITY} kg/m³)",
    transform=ax.transAxes,
    fontsize=7,
    ha="right",
    va="top",
    style="italic",
    alpha=0.7,
    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
)

# Tight layout
plt.tight_layout()

# Save the figure
plt.savefig("analysis/gridding_justification/sar_cube_cells_vs_grid_size.pdf")
plt.savefig("analysis/gridding_justification/sar_cube_cells_vs_grid_size.png", dpi=300)

print("Saved: sar_cube_cells_vs_grid_size.pdf and .png")

# Show the plot
plt.show()
