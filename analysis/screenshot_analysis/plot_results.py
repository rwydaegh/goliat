import pandas as pd
import matplotlib.pyplot as plt
import scienceplots

# Set plot style for a scientific paper look
plt.style.use("science")

# Load the data from the CSV file
data = pd.read_csv("analysis/screenshot_analysis/results.csv")

# Create a figure and axis object
fig, ax = plt.subplots()
ax.grid(True, which="major", axis="x", linestyle="--")

# Filter out zero perforation points for plotting and labeling
plot_data = data[data["perforation"] > 0].copy()
ax.plot(
    plot_data["grid_size"],
    plot_data["perforation"],
    "o-",
    label="Perforation",
    markersize=4,
)

# Add labels to each point
for i, row in plot_data.iterrows():
    if row["perforation"] > 13.1:
        # Position text above the point
        ax.text(
            row["grid_size"],
            row["perforation"] * 1.2,
            f"{row['perforation']:.2f}\%",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    else:
        # Position text to the right of the point
        ax.text(
            row["grid_size"] + 0.15,
            row["perforation"],
            f"{row['perforation']:.2f}\%",
            ha="left",
            va="center",
            fontsize=8,
        )

# Set the labels for the axes
ax.set_xlabel("Grid step size [mm]")
ax.set_ylabel("Perforation [\%]")

# Set y-axis to log scale
ax.set_yscale("log")

# Adjust y-axis limits to see the lowest point
ax.set_ylim(bottom=0.8, top=200)

# Set the zero perforation line at 1.5
zero_perforation_point = 1.5

# Add a vertical line and shaded region
ax.axvline(x=zero_perforation_point, color="k", linestyle="--", linewidth=1)
ax.axvspan(zero_perforation_point, 0, facecolor="gray", alpha=0.2)
ax.text(
    zero_perforation_point / 2,
    2,
    r"\textbf{No perforation}",
    rotation=90,
    verticalalignment="bottom",
    ha="center",
    fontsize=10,
)


# Invert the x-axis and set limits
ax.set_xlim(left=data["grid_size"].max() + 0.5, right=0)
ax.invert_xaxis()

# Save the figure
plt.savefig("analysis/screenshot_analysis/perforation_vs_grid_size.pdf")
plt.savefig("analysis/screenshot_analysis/perforation_vs_grid_size.png", dpi=300)


# Show the plot
plt.show()
