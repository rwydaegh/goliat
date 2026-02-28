"""
Plot 2: Computational Resources vs Grid Size
- Similar layout to perforation plot
- Y-axis: Computational resources (arbitrary units) scaling as 1/dx^4
- Three regions: 
  - Red (impossible): dx < 0.3mm
  - Orange (hard): 0.3mm < dx < 1.0mm  
  - Green (doable): dx > 1.0mm
"""

import matplotlib.pyplot as plt
import numpy as np

try:
    import scienceplots
    plt.style.use("science")
except ImportError:
    plt.style.use("seaborn-v0_8-whitegrid")

# Create grid size range (similar to perforation data range)
grid_sizes = np.linspace(0.2, 8.5, 200)

# Computational resources scale as 1/dx^4 for 3D FDTD
# - Number of cells scales as 1/dx^3
# - Time step scales as dx (Courant condition)
# - So total operations scale as 1/dx^4
# Normalize so that dx=1mm gives resources=1
resources = (1.0 / grid_sizes) ** 4

# Create a figure and axis object
fig, ax = plt.subplots(figsize=(6, 4))

# Define thresholds
THRESHOLD_IMPOSSIBLE = 0.3  # Below this is impossible
THRESHOLD_HARD = 1.0        # Below this is hard, above is doable

# Add shaded regions with low alpha
# Red region: impossible (grid size < 0.3mm)
ax.axvspan(0, THRESHOLD_IMPOSSIBLE, facecolor="red", alpha=0.2, label="Borderline impossible")
# Orange region: hard (0.3mm < grid size < 1.0mm)
ax.axvspan(THRESHOLD_IMPOSSIBLE, THRESHOLD_HARD, facecolor="orange", alpha=0.2, label="Challenging")
# Green region: doable (grid size > 1.0mm)
ax.axvspan(THRESHOLD_HARD, grid_sizes.max() + 1, facecolor="green", alpha=0.15, label="Feasible")

# Add vertical lines at thresholds
ax.axvline(x=THRESHOLD_IMPOSSIBLE, color="red", linestyle="--", linewidth=1.5, alpha=0.7)
ax.axvline(x=THRESHOLD_HARD, color="orange", linestyle="--", linewidth=1.5, alpha=0.7)

# Plot with BLACK line
ax.plot(
    grid_sizes,
    resources,
    "-",
    color="black",
    linewidth=1.5,
    label=r"$\propto \Delta x^{-4}$",
)

# Add annotations for thresholds
ax.annotate(
    f"{THRESHOLD_IMPOSSIBLE} mm",
    xy=(THRESHOLD_IMPOSSIBLE, 100),
    xytext=(THRESHOLD_IMPOSSIBLE + 0.3, 500),
    fontsize=8,
    arrowprops=dict(arrowstyle="->", color="red", alpha=0.7),
    ha="left",
    color="red",
)

ax.annotate(
    f"{THRESHOLD_HARD} mm",
    xy=(THRESHOLD_HARD, 1),
    xytext=(THRESHOLD_HARD + 0.5, 5),
    fontsize=8,
    arrowprops=dict(arrowstyle="->", color="orange", alpha=0.7),
    ha="left",
    color="darkorange",
)

# Add region labels
ax.text(0.15, 0.5, "Impossible", rotation=90, fontsize=8, color="darkred", 
        ha="center", va="bottom", alpha=0.8)
ax.text(0.65, 0.3, "Challenging", rotation=90, fontsize=8, color="darkorange",
        ha="center", va="bottom", alpha=0.8)
ax.text(4.5, 0.1, "Feasible", fontsize=9, color="darkgreen",
        ha="center", va="center", alpha=0.8)

# Set the labels for the axes
ax.set_xlabel("Grid step size [mm]")
ax.set_ylabel("Computational resources [a.u.]")

# Set y-axis to log scale
ax.set_yscale("log")

# Adjust y-axis limits
ax.set_ylim(bottom=1e-4, top=1e4)

# Set x-axis limits and invert (to match perforation plot)
ax.set_xlim(left=grid_sizes.max() + 0.5, right=0)
ax.invert_xaxis()

# Add grid
ax.grid(True, which="major", axis="both", linestyle="--", alpha=0.5)

# Add legend
ax.legend(loc="upper left", fontsize=8)

# Add note about scaling
ax.text(
    0.98, 0.02,
    r"Resources $\propto N_{\mathrm{cells}} \times N_{\mathrm{steps}} \propto \Delta x^{-4}$",
    transform=ax.transAxes,
    fontsize=7,
    ha="right",
    va="bottom",
    style="italic",
    alpha=0.7,
)

# Tight layout
plt.tight_layout()

# Save the figure
plt.savefig("analysis/gridding_justification/computational_resources_vs_grid_size.pdf")
plt.savefig("analysis/gridding_justification/computational_resources_vs_grid_size.png", dpi=300)

print("Saved: computational_resources_vs_grid_size.pdf and .png")

# Show the plot
plt.show()
