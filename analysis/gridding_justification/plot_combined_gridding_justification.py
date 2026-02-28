"""
Combined Gridding Justification Figure
All plots stacked vertically to justify grid size selection for the paper.
Shows the "Goldilocks zone" for grid sizing.

Uses IEEE figsize and scienceplots style to match the paper.
Perforation plot is copied verbatim from the original with added coloring.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
import scienceplots

# Set plot style for a scientific paper look - force IEEE style
plt.style.use(["science", "ieee"])

# Constants for d_90 calculation
MU_0 = 4 * np.pi * 1e-7  # Permeability of free space (H/m)
EPS_0 = 8.854187817e-12  # Permittivity of free space (F/m)

# 10g SAR cube parameters
TISSUE_DENSITY = 1000  # kg/m³
MASS_10G = 0.01  # kg
VOLUME_10G = MASS_10G / TISSUE_DENSITY  # m³
SIDE_LENGTH_MM = (VOLUME_10G ** (1/3)) * 1000  # mm (~21.5 mm)


def calculate_d90(freq_mhz, eps_r, sigma):
    """Calculate d_90 (90% power absorption depth) in mm for lossy dielectric."""
    omega = 2 * np.pi * freq_mhz * 1e6
    eps_complex = eps_r - 1j * sigma / (omega * EPS_0)
    k = omega * np.sqrt(MU_0 * EPS_0 * eps_complex)
    alpha = -np.imag(k)
    # d_90 = ln(10) / (2*alpha) - depth where 90% of power is absorbed
    return np.log(10) / (2 * alpha) * 1000 if alpha > 0 else np.inf


def get_color_for_cells(cells, threshold_red=3, threshold_orange=5):
    """Return color based on number of cells per d_90."""
    if cells < threshold_red:
        return "red"
    elif cells < threshold_orange:
        return "orange"
    else:
        return "green"


def plot_colored_line(ax, x, y, threshold_red=3, threshold_orange=5, linewidth=1.5, label=None):
    """Plot a line with color changing based on y-value thresholds."""
    # Create segments
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    
    # Assign colors based on y values (average of segment endpoints)
    colors = []
    for i in range(len(segments)):
        avg_y = (y[i] + y[i+1]) / 2
        colors.append(get_color_for_cells(avg_y, threshold_red, threshold_orange))
    
    # Create LineCollection
    lc = LineCollection(segments, colors=colors, linewidths=linewidth)
    ax.add_collection(lc)
    
    # Add a dummy line for legend
    if label:
        ax.plot([], [], color="gray", linewidth=linewidth, label=label)
    
    return lc


# Skin tissue properties at different frequencies (from IT'IS database)
skin_properties = {
    450: {"eps_r": 45.75, "sigma": 0.709},
    7000: {"eps_r": 32.0, "sigma": 4.5},  # Added 7 GHz
    26000: {"eps_r": 22.0, "sigma": 25.0},
}

# Calculate d_90 values
d90_450 = calculate_d90(450, skin_properties[450]["eps_r"], skin_properties[450]["sigma"])
d90_7000 = calculate_d90(7000, skin_properties[7000]["eps_r"], skin_properties[7000]["sigma"])
d90_26000 = calculate_d90(26000, skin_properties[26000]["eps_r"], skin_properties[26000]["sigma"])

print(f"d_90 at 450 MHz: {d90_450:.2f} mm")
print(f"d_90 at 7 GHz: {d90_7000:.2f} mm")
print(f"d_90 at 26 GHz: {d90_26000:.2f} mm")

# Load perforation data
data = pd.read_csv("analysis/screenshot_analysis/results.csv")

# Create grid size range - extend to very small values so lines skyrocket
grid_sizes = np.logspace(np.log10(0.01), np.log10(10), 500)  # Extend to 0.01 mm, up to 10 mm
grid_sizes_fine = np.logspace(np.log10(0.01), np.log10(10), 500)  # For d_90 plot

# Create figure with 4 subplots stacked vertically (IEEE column width)
fig, axes = plt.subplots(4, 1, figsize=(3.5, 8), sharex=True)

# Common x-axis settings - LOG SCALE (can't use 0)
x_min, x_max = 0.1, 10  # Stop at 10 mm, start at 0.1 mm for log scale

# Color scheme (muted for academic paper)
COLOR_ACCEPTABLE = "green"
COLOR_MARGINAL = "orange"
COLOR_PROBLEMATIC = "red"
ALPHA_REGION = 0.15

# ============================================================================
# Plot 1 (a): Perforation - COPIED VERBATIM FROM ORIGINAL with added coloring
# ============================================================================
ax1 = axes[0]
ax1.grid(True, which="major", axis="x", linestyle="--")

# Threshold for perforation - add colored regions
PERF_THRESHOLD = 2.5
ax1.axvspan(x_min, PERF_THRESHOLD, facecolor=COLOR_ACCEPTABLE, alpha=ALPHA_REGION)
ax1.axvspan(PERF_THRESHOLD, x_max, facecolor=COLOR_PROBLEMATIC, alpha=ALPHA_REGION)
ax1.axvline(x=PERF_THRESHOLD, color="gray", linestyle="--", linewidth=1, alpha=0.7)

# Filter out zero perforation points for plotting and labeling
plot_data = data[data["perforation"] > 0].copy()
ax1.plot(
    plot_data["grid_size"],
    plot_data["perforation"],
    "o-",
    color="black",  # Changed to black
    markersize=4,
)

# Add virtual data point at 0% to extend the line downward
# Find the lowest perforation point (1% at 2mm) and extrapolate
lowest_point = plot_data[plot_data["perforation"] == plot_data["perforation"].min()].iloc[0]
# Add a virtual point that extends the line down to ~0.1% (well below visible y range)
virtual_x = lowest_point["grid_size"] - 0.2  # Slightly to the left
virtual_y = 0.1  # Well below the y-axis minimum of 0.8
# Replot with the virtual point included
ax1.plot(
    [virtual_x, lowest_point["grid_size"]],
    [virtual_y, lowest_point["perforation"]],
    "-",
    color="black",
    markersize=0,  # No marker for virtual point
)

# Add labels to each point
for i, row in plot_data.iterrows():
    if row["perforation"] > 13.1:
        # Position text above the point
        ax1.text(
            row["grid_size"],
            row["perforation"] * 1.2,
            f"{row['perforation']:.1f}\\%",
            ha="center",
            va="bottom",
        )
    else:
        # Position text to the right of the point
        ax1.text(
            row["grid_size"] + 0.15,
            row["perforation"],
            f"{row['perforation']:.1f}\\%",
            ha="left",
            va="center",
        )

# Set the labels for the axes
ax1.set_ylabel("Perforation [\\%]")

# Set y-axis to log scale
ax1.set_yscale("log")

# Adjust y-axis limits to see the lowest point
ax1.set_ylim(bottom=0.8, top=200)

# Set the zero perforation line at 1.5
zero_perforation_point = 1.5

# Add a vertical line and shaded region (use x_min for log scale)
ax1.axvline(x=zero_perforation_point, color="k", linestyle="--", linewidth=1)
ax1.axvspan(x_min, zero_perforation_point, facecolor="gray", alpha=0.2)
ax1.text(
    np.sqrt(x_min * zero_perforation_point),  # Geometric mean for log scale
    2,
    r"\textbf{No perforation}",
    rotation=90,
    verticalalignment="bottom",
    ha="center",
)

# Panel label in BOTTOM RIGHT
ax1.text(0.98, 0.05, "(a)", transform=ax1.transAxes, fontweight="bold", va="bottom", ha="right")

# ============================================================================
# Plot 2 (b): Computational Resources
# ============================================================================
ax2 = axes[1]
ax2.grid(True, which="major", axis="x", linestyle="--")

# Thresholds
COMP_IMPOSSIBLE = 0.3
COMP_HARD = 1.0

# Transition point: 7 GHz uses 0.6 mm grid, above which height factor kicks in
HEIGHT_FACTOR_TRANSITION = 0.6  # mm (7 GHz grid size)

# Full Δx⁻⁴ scaling for the entire range (solid line)
resources_full = (1.0 / grid_sizes) ** 4

# For the dotted line: Δx⁻¹ scaling below 0.6 mm (with height factor)
# Only for grid sizes below the transition point
grid_sizes_reduced = grid_sizes[grid_sizes < HEIGHT_FACTOR_TRANSITION]
cost_at_transition = (1.0 / HEIGHT_FACTOR_TRANSITION) ** 4
resources_reduced = cost_at_transition * (HEIGHT_FACTOR_TRANSITION / grid_sizes_reduced) ** 1

# Shaded regions (use x_min for log scale)
ax2.axvspan(x_min, COMP_IMPOSSIBLE, facecolor=COLOR_PROBLEMATIC, alpha=ALPHA_REGION)
ax2.axvspan(COMP_IMPOSSIBLE, COMP_HARD, facecolor=COLOR_MARGINAL, alpha=ALPHA_REGION)
ax2.axvspan(COMP_HARD, x_max, facecolor=COLOR_ACCEPTABLE, alpha=ALPHA_REGION)

# Threshold lines
ax2.axvline(x=COMP_IMPOSSIBLE, color="gray", linestyle="--", linewidth=1, alpha=0.7)
ax2.axvline(x=COMP_HARD, color="gray", linestyle="--", linewidth=1, alpha=0.7)

# Plot solid line for full Δx⁻⁴ scaling (entire range)
ax2.plot(grid_sizes, resources_full, "-", color="black", linewidth=1)

# Plot dotted line for reduced Δx⁻¹ scaling (below 0.6 mm, with height factor)
# This branches off from the solid line at the transition point
ax2.plot(grid_sizes_reduced, resources_reduced, ":", color="black", linewidth=1)

# Mark the transition point
ax2.axvline(x=HEIGHT_FACTOR_TRANSITION, color="gray", linestyle=":", linewidth=0.8, alpha=0.5)

ax2.set_ylabel("Comp. cost [a.u.]")
ax2.set_yscale("log")
ax2.set_ylim(1e-4, 1e4)

# Panel label in TOP RIGHT
ax2.text(0.98, 0.95, "(b)", transform=ax2.transAxes, fontweight="bold", va="top", ha="right")

# Add scaling note - BOTTOM RIGHT (0.5 OOM lower from 0.25)
ax2.text(0.98, 0.20, r"$\propto \Delta x^{-4}$", transform=ax2.transAxes,
         ha="right", va="bottom", style="italic")

# Add note for reduced scaling near the dotted line (1.5 OOM lower)
ax2.text(0.35, 0.52, r"$\propto \Delta x^{-1}$", transform=ax2.transAxes,
         ha="center", va="bottom", style="italic")
ax2.text(0.35, 0.50, r"(with height scaling)", transform=ax2.transAxes,
         ha="center", va="top", style="italic", fontsize=6)

# ============================================================================
# Plot 3 (c): Cells per 10g SAR cube side
# ============================================================================
ax3 = axes[2]
ax3.grid(True, which="major", axis="x", linestyle="--")

cells_per_side = SIDE_LENGTH_MM / grid_sizes

# Thresholds - orange should start PAST 2.5 mm
SAR_MIN_CELLS = 5
SAR_MARGINAL_THRESHOLD = 2.5  # Orange starts at 2.5 mm
grid_at_min = SIDE_LENGTH_MM / SAR_MIN_CELLS  # ~4.3 mm - red starts here

# Shaded regions (orange starts at 2.5mm, red at ~4.3mm) - use x_min for log scale
ax3.axvspan(grid_at_min, x_max, facecolor=COLOR_PROBLEMATIC, alpha=ALPHA_REGION)
ax3.axvspan(SAR_MARGINAL_THRESHOLD, grid_at_min, facecolor=COLOR_MARGINAL, alpha=ALPHA_REGION)
ax3.axvspan(x_min, SAR_MARGINAL_THRESHOLD, facecolor=COLOR_ACCEPTABLE, alpha=ALPHA_REGION)

# Threshold lines
ax3.axvline(x=SAR_MARGINAL_THRESHOLD, color="gray", linestyle="--", linewidth=1, alpha=0.7)
ax3.axvline(x=grid_at_min, color="gray", linestyle="--", linewidth=1, alpha=0.7)

# Plot with BLACK line
ax3.plot(grid_sizes, cells_per_side, "-", color="black", linewidth=1)

ax3.set_ylabel("Cells per 10g cube side")
ax3.set_yscale("log")
ax3.set_ylim(1, 200)

# Panel label in TOP RIGHT
ax3.text(0.98, 0.95, "(c)", transform=ax3.transAxes, fontweight="bold", va="top", ha="right")

# ============================================================================
# Plot 4 (d): Cells per d_90 with colored lines
# ============================================================================
ax4 = axes[3]
ax4.grid(True, which="major", axis="x", linestyle="--")

# Use finer grid for this plot (extends to very small values)
cells_d90_450 = d90_450 / grid_sizes_fine
cells_d90_7000 = d90_7000 / grid_sizes_fine
cells_d90_26000 = d90_26000 / grid_sizes_fine

# Thresholds for coloring (cells per d_90)
THRESHOLD_RED = 3    # Below this is red (insufficient)
THRESHOLD_ORANGE = 5  # Below this is orange (marginal)

# Plot colored lines for each frequency (no legend labels)
plot_colored_line(ax4, grid_sizes_fine, cells_d90_450,
                  threshold_red=THRESHOLD_RED, threshold_orange=THRESHOLD_ORANGE,
                  linewidth=1.5)

plot_colored_line(ax4, grid_sizes_fine, cells_d90_7000,
                  threshold_red=THRESHOLD_RED, threshold_orange=THRESHOLD_ORANGE,
                  linewidth=1.5)

plot_colored_line(ax4, grid_sizes_fine, cells_d90_26000,
                  threshold_red=THRESHOLD_RED, threshold_orange=THRESHOLD_ORANGE,
                  linewidth=1.5)

# Add text labels at specific positions instead of legend
# 26 GHz: at x=1.2mm, 0.2 mm to the left (so x=1.0)
y_26ghz_at_1p2 = d90_26000 / 1.2
ax4.text(1.0, y_26ghz_at_1p2 * 1.5, "26 GHz", ha="left", va="bottom")

# 7 GHz: fixed position at (2.5, 7)
ax4.text(2.5, 7, "7 GHz", ha="center", va="bottom")

# 450 MHz: fixed position at (5, 30)
ax4.text(5, 30, "450 MHz", ha="center", va="bottom")

# Horizontal threshold lines
ax4.axhline(y=THRESHOLD_RED, color="red", linestyle=":", linewidth=0.8, alpha=0.5)
ax4.axhline(y=THRESHOLD_ORANGE, color="orange", linestyle=":", linewidth=0.8, alpha=0.5)

ax4.set_xlabel("Grid step size [mm]")
ax4.set_ylabel("Cells per $\\delta_{90}$")
ax4.set_yscale("log")
ax4.set_ylim(1, 1000)  # Start at 1 (10^0), not below
ax4.set_xlim(0, 9)  # Will be inverted later

# Panel label in TOP RIGHT
ax4.text(0.98, 0.95, "(d)", transform=ax4.transAxes, fontweight="bold", va="top", ha="right")

# Need to set autoscale for LineCollection
ax4.autoscale_view()

# ============================================================================
# Common x-axis settings
# ============================================================================
# Set log scale - smallest values on left (standard convention)
for ax in axes:
    ax.set_xscale("log")
    ax.set_xlim(left=x_min, right=x_max)  # Standard: small to large

# Tight layout
plt.tight_layout()

# Save the figure
plt.savefig("analysis/gridding_justification/gridding_justification_combined.pdf")
plt.savefig("analysis/gridding_justification/gridding_justification_combined.png", dpi=300)

print("Saved: gridding_justification_combined.pdf and .png")

# Show the plot
plt.show()
