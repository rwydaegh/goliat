"""Recreate the penetration ratio SAR vs frequency plot.

This script recreates the plot from the existing CSV data with the same
scienceplots styling used in the GOLIAT analysis pipeline.
"""

import pandas as pd
import matplotlib.pyplot as plt

# Apply scienceplots style for academic-looking plots with IEEE standards
try:
    import scienceplots  # noqa: F401
    
    plt.style.use(["science", "ieee", "no-latex"])
    
    # IEEE standard font sizes (9pt base, 8pt for ticks/legend, 10pt for titles)
    plt.rcParams.update(
        {
            "font.size": 9,  # Base font size (IEEE recommends 9pt)
            "axes.titlesize": 9,  # Axes title size
            "axes.labelsize": 9,  # Axes labels size
            "xtick.labelsize": 8,  # X-axis tick labels size
            "ytick.labelsize": 8,  # Y-axis tick labels size
            "legend.fontsize": 8,  # Legend font size
            "figure.titlesize": 10,  # Figure title size (suptitle)
            "lines.markersize": 4,  # Smaller default marker size
            "lines.markeredgewidth": 0.5,  # Thinner marker edges
            "scatter.marker": "o",  # Default scatter marker
            "axes.prop_cycle": plt.cycler(
                "color", ["black", "red", "#00008B", "purple", "orange", "brown", "pink", "gray", "cyan", "magenta"]
            ),  # Custom academic colors: black, red, dark blue, then others
        }
    )
except ImportError:
    print("Warning: SciencePlots not available. Install with: pip install scienceplots")
    # Fallback: set IEEE-compliant font sizes even without scienceplots
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 9,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "figure.titlesize": 10,
            "lines.markersize": 4,
            "lines.markeredgewidth": 0.5,
            "scatter.marker": "o",
        }
    )


def main():
    # Define phantoms and their display names
    phantoms = {
        "duke": "Duke",
        "eartha": "Eartha",
        "ella": "Ella",
        "thelonious": "Thelonious"
    }
    
    # Academic color palette (black, red, dark blue, purple)
    colors = ["black", "red", "#00008B", "purple"]
    
    # Markers for each phantom
    markers = ["o", "s", "^", "D"]
    
    # Alternating line styles
    line_styles = ["solid", "dashed", "dotted", "dashdot"]
    
    # Create figure with IEEE single-column width
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    
    # Load and plot data for each phantom
    for idx, (phantom_key, phantom_name) in enumerate(phantoms.items()):
        csv_path = rf"plots\far_field\{phantom_key}\penetration\penetration_ratio_SAR_vs_frequency_all.csv"
        data = pd.read_csv(csv_path, index_col=0)
        
        # Plot with academic styling (thinner lines and alternating styles)
        ax.plot(
            data["frequency_mhz"],
            data["penetration_ratio"],
            marker=markers[idx],
            linestyle=line_styles[idx],
            color=colors[idx],
            linewidth=1.5,
            markersize=4,
            label=phantom_name,
        )
    
    # Set axis labels
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Ratio (SAR Brain / SAR Skin)")
    
    # Set y-axis to log scale
    ax.set_yscale("log")
    
    # Rotate x-axis labels for better readability
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    
    # Add grid
    ax.grid(True, which="both", ls="--", alpha=0.3)
    
    # Add clean legend with 1pt black box, no rounded corners
    legend = ax.legend(
        frameon=True,
        edgecolor="black",
        fancybox=False,  # No rounded corners
        framealpha=1.0,
        loc="best"
    )
    legend.get_frame().set_linewidth(1.0)  # 1pt border
    
    # Tight layout to prevent label cutoff
    plt.tight_layout()
    
    # Save the figure
    output_dir = r"plots\far_field"
    plt.savefig(f"{output_dir}\\penetration_ratio_all_phantoms.pdf", bbox_inches="tight")
    plt.savefig(f"{output_dir}\\penetration_ratio_all_phantoms.png", dpi=300, bbox_inches="tight")
    
    print(f"Plot saved to {output_dir}\\penetration_ratio_all_phantoms.pdf")
    print(f"Plot saved to {output_dir}\\penetration_ratio_all_phantoms.png")
    
    # Show the plot
    plt.show()


if __name__ == "__main__":
    main()
