"""
Recreate the SAM Head & Hand with Phone - CUDA vs aXware performance plot.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Read the data
df = pd.read_csv("performance_data.csv")

# Define colors for each GPU configuration
colors = {
    "1 x GTX 750 Ti": {"CUDA": "red", "aXware": "purple"},
    "1 x GTX 1070": {"CUDA": "green", "aXware": None},
    "1 x K80 (2)": {"CUDA": "olive", "aXware": "darkgoldenrod"},
    "1 x Titan": {"CUDA": "orange", "aXware": "darkorange"},
    "2 x Titan": {"CUDA": "blue", "aXware": "dodgerblue"},
    "4 x Titan": {"CUDA": "black", "aXware": "black"},
    "8 x Titan": {"CUDA": "magenta", "aXware": "magenta"},
}

# Define markers
cuda_marker = "s"  # square
axware_marker = "o"  # circle for aXware (but we use different styles)

# Create figure
fig, ax = plt.subplots(figsize=(12, 8))

# Plot each series
series_list = df["series"].unique()

for series in series_list:
    for backend in ["CUDA", "aXware"]:
        subset = df[(df["series"] == series) & (df["backend"] == backend)]
        if len(subset) == 0:
            continue

        color = colors.get(series, {}).get(backend, "gray")
        if color is None:
            continue

        # Sort by grid size for proper line drawing
        subset = subset.sort_values("grid_size_mcells")

        # Determine line style
        if backend == "CUDA":
            linestyle = "-"
            marker = "s"
        else:  # aXware
            linestyle = "--"
            marker = "o"

        label = f"{series} {backend}"

        ax.plot(
            subset["grid_size_mcells"],
            subset["average_speed_mcells_s"],
            marker=marker,
            linestyle=linestyle,
            color=color,
            label=label,
            markersize=8,
            linewidth=2,
        )

# Configure axes
ax.set_xlabel("Grid Size [MCells]", fontsize=12, fontweight="bold")
ax.set_ylabel("Average Speed [MCells/s]", fontsize=12, fontweight="bold")
ax.set_title("SAM Head & Hand with Phone - CUDA vs aXware", fontsize=14, fontweight="bold")

# Set axis limits
ax.set_xlim(0, 2200)
ax.set_ylim(0, 17000)

# Configure x-axis ticks
ax.xaxis.set_major_locator(ticker.MultipleLocator(200))
ax.yaxis.set_major_locator(ticker.MultipleLocator(2000))

# Format y-axis with thousands separator
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: format(int(x), ",")))

# Add grid
ax.grid(True, linestyle="-", alpha=0.3)

# Add legend
ax.legend(loc="lower right", fontsize=9, framealpha=0.9)

# Tight layout
plt.tight_layout()

# Save the figure
plt.savefig("recreated_plot.png", dpi=150, bbox_inches="tight", facecolor="white")
print("Plot saved to recreated_plot.png")

plt.show()
