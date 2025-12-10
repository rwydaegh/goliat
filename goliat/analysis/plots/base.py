"""Base plotter class with shared utilities and constants."""

import logging
import os
import re
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import pandas as pd

# Apply scienceplots style for academic-looking plots with IEEE standards
# Use 'no-latex' to avoid slow rendering, but LaTeX notation in strings still works for units
try:
    import scienceplots  # noqa: F401

    plt.style.use(["science", "ieee", "no-latex"])

    # IEEE standard font sizes (9pt base, 8pt for ticks/legend, 10pt for titles)
    # Smaller markers globally
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
    logging.getLogger("progress").warning(
        "SciencePlots not available. Install with: pip install scienceplots",
        extra={"log_type": "warning"},
    )
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
            "lines.markersize": 4,  # Smaller default marker size
            "lines.markeredgewidth": 0.5,  # Thinner marker edges
            "scatter.marker": "o",  # Default scatter marker
        }
    )

if TYPE_CHECKING:
    pass

# Metric labels for plot titles and legends
METRIC_LABELS = {
    "SAR_head": "Head SAR",
    "SAR_trunk": "Trunk SAR",
    "SAR_whole_body": "Whole-Body SAR",
    "SAR_eyes": "Eyes SAR",
    "SAR_brain": "Brain SAR",
    "SAR_skin": "Skin SAR",
    "SAR_genitals": "Genitals SAR",
    "psSAR10g_eyes": "psSAR10g Eyes",
    "psSAR10g_skin": "psSAR10g Skin",
    "psSAR10g_brain": "psSAR10g Brain",
    "psSAR10g_genitals": "psSAR10g Genitals",
    "psSAR10g_whole_body": "psSAR10g Whole Body",
    "peak_sar": "Peak SAR (10g)",
}

LEGEND_LABELS = {
    "psSAR10g_eyes": "Eyes",
    "psSAR10g_skin": "Skin",
    "psSAR10g_brain": "Brain",
    "psSAR10g_genitals": "Genitals",
    "psSAR10g_whole_body": "Whole Body",
    # SAR legend labels (trimmed - remove "SAR" since it's in axis/title)
    "SAR_head": "Head",
    "SAR_trunk": "Trunk",
    "SAR_whole_body": "Whole-Body",
    "SAR_eyes": "Eyes",
    "SAR_brain": "Brain",
    "SAR_skin": "Skin",
    "SAR_genitals": "Genitals",
}


class BasePlotter:
    """Base class for plot modules with shared utilities.

    Provides common helper methods for subdirectory management, data filtering,
    and title generation.
    """

    def __init__(self, plots_dir: str, phantom_name: str | None = None, plot_format: str = "pdf"):
        """Initialize base plotter.

        Args:
            plots_dir: Directory where all plots will be saved.
            phantom_name: Optional phantom model name for titles.
            plot_format: Output format for plots ('pdf' or 'png'), default 'pdf'.
        """
        self.plots_dir = plots_dir
        self.phantom_name = phantom_name
        self.plot_format = plot_format

    def _get_subdir(self, subdir_name: str) -> str:
        """Creates and returns a subdirectory path for organizing plots.

        Args:
            subdir_name: Name of the subdirectory (e.g., 'spatial', 'correlation').

        Returns:
            Full path to the subdirectory.
        """
        subdir_path = os.path.join(self.plots_dir, subdir_name)
        os.makedirs(subdir_path, exist_ok=True)
        return subdir_path

    def _filter_all_regions(self, df: pd.DataFrame, tissue_column: str = "tissue") -> pd.DataFrame:
        """Filters out 'All Regions' from tissue dataframes.

        'All Regions' is a whole-body aggregate, not a real tissue, so it should
        be excluded from most tissue-level analyses to avoid double-counting.

        Args:
            df: DataFrame with tissue data.
            tissue_column: Name of the column containing tissue names.

        Returns:
            DataFrame with 'All Regions' rows removed.
        """
        if tissue_column not in df.columns:
            return df
        return df[df[tissue_column] != "All Regions"].copy()

    def _clean_tissue_name(self, tissue_name: str) -> str:
        """Removes redundant phantom identifiers from tissue names.

        NOTE: Tissue names are cleaned early during data extraction (in extract_data methods).
        This method is kept as a safety net, but should mostly be a no-op.

        Args:
            tissue_name: Original tissue name (may contain phantom identifier).

        Returns:
            Cleaned tissue name without redundant phantom identifier.
        """
        if not tissue_name:
            return tissue_name

        # Remove common phantom identifier patterns like "(Thelonious_6y_V6)", "(Thelonious_by_V6)", etc.
        # Pattern matches: (PhantomName_...) or (PhantomName) at the end
        pattern = r"\s*\([^)]*\)\s*$"
        cleaned = re.sub(pattern, "", tissue_name).strip()
        return cleaned if cleaned else tissue_name

    def _format_organ_name(self, organ_name: str) -> str:
        """Formats organ/tissue name for display (replaces underscores, capitalizes properly).

        Converts organ names with underscores to human-readable form.
        Preserves acronyms like SAR, SAT, psSAR10g, etc.

        Args:
            organ_name: Raw organ/tissue name (e.g., 'brain_tissue', 'SAT_(orig)', 'left_eye', 'psSAR10g_eyes').

        Returns:
            Formatted organ name (e.g., 'Brain Tissue', 'SAT (orig)', 'Left Eye', 'psSAR10g Eyes').
        """
        if not organ_name:
            return organ_name

        # First fix any incorrect psSAR10g capitalization
        organ_name = organ_name.replace("Pssar10g", "psSAR10g").replace("Pssar", "psSAR")

        # First clean phantom identifiers if present
        cleaned = self._clean_tissue_name(organ_name)

        # Replace underscores with spaces
        formatted = cleaned.replace("_", " ")

        # Split into words and capitalize each word, but preserve acronyms
        words = formatted.split()
        formatted_words = []

        for word in words:
            # Preserve psSAR10g exactly as is
            if word.lower() == "pssar10g" or word == "psSAR10g":
                formatted_words.append("psSAR10g")
            # Check if word is an acronym (all caps, possibly with numbers)
            elif word.startswith("(") and word.endswith(")"):
                formatted_words.append(word)
            elif word.isupper() and len(word) > 1:
                # Preserve acronyms like SAR, SAT, etc.
                formatted_words.append(word)
            elif word.replace("(", "").replace(")", "").isupper() and len(word.replace("(", "").replace(")", "")) > 1:
                # Handle cases like "(orig)" or "(ORIG)"
                formatted_words.append(word)
            else:
                # Capitalize normally
                formatted_words.append(word.capitalize())

        return " ".join(formatted_words)

    def _format_scenario_name(self, scenario_name: str) -> str:
        """Formats scenario name for display (replaces underscores, capitalizes properly).

        Handles complex names like 'by_belly_right_vertical' -> 'By Belly Right Vertical'.

        Args:
            scenario_name: Raw scenario name (e.g., 'by_belly', 'front_of_eyes', 'by_belly_right_vertical').

        Returns:
            Formatted scenario name (e.g., 'By Belly', 'Front of Eyes', 'By Belly Right Vertical').
        """
        if not scenario_name:
            return scenario_name
        # Replace underscores with spaces and title case
        # This handles all cases: by_belly -> By Belly, by_belly_right_vertical -> By Belly Right Vertical
        formatted = scenario_name.replace("_", " ").title()
        return formatted

    def _format_axis_label(self, label: str, unit: str | None = None) -> str:
        """Formats axis labels with consistent unit notation.

        Args:
            label: Base label text (e.g., 'Frequency', 'SAR').
            unit: Optional unit string (e.g., 'MHz', 'mW kg⁻¹').

        Returns:
            Formatted label with unit in parentheses if provided.
        """
        if unit:
            return f"{label} ({unit})"
        return label

    def _get_academic_colors(self, n_colors: int) -> list:
        """Returns a list of academic colors in order: black, red, dark blue, then others.

        No yellow or green tones. Colors cycle if more than available colors are requested.

        Args:
            n_colors: Number of colors needed.

        Returns:
            List of color strings/hex codes.
        """
        # Academic color palette: black, pure red, pure dark blue, then other academic colors
        # No yellow or green tones
        base_colors = [
            "black",  # 0: black
            "red",  # 1: pure red
            "#00008B",  # 2: dark blue (pure dark blue)
            "purple",  # 3: purple
            "orange",  # 4: orange
            "brown",  # 5: brown
            "pink",  # 6: pink
            "gray",  # 7: gray
            "cyan",  # 8: cyan
            "magenta",  # 9: magenta
            "#8B0000",  # 10: dark red
            "#4B0082",  # 11: indigo
            "#800080",  # 12: darker purple
            "#FF4500",  # 13: orange red
            "#A52A2A",  # 14: darker brown
        ]

        # Cycle colors if more are needed
        if n_colors <= len(base_colors):
            return base_colors[:n_colors]
        else:
            # Repeat colors if more needed
            colors = []
            for i in range(n_colors):
                colors.append(base_colors[i % len(base_colors)])
            return colors

    def _get_academic_linestyles(self, n_styles: int) -> list:
        """Returns a list of academic/professional linestyles for publication-quality plots.

        Linestyles cycle if more than available are requested.

        Args:
            n_styles: Number of linestyles needed.

        Returns:
            List of linestyle specifications.
        """
        base_linestyles = [
            "solid",  # 0: solid
            "dashed",  # 1: dashed
            "dotted",  # 2: dotted
            "dashdot",  # 3: dash-dot
            (0, (5, 1)),  # 4: densely dashed (5pt dash, 1pt gap)
            (0, (3, 1, 1, 1)),  # 5: dash-dot-dot
            (0, (1, 1)),  # 6: densely dotted
            (0, (5, 2, 1, 2)),  # 7: dash-dot with wider gaps
            (0, (3, 3)),  # 8: loosely dashed
            (0, (1, 2)),  # 9: loosely dotted
        ]

        if n_styles <= len(base_linestyles):
            return base_linestyles[:n_styles]
        else:
            linestyles = []
            for i in range(n_styles):
                linestyles.append(base_linestyles[i % len(base_linestyles)])
            return linestyles

    def _get_academic_markers(self, n_markers: int) -> list:
        """Returns a list of academic/professional markers for publication-quality plots.

        Markers cycle if more than available are requested.

        Args:
            n_markers: Number of markers needed.

        Returns:
            List of marker specifications.
        """
        base_markers = [
            "o",  # 0: circle
            "s",  # 1: square
            "^",  # 2: triangle up
            "D",  # 3: diamond
            "v",  # 4: triangle down
            "p",  # 5: pentagon
            "h",  # 6: hexagon
            "*",  # 7: star
            "X",  # 8: x (filled)
            "P",  # 9: plus (filled)
        ]

        if n_markers <= len(base_markers):
            return base_markers[:n_markers]
        else:
            markers = []
            for i in range(n_markers):
                markers.append(base_markers[i % len(base_markers)])
            return markers

    def _get_title_with_phantom(self, base_title: str, scenario_name: str | None = None) -> str:
        """Creates a plot title with phantom name and optional scenario.

        Formats as complete sentence starting with "The", no parentheses/dashes, no period at end.
        Formats scenario names properly (replaces underscores).

        Args:
            base_title: Base title for the plot (will be formatted as complete sentence).
            scenario_name: Optional scenario name to append (will be formatted).

        Returns:
            Formatted title with phantom name and scenario.
        """
        # Ensure title starts with "The" and is a complete sentence
        if base_title:
            # Remove any existing "The" at start
            base_title = base_title.strip()
            if base_title.lower().startswith("the "):
                base_title = base_title[4:].strip()
            # Remove parentheses, dashes, colons, and periods, replace underscores with spaces
            base_title = (
                base_title.replace("(", "").replace(")", "").replace("-", " ").replace(":", " ").replace("_", " ").replace(".", "").strip()
            )
            # Clean up multiple spaces
            base_title = re.sub(r"\s+", " ", base_title)
            # Capitalize first letter and add "The" at start
            base_title = "The " + (base_title[0].upper() + base_title[1:] if len(base_title) > 1 else base_title.upper())

        title_parts = [base_title]
        if self.phantom_name:
            # Capitalize phantom name
            phantom_capitalized = self.phantom_name.capitalize()
            title_parts.append(f"({phantom_capitalized})")
        if scenario_name:
            formatted_scenario = self._format_scenario_name(scenario_name)
            title_parts.append(f"- {formatted_scenario}")
        return " ".join(title_parts)

    def _save_caption_file(self, subdir: str, filename_base: str, title: str, caption: str = ""):
        """Saves a caption file (txt) with title and caption for a plot.

        Args:
            subdir: Subdirectory name (e.g., 'bar', 'line').
            filename_base: Base filename without extension (matches plot filename).
            title: Plot title.
            caption: Optional caption text.
        """
        subdir_path = self._get_subdir(subdir)
        caption_filename = f"{filename_base}.txt"
        caption_path = os.path.join(subdir_path, caption_filename)

        with open(caption_path, "w", encoding="utf-8") as f:
            f.write(f"Title: {title}\n\n")
            if caption:
                f.write(f"Caption: {caption}\n")

    def _save_figure(self, fig, subdir: str, filename_base: str, title: str = "", caption: str = "", dpi: int = 300):
        """Saves a figure in the specified format (PDF or PNG) and creates a caption file.

        Args:
            fig: Matplotlib figure object.
            subdir: Subdirectory name (e.g., 'bar', 'line').
            filename_base: Base filename without extension.
            title: Plot title (for caption file).
            caption: Optional caption text (for caption file).
            dpi: Resolution for PNG format (default: 300).
        """
        subdir_path = self._get_subdir(subdir)
        if self.plot_format == "pdf":
            filename = f"{filename_base}.pdf"
            filepath = os.path.join(subdir_path, filename)
        else:
            filename = f"{filename_base}.png"
            filepath = os.path.join(subdir_path, filename)

        try:
            if self.plot_format == "pdf":
                fig.savefig(filepath, bbox_inches="tight", format="pdf")
            else:
                fig.savefig(filepath, dpi=dpi, bbox_inches="tight")
        except PermissionError:
            logging.getLogger("progress").error(
                f"  - ERROR: Cannot save {filename} - file is likely open in another program. Please close it and try again.",
                extra={"log_type": "error"},
            )
            plt.close(fig)
            raise
        except Exception as e:
            logging.getLogger("progress").error(
                f"  - ERROR: Failed to save {filename}: {str(e)}",
                extra={"log_type": "error"},
            )
            plt.close(fig)
            raise

        # Save caption file
        if title:
            self._save_caption_file(subdir, filename_base, title, caption)

        plt.close(fig)
        return filename

    def _adjust_slanted_tick_labels(self, ax, rotation: float = 45.0) -> None:
        """Adjusts the position of the '835' x-tick label when both '700' and '835' are present.

        When x-tick labels are slanted at 45 degrees and both '700' and '835' frequency
        labels are present, they can overlap. This method shifts the '835' label slightly
        to the right to avoid the overlap.

        Args:
            ax: Matplotlib axes object.
            rotation: Expected rotation angle for x-tick labels (default: 45.0).
        """
        # Get current x-tick labels
        tick_labels = ax.get_xticklabels()
        if not tick_labels:
            return

        # Check if labels are rotated (approximately 45 degrees)
        first_label = tick_labels[0]
        label_rotation = first_label.get_rotation()
        if abs(label_rotation - rotation) > 5:  # Allow some tolerance
            return

        # Extract label texts
        label_texts = [label.get_text() for label in tick_labels]

        # Check if both '700' and '835' are present (can be just the number or with text like '700\n(5/6)')
        has_700 = any("700" in str(text) for text in label_texts)
        has_835 = any("835" in str(text) for text in label_texts)

        if not (has_700 and has_835):
            return

        # Find the '835' label and shift it to the right
        for label in tick_labels:
            label_text = label.get_text()
            if "835" in str(label_text):
                # Get current position
                current_pos = label.get_position()
                # Shift slightly to the right (positive x direction)
                # The shift amount is small - about 0.15 units on the x-axis
                label.set_position((current_pos[0] + 0.15, current_pos[1]))

    def _save_csv_data(self, data_df: pd.DataFrame, subdir: str, filename_base: str):
        """Saves plot data to CSV file.

        Args:
            data_df: DataFrame containing the plot data.
            subdir: Subdirectory name (e.g., 'bar', 'line').
            filename_base: Base filename without extension.
        """
        subdir_path = self._get_subdir(subdir)
        csv_filename = f"{filename_base}.csv"
        csv_filepath = os.path.join(subdir_path, csv_filename)
        try:
            data_df.to_csv(csv_filepath, index=True)
        except Exception as e:
            logging.getLogger("progress").warning(
                f"  - WARNING: Failed to save CSV {csv_filename}: {str(e)}",
                extra={"log_type": "warning"},
            )
