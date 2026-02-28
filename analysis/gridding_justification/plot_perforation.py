"""
Plot 1: Perforation vs Grid Size
- Black line with markers
- Two-region shading: green (fine) below 2.5mm, red (too coarse) above 2.5mm
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

try:
    import scienceplots
    plt.style.use("science")
except ImportError:
    plt.style.use("seaborn-v0_8-whitegrid")

# Load the data from the CSV file
data = pd.read_csv("analysis/screenshot_analysis/results.csv")

# Create a figure and axis object
fig, ax = plt.subplots(figsize=(6, 4))

# Define threshold for coarse vs fine
THRESHOLD_MM = 2.5

# Add shaded regions with low alpha
# Green region: fine (grid size < 2.5mm)
ax.axvspan(0, THRESHOLD_MM, facecolor="green", alpha=0.15, label="Fine grid")
# Red region: too coarse (grid size > 2.5mm)  
ax.axvspan(THRESHOLD_MM, data["grid_size"].max() + 1, facecolor="red", alpha=0.15, label="Too coarse")

# Add vertical line at threshold
ax.axvline(x=THRESHOLD_MM, color="gray", linestyle="--", linewidth=1.5, alpha=0.7)

# Filter out zero perforation points for plotting and labeling
plot_data = data[data["perforation"] > 0].copy()

# Plot with BLACK line
ax.plot(
    plot_data["grid_size"],
    plot_data["perforation"],
    "o-",
    color="black",
    markersize=5,
    linewidth=1.5,
    label="Perforation",
)

# Add labels to each point
for i, row in plot_data.iterrows():
    if row["perforation"] > 13.1:
        # Position text above the point
        ax.text(
            row["grid_size"],
            row["perforation"] * 1.25,
            f"{row['perforation']:.1f}\\%",
            ha="center",
            va="bottom",
            fontsize=7,
        )
    else:
        # Position text to the right of the point
        ax.text(
            row["grid_size"] + 0.15,
            row["perforation"],
            f"{row['perforation']:.1f}\\%",
            ha="left",
            va="center",
            fontsize=7,
        )

# Add annotation for the threshold
ax.annotate(
    f"Threshold: {THRESHOLD_MM} mm",
    xy=(THRESHOLD_MM, 13.1),
    xytext=(THRESHOLD_MM + 1.5, 5),
    fontsize=8,
    arrowprops=dict(arrowstyle="->", color="gray", alpha=0.7),
    ha="left",
)

# Set the labels for the axes
ax.set_xlabel("Grid step size [mm]")
ax.set_ylabel("Perforation [\\%]")

# Set y-axis to log scale
ax.set_yscale("log")

# Adjust y-axis limits to see the lowest point
ax.set_ylim(bottom=0.8, top=200)

# Set the zero perforation line at 1.5
zero_perforation_point = 1.5

# Add a vertical line and shaded region for no perforation
ax.axvline(x=zero_perforation_point, color="k", linestyle="--", linewidth=1)
ax.axvspan(zero_perforation_point, 0, facecolor="gray", alpha=0.3)
ax.text(
    zero_perforation_point / 2,
    2,
    r"\textbf{No perforation}",
    rotation=90,
    verticalalignment="bottom",
    ha="center",
    fontsize=9,
)

# Set x-axis limits and invert
ax.set_xlim(left=data["grid_size"].max() + 0.5, right=0)
ax.invert_xaxis()

# Add grid
ax.grid(True, which="major", axis="both", linestyle="--", alpha=0.5)

# Tight layout
plt.tight_layout()

# Save the figure
plt.savefig("analysis/gridding_justification/perforation_vs_grid_size.pdf")
plt.savefig("analysis/gridding_justification/perforation_vs_grid_size.png", dpi=300)

print("Saved: perforation_vs_grid_size.pdf and .png")

# Show the plot
plt.show()
