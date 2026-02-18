#!/usr/bin/env python3
"""Auto-induced exposure analysis strategy.

Generates publication-ready plots for auto-induced far-field exposure results.
Follows the same styling conventions as far_field_strategy.py for consistency.

Outputs:
    - plots/auto_induced/ - All generated figures
    - paper/auto_induced/pure_results/results.tex - Auto-generated LaTeX file

Usage:
    # From command line (after source .bashrc):
    cd goliat && python -m goliat.analysis.auto_induced_strategy

    # Or import and use programmatically:
    from goliat.analysis.auto_induced_strategy import AutoInducedAnalyzer
    analyzer = AutoInducedAnalyzer(results_dir, output_dir, plot_format="png")
    analyzer.run_analysis()
"""

import json
import logging
import os
import warnings
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from scipy.optimize import curve_fit

# Suppress matplotlib thread warning
warnings.filterwarnings("ignore", message=".*Starting a Matplotlib GUI outside of the main thread.*")

# Apply scienceplots style for academic-looking plots with IEEE standards
# Use LaTeX rendering for proper Computer Modern fonts matching IEEE papers
# Font sizes are NOT explicitly set - the IEEE style + 3.5" figure width
# naturally produces fonts that match IEEE paper body text when imported
try:
    import scienceplots  # noqa: F401

    plt.style.use(["science", "ieee"])  # No "no-latex" - we want LaTeX fonts!
    plt.rcParams.update(
        {
            # Only set non-font styling options
            "lines.markersize": 4,
            "lines.markeredgewidth": 0.5,
            "scatter.marker": "o",
            "axes.prop_cycle": plt.cycler(
                "color", ["black", "red", "#00008B", "purple", "orange", "brown", "pink", "gray", "cyan", "magenta"]
            ),
        }
    )
except ImportError:
    # Fallback without scienceplots - use serif font to approximate LaTeX look
    plt.rcParams.update(
        {
            "font.family": "serif",
            "lines.markersize": 4,
            "lines.markeredgewidth": 0.5,
            "scatter.marker": "o",
        }
    )

if TYPE_CHECKING:
    pass

# =============================================================================
# CONSTANTS (matching far_field_strategy conventions)
# =============================================================================

# Phantom labels matching far_field_strategy styling (with demographics)
PHANTOM_LABELS = {
    "duke": "Duke (34y M)",
    "ella": "Ella (26y F)",
    "eartha": "Eartha (8y F)",
    "thelonious": "Thelonious (6y M)",
}

# Simple phantom names (without demographics) for cleaner plots
PHANTOM_NAMES = {
    "duke": "Duke",
    "ella": "Ella",
    "eartha": "Eartha",
    "thelonious": "Thelonious",
}

# Academic color palette: black, red, dark blue, purple (matching base.py)
PHANTOM_COLORS = {
    "duke": "black",
    "ella": "red",
    "eartha": "#00008B",  # dark blue
    "thelonious": "purple",
}

# Frequency colors using academic color scheme for consistency
FREQUENCY_COLORS = {
    7: "black",  # darkest frequency
    9: "red",  #
    11: "#00008B",  # dark blue
    13: "purple",  #
    15: "orange",  # highest frequency
}

# IEEE figure sizes
IEEE_SINGLE_COLUMN_WIDTH = 3.5  # inches
IEEE_DOUBLE_COLUMN_WIDTH = 7.0  # inches

# Section mapping for better results.tex organization
SECTION_MAPPING = {
    "heatmap": "Key Results",
    "correlation": "Model Validation",
    "distribution": "Distribution Analysis",
    "spatial": "Spatial Visualization",
    "body_position": "Phantom-Specific Analysis",
    "supplementary_distributions": "Supplementary: Per-Condition Distributions",
    "compliance": "Regulatory Compliance",
    "statistics": "Statistical Summary",
}

# Body region Z ranges for Duke (approximate mm from feet)
BODY_REGIONS = {
    "Head": (850, 1000),
    "Neck/Shoulders": (750, 850),
    "Torso": (400, 750),
    "Pelvis": (300, 400),
    "Arms": None,  # Detected by x-coordinate
    "Hands": None,  # High curvature regions
    "Legs": (50, 300),
    "Feet": (0, 50),
}


# =============================================================================
# MAIN ANALYZER CLASS
# =============================================================================


class AutoInducedAnalyzer:
    """Analyzer for auto-induced exposure results.

    Loads data from FR3 auto-induced results and generates publication-ready plots
    following the same conventions as FarFieldAnalysisStrategy.
    """

    def __init__(
        self,
        results_dir: str | Path,
        output_dir: str | Path,
        plot_format: str = "png",
        paper_dir: str | Path | None = None,
    ):
        """Initialize the auto-induced analyzer.

        Args:
            results_dir: Path to results/auto_induced_FR3 directory.
            output_dir: Path to save output plots (plots/auto_induced/).
            plot_format: Output format ('png' or 'pdf'), default 'png'.
            paper_dir: Path to paper output directory for results.tex.
        """
        self.results_dir = Path(results_dir)
        self.output_dir = Path(output_dir)
        self.plot_format = plot_format
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Paper directory for results.tex
        if paper_dir:
            self.paper_dir = Path(paper_dir)
        else:
            # Default: paper/auto_induced/pure_results/
            self.paper_dir = self.output_dir.parent.parent / "paper" / "auto_induced" / "pure_results"
        self.paper_dir.mkdir(parents=True, exist_ok=True)

        # Data containers
        self.proxy_df: pd.DataFrame = pd.DataFrame()
        self.candidate_df: pd.DataFrame = pd.DataFrame()
        self.model: dict = {}  # Linear model: SAPD = alpha * HS + beta
        self.exp_model: dict = {}  # Exponential model: std = a * exp(-b * f) + c

        # Track generated figures for results.tex
        self.generated_figures: list[dict] = []

        # Logger
        self.logger = logging.getLogger("progress")

    # =========================================================================
    # DATA LOADING
    # =========================================================================

    def load_data(self) -> None:
        """Load all auto-induced results data."""
        self.logger.info("Loading auto-induced data...")

        # Load proxy scores
        self._load_proxy_scores()

        # Load candidate data
        self._load_candidates()

        # Load or compute linear model
        self._load_or_compute_model()

        self.logger.info(f"Loaded {len(self.proxy_df):,} proxy scores, {len(self.candidate_df)} candidates")

    def _load_proxy_scores(self) -> None:
        """Load all proxy scores from all frequency/phantom combinations."""
        all_scores = []

        for freq_folder in sorted(self.results_dir.iterdir()):
            if not freq_folder.is_dir() or not freq_folder.name.endswith("GHz"):
                continue

            freq_ghz = int(freq_folder.name.replace("GHz", ""))

            for phantom_folder in freq_folder.iterdir():
                if not phantom_folder.is_dir():
                    continue

                proxy_csv = phantom_folder / "auto_induced" / "all_proxy_scores.csv"
                if proxy_csv.exists():
                    df = pd.read_csv(proxy_csv)
                    df["freq_ghz"] = freq_ghz
                    df["phantom"] = phantom_folder.name
                    # Normalize proxy_score from E=1V/m to E=27.46V/m (1 W/m² incident)
                    # proxy_score is |E|² in V²/m², so multiply by 754
                    if "proxy_score" in df.columns:
                        df["proxy_score"] = df["proxy_score"] * 754
                    all_scores.append(df)

        if all_scores:
            self.proxy_df = pd.concat(all_scores, ignore_index=True)

    def _load_candidates(self) -> None:
        """Load all candidate data with SAPD values."""
        all_candidates = []

        for freq_folder in sorted(self.results_dir.iterdir()):
            if not freq_folder.is_dir() or not freq_folder.name.endswith("GHz"):
                continue

            freq_ghz = int(freq_folder.name.replace("GHz", ""))

            for phantom_folder in freq_folder.iterdir():
                if not phantom_folder.is_dir():
                    continue

                # Load from proxy_sapd_correlation.csv (the correct file)
                candidates_csv = phantom_folder / "auto_induced" / "proxy_sapd_correlation.csv"
                if candidates_csv.exists():
                    df = pd.read_csv(candidates_csv)
                    df["freq_ghz"] = freq_ghz
                    df["phantom"] = phantom_folder.name
                    # Normalize all values from E=1V/m to 1 W/m² incident power density
                    # Multiply by 754 (see docs/technical/power_normalization_philosophy.md)
                    if "sapd_w_m2" in df.columns:
                        df["peak_sapd"] = df["sapd_w_m2"] * 754  # W/m² at 1 W/m² incident
                    if "proxy_score" in df.columns:
                        df["proxy_score"] = df["proxy_score"] * 754  # V²/m² at 1 W/m² incident
                    if "distance_to_skin_mm" in df.columns:
                        df["distance_to_skin"] = df["distance_to_skin_mm"]
                    all_candidates.append(df)

        if all_candidates:
            self.candidate_df = pd.concat(all_candidates, ignore_index=True)

    def _load_or_compute_model(self) -> None:
        """Load linear model parameters or compute them from data."""
        model_path = self.output_dir / "linear_model_parameters.json"

        if not self.candidate_df.empty:
            # Always recompute linear model: SAPD = alpha * hotspot_score + beta
            x = self.candidate_df["proxy_score"].values
            y = self.candidate_df["peak_sapd"].values

            mask = ~np.isnan(x) & ~np.isnan(y)
            x, y = x[mask], y[mask]

            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

            self.model = {
                "slope_alpha": float(slope),
                "intercept_beta": float(intercept),
                "r_squared": float(r_value**2),
                "r_value": float(r_value),
                "p_value": float(p_value),
                "std_err": float(std_err),
            }

            # Save model
            with open(model_path, "w") as f:
                json.dump(self.model, f, indent=2)
        elif model_path.exists():
            with open(model_path) as f:
                self.model = json.load(f)
        else:
            # Default model if no data
            self.model = {"slope_alpha": 5.03, "intercept_beta": 0.21, "r_squared": 0.791}

    # =========================================================================
    # HELPER METHODS (matching base.py conventions)
    # =========================================================================

    def _get_subdir(self, subdir_name: str) -> Path:
        """Creates and returns a subdirectory path."""
        subdir_path = self.output_dir / subdir_name
        subdir_path.mkdir(parents=True, exist_ok=True)
        return subdir_path

    def _get_academic_colors(self, n_colors: int) -> list:
        """Returns academic colors matching base.py."""
        base_colors = [
            "black",
            "red",
            "#00008B",
            "purple",
            "orange",
            "brown",
            "pink",
            "gray",
            "cyan",
            "magenta",
        ]
        if n_colors <= len(base_colors):
            return base_colors[:n_colors]
        return [base_colors[i % len(base_colors)] for i in range(n_colors)]

    def _get_academic_markers(self, n_markers: int) -> list:
        """Returns academic markers matching base.py."""
        base_markers = ["o", "s", "^", "D", "v", "p", "h", "*", "X", "P"]
        if n_markers <= len(base_markers):
            return base_markers[:n_markers]
        return [base_markers[i % len(base_markers)] for i in range(n_markers)]

    def _save_figure(
        self,
        fig,
        subdir: str,
        filename_base: str,
        title: str = "",
        caption: str = "",
        dpi: int = 300,
    ) -> str:
        """Saves figure following base.py conventions."""
        subdir_path = self._get_subdir(subdir)
        ext = "pdf" if self.plot_format == "pdf" else "png"
        filepath = subdir_path / f"{filename_base}.{ext}"

        try:
            if self.plot_format == "pdf":
                fig.savefig(filepath, bbox_inches="tight", format="pdf")
            else:
                fig.savefig(filepath, dpi=dpi, bbox_inches="tight")
        except Exception as e:
            self.logger.error(f"Failed to save {filepath}: {e}")
            plt.close(fig)
            raise

        # Save caption file
        if title:
            caption_path = subdir_path / f"{filename_base}.txt"
            with open(caption_path, "w", encoding="utf-8") as f:
                f.write(f"Title: {title}\n\n")
                if caption:
                    f.write(f"Caption: {caption}\n")

        # Track for results.tex
        self.generated_figures.append(
            {
                "filename": str(filepath.relative_to(self.output_dir)),
                "title": title,
                "caption": caption,
                "subdir": subdir,
            }
        )

        plt.close(fig)
        return str(filepath)

    # =========================================================================
    # PLOT GENERATION METHODS
    # =========================================================================

    def run_analysis(self) -> None:
        """Run complete analysis pipeline."""
        self.load_data()

        if self.proxy_df.empty and self.candidate_df.empty:
            self.logger.warning("No data found. Skipping analysis.")
            return

        self.logger.info("Generating plots...")

        # Generate all plots
        self.plot_worst_case_sapd_heatmap()
        self.plot_linear_model()
        self.plot_distribution_spread_fits()
        self.plot_pairplot_top20()
        self.plot_spatial_yz_projection()
        self.plot_individual_distributions_with_inset()
        self.plot_score_vs_body_position_per_phantom()
        self.plot_icnirp_comparison()
        self.plot_icnirp_compliance_heatmap()
        self.plot_icnirp_compliance_by_frequency()

        # Generate results.tex
        self._generate_results_tex()

        self.logger.info(f"Analysis complete. Results saved to: {self.output_dir}")

    def plot_worst_case_sapd_heatmap(self) -> None:
        """Create worst-case SAPD heatmap (phantoms × frequencies)."""
        if self.candidate_df.empty:
            return

        self.logger.info("  - Generating worst-case SAPD heatmap...")

        # Get worst-case (max) SAPD per phantom/frequency
        worst_case = self.candidate_df.groupby(["phantom", "freq_ghz"])["peak_sapd"].max().unstack()

        # Reorder phantoms
        phantom_order = ["duke", "ella", "eartha", "thelonious"]
        worst_case = worst_case.reindex([p for p in phantom_order if p in worst_case.index])

        # Create figure (IEEE single-column width)
        fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COLUMN_WIDTH, 2.5))

        # Create heatmap - vmin=0 to start at 0
        vmax = worst_case.max().max()
        sns.heatmap(
            worst_case,
            annot=True,
            fmt=".2f",
            cmap="Reds",
            vmin=0,
            vmax=vmax,
            cbar_kws={"label": "Peak SAPD (W/m²)"},
            ax=ax,
            linewidths=0.5,
        )

        # Labels - use simple names without age/gender for cleaner heatmap
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel("")
        ax.set_yticklabels([PHANTOM_NAMES.get(p, p) for p in worst_case.index], rotation=0)

        plt.tight_layout()
        self._save_figure(
            fig,
            "heatmap",
            "worst_case_sapd_heatmap",
            title="Worst-Case SAPD by Phantom and Frequency",
            caption="Maximum 4-cm² averaged absorbed power density for each phantom/frequency combination, normalized to 1 W/m² incident power density.",
        )

    def plot_linear_model(self) -> None:
        """Create linear regression plot: hotspot score → SAPD."""
        if self.candidate_df.empty:
            return

        self.logger.info("  - Generating linear model plot...")

        fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COLUMN_WIDTH, 3.0))

        # Scatter points colored by frequency
        frequencies = sorted(self.candidate_df["freq_ghz"].unique())
        markers = self._get_academic_markers(len(frequencies))

        for freq, marker in zip(frequencies, markers):
            data = self.candidate_df[self.candidate_df["freq_ghz"] == freq]
            ax.scatter(
                data["proxy_score"],
                data["peak_sapd"],
                c=FREQUENCY_COLORS.get(freq, "gray"),
                marker=marker,
                s=20,
                alpha=0.7,
                label=f"{freq} GHz",
                edgecolors="white",
                linewidths=0.3,
            )

        # Regression line starting from x=0
        x_max = self.candidate_df["proxy_score"].max()
        x_range = np.linspace(0, x_max * 1.05, 100)
        y_pred = self.model["slope_alpha"] * x_range + self.model["intercept_beta"]
        ax.plot(x_range, y_pred, "k--", linewidth=1.5, label="Linear fit")

        # Annotation
        r2 = self.model.get("r_squared", 0)
        ax.text(
            0.05,
            0.95,
            f"R² = {r2:.3f}\n4-cm$^2$ averaged APD = {self.model['slope_alpha']:.3f}×HS + {self.model['intercept_beta']:.2f}",
            transform=ax.transAxes,
            fontsize=7,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

        # Axes starting at 0
        ax.set_xlim(left=0)
        # SAPD doesn't start at 0 due to intercept term
        ax.set_ylim(bottom=0)

        ax.set_xlabel("Hotspot Score (V²/m²)")
        ax.set_ylabel("Peak 4-cm$^2$ averaged APD (W/m²)")
        ax.legend(fontsize=6, loc="lower right", ncol=2)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        self._save_figure(
            fig,
            "correlation",
            "linear_model_sapd_prediction",
            title="Linear Model: Hotspot Score to 4-cm$^2$ averaged APD Prediction",
            caption=f"Linear regression of peak 4-cm$^2$ averaged APD vs hotspot score across all 400 candidates. R² = {r2:.3f}.",
        )

    def plot_distribution_spread_fits(self) -> None:
        """Create distribution spread analysis with exponential fit."""
        if self.proxy_df.empty:
            return

        self.logger.info("  - Generating distribution spread fits...")

        # Calculate std dev per frequency
        freq_stats = []
        frequencies = sorted(self.proxy_df["freq_ghz"].unique())

        for freq in frequencies:
            data = self.proxy_df[self.proxy_df["freq_ghz"] == freq]["proxy_score"]
            freq_stats.append(
                {
                    "freq_ghz": freq,
                    "std": data.std(),
                    "mean": data.mean(),
                }
            )

        stats_df = pd.DataFrame(freq_stats)

        fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COLUMN_WIDTH, 2.5))

        # Plot data points
        ax.scatter(stats_df["freq_ghz"], stats_df["std"], c="black", s=50, zorder=5)

        # Exponential fit: std = a * exp(-b * f) + c
        def exp_decay(x, a, b, c):
            return a * np.exp(-b * x) + c

        try:
            popt, pcov = curve_fit(
                exp_decay,
                stats_df["freq_ghz"].values,
                stats_df["std"].values,
                p0=[0.5, 0.3, 0.01],
                maxfev=5000,
            )

            x_fit = np.linspace(6.5, 15.5, 100)
            y_fit = exp_decay(x_fit, *popt)
            ax.plot(x_fit, y_fit, "r--", linewidth=1.5, label="Exponential fit")

            # Calculate R²
            y_pred = exp_decay(stats_df["freq_ghz"].values, *popt)
            ss_res = np.sum((stats_df["std"].values - y_pred) ** 2)
            ss_tot = np.sum((stats_df["std"].values - stats_df["std"].mean()) ** 2)
            r2 = 1 - (ss_res / ss_tot)

            # Store exponential model parameters
            self.exp_model = {
                "a": float(popt[0]),
                "b": float(popt[1]),
                "c": float(popt[2]),
                "r_squared": float(r2),
                "formula": "std = a * exp(-b * f) + c",
            }

            # Save to JSON
            exp_model_path = self.output_dir / "exponential_model_parameters.json"
            with open(exp_model_path, "w") as f:
                json.dump(self.exp_model, f, indent=2)

            # Use proper LaTeX formula notation
            ax.text(
                0.95,
                0.95,
                f"$R^2 = {r2:.4f}$\n$\\sigma = {popt[0]:.3f} \\cdot e^{{-{popt[1]:.3f} f}} + {popt[2]:.4f}$",
                transform=ax.transAxes,
                verticalalignment="top",
                horizontalalignment="right",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
            )
        except Exception as e:
            self.logger.warning(f"    - Exponential fit failed: {e}")

        # Axes starting at 0
        ax.set_xlim(left=6)
        ax.set_ylim(bottom=0)

        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel("Hotspot Score Std Dev")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        self._save_figure(
            fig,
            "distribution",
            "distribution_spread_fits",
            title="Frequency-Dependent Distribution Sharpening",
            caption="Standard deviation of hotspot score distributions decreases exponentially with frequency.",
        )

    def plot_pairplot_top20(self) -> None:
        """Create pairplot using only top 20 candidates."""
        if self.candidate_df.empty:
            return

        self.logger.info("  - Generating pairplot (top 20 candidates)...")

        # Select columns
        cols = ["proxy_score", "peak_sapd", "freq_ghz"]
        if "distance_to_skin" in self.candidate_df.columns:
            cols.insert(2, "distance_to_skin")

        plot_df = self.candidate_df[cols + ["phantom"]].copy()

        # Rename columns for cleaner labels with units
        column_labels = {
            "proxy_score": "Hotspot Score (V²/m²)",
            "peak_sapd": "Peak SAPD (W/m²)",
            "distance_to_skin": "Distance to Skin (mm)",
            "freq_ghz": "Frequency (GHz)",
        }
        plot_df = plot_df.rename(columns=column_labels)

        # Map frequency to color using academic colors
        freq_palette = {f: FREQUENCY_COLORS.get(f, "gray") for f in sorted(plot_df["Frequency (GHz)"].unique())}

        g = sns.pairplot(
            plot_df,
            hue="Frequency (GHz)",
            palette=freq_palette,
            diag_kind="kde",
            plot_kws={"alpha": 0.6, "s": 15, "edgecolor": "white", "linewidth": 0.3},
            diag_kws={"linewidth": 1},
            height=1.4,  # Slightly smaller for better fit
        )

        # Move legend below the grid - simple black rectangle style
        # Save handles before removing the legend
        legend_handles = g._legend.legend_handles if hasattr(g._legend, "legend_handles") else g._legend.legendHandles  # type: ignore[union-attr]
        g._legend.remove()  # type: ignore[union-attr]
        g.fig.legend(
            handles=legend_handles,
            labels=[f"{int(f)} GHz" for f in sorted(plot_df["Frequency (GHz)"].unique())],
            loc="lower center",
            bbox_to_anchor=(0.5, -0.08),  # Much lower
            ncol=5,
            frameon=True,
            fontsize=8,
            title="Frequency",
            title_fontsize=9,
            fancybox=False,  # Sharp corners
            edgecolor="black",
            facecolor="white",
        )

        # Adjust layout to make room for legend
        g.fig.subplots_adjust(bottom=0.15)

        self._save_figure(
            g.fig,
            "correlation",
            "pairplot_top20_by_frequency",
            title="Pairplot of Top 20 Candidates by Frequency",
            caption="Pairwise relationships between hotspot score, SAPD, and distance to skin for top 20 candidates per frequency.",
        )

    def plot_spatial_yz_projection(self) -> None:
        """Create YZ (side view) spatial plot for Duke."""
        if self.proxy_df.empty:
            return

        self.logger.info("  - Generating YZ spatial projection...")

        # Filter for Duke at 9 GHz (representative)
        full_data = self.proxy_df[(self.proxy_df["phantom"] == "duke") & (self.proxy_df["freq_ghz"] == 9)].copy()

        if full_data.empty or "y_mm" not in full_data.columns or "z_mm" not in full_data.columns:
            self.logger.warning("    - Missing y_mm or z_mm columns, skipping spatial plot")
            return

        # Get top 5 hotspot locations BEFORE sampling
        top5 = full_data.nlargest(5, "proxy_score")

        # Sample the rest for performance (excluding top 5)
        remaining = full_data.drop(top5.index)
        if len(remaining) > 5000:
            data = remaining.sample(n=5000, random_state=42)
        else:
            data = remaining

        fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COLUMN_WIDTH, 4.0))

        # Scatter plot with vmin=0
        vmax = full_data["proxy_score"].max()
        scatter = ax.scatter(
            data["y_mm"],
            data["z_mm"],
            c=data["proxy_score"],
            cmap="viridis",
            vmin=0,
            vmax=vmax,
            s=2,
            alpha=0.6,
        )

        # Highlight top 5 hotspot locations with red markers and numbered labels
        ax.scatter(
            top5["y_mm"],
            top5["z_mm"],
            c="red",
            s=50,
            marker="*",
            edgecolors="white",
            linewidths=0.5,
            zorder=10,
            label="Top 5 Hotspots",
        )

        # Add numbered labels for top 5
        for i, (_, row) in enumerate(top5.iterrows(), 1):
            ax.annotate(
                str(i),
                (row["y_mm"], row["z_mm"]),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=7,
                fontweight="bold",
                color="red",
            )

        # Colorbar
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label("Hotspot Score (V²/m²)")

        ax.set_xlabel("Y Position (mm)")
        ax.set_ylabel("Z Position (mm)")
        ax.set_aspect("equal")
        ax.legend(loc="upper right", fontsize=7)

        plt.tight_layout()
        self._save_figure(
            fig,
            "spatial",
            "spatial_yz_duke_paper",
            title="YZ Projection: Duke at 9 GHz",
            caption="Side view (YZ plane) of hotspot score distribution for Duke phantom at 9 GHz.",
        )

    def plot_individual_distributions_with_inset(self) -> None:
        """Create individual distribution plots with zoom inset for tails."""
        if self.proxy_df.empty:
            return

        self.logger.info("  - Generating individual distribution plots with insets...")

        frequencies = sorted(self.proxy_df["freq_ghz"].unique())
        phantoms = ["duke", "ella", "eartha", "thelonious"]

        for phantom in phantoms:
            for freq in frequencies:
                data = self.proxy_df[(self.proxy_df["phantom"] == phantom) & (self.proxy_df["freq_ghz"] == freq)]["proxy_score"]

                if data.empty:
                    continue

                fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COLUMN_WIDTH, 2.8))

                # Main histogram with x starting at 0
                bins = np.linspace(0, data.max() * 1.05, 50)
                ax.hist(data, bins=bins, alpha=0.7, color=PHANTOM_COLORS.get(phantom, "gray"), edgecolor="black", linewidth=0.5)

                # Vertical lines
                ax.axvline(data.mean(), color="black", linestyle="-", linewidth=1.5, label=f"Mean: {data.mean():.4f}")
                ax.axvline(data.quantile(0.95), color="red", linestyle="--", linewidth=1, label=f"95th: {data.quantile(0.95):.4f}")
                ax.axvline(data.max(), color="darkgreen", linestyle=":", linewidth=1, label=f"Max: {data.max():.4f}")

                ax.set_xlim(left=0)
                ax.set_ylim(bottom=0)
                ax.set_xlabel("Hotspot Score (V²/m²)")
                ax.set_ylabel("Count")
                ax.legend(fontsize=5, loc="upper right")

                # Inset for tail (top 5%)
                p95 = data.quantile(0.95)
                tail_data = data[data >= p95]

                if len(tail_data) > 10:
                    # Create inset axes
                    axins = inset_axes(ax, width="40%", height="35%", loc="right", borderpad=1.5)

                    # Tail histogram
                    tail_bins = np.linspace(p95, data.max(), 20)
                    axins.hist(
                        tail_data, bins=tail_bins, alpha=0.7, color=PHANTOM_COLORS.get(phantom, "gray"), edgecolor="black", linewidth=0.3
                    )
                    axins.axvline(data.max(), color="darkgreen", linestyle=":", linewidth=1)

                    axins.set_xlim(p95, data.max() * 1.02)
                    axins.set_ylim(bottom=0)
                    axins.set_title("Top 5%", fontsize=6)
                    axins.tick_params(labelsize=5)

                    # Draw box around inset region in main plot
                    ax.axvspan(p95, data.max() * 1.02, alpha=0.1, color="gray")

                plt.tight_layout()

                # Use _save_figure to track in generated_figures
                self._save_figure(
                    fig,
                    "supplementary_distributions",
                    f"dist_{phantom}_{freq}GHz",
                    title=f"Hotspot Score Distribution - {PHANTOM_LABELS.get(phantom, phantom)} at {freq} GHz",
                    caption=f"Distribution of hotspot scores for {PHANTOM_LABELS.get(phantom, phantom)} at {freq} GHz. Inset shows top 5% tail.",
                )

        self.logger.info(f"  Saved {len(frequencies) * len(phantoms)} distribution plots")

    def plot_score_vs_body_position_per_phantom(self) -> None:
        """Create Score vs Body Position plots per phantom (single column IEEE format)."""
        if self.proxy_df.empty:
            return

        self.logger.info("  - Generating Score vs Body Position plots per phantom...")

        # Required columns
        if "z_mm" not in self.proxy_df.columns:
            self.logger.warning("    - Missing z_mm column, skipping body position plots")
            return

        phantoms = ["duke", "ella", "eartha", "thelonious"]

        for phantom in phantoms:
            data = self.proxy_df[self.proxy_df["phantom"] == phantom].copy()

            if data.empty:
                continue

            # Sample for performance
            if len(data) > 50000:
                data = data.sample(n=50000, random_state=42)

            # === Figure 1: Score vs Body Position (Z) ===
            fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COLUMN_WIDTH, 2.8))

            # Color by frequency
            for freq in sorted(data["freq_ghz"].unique()):
                freq_data = data[data["freq_ghz"] == freq]
                if len(freq_data) > 5000:
                    freq_data = freq_data.sample(n=5000, random_state=42)
                ax.scatter(
                    freq_data["z_mm"],
                    freq_data["proxy_score"],
                    c=FREQUENCY_COLORS.get(freq, "gray"),
                    s=1,
                    alpha=0.3,
                    label=f"{freq} GHz",
                )

            # Mark top 10
            top10 = data.nlargest(10, "proxy_score")
            ax.scatter(
                top10["z_mm"],
                top10["proxy_score"],
                c="red",
                s=30,
                marker="*",
                edgecolors="black",
                linewidths=0.5,
                zorder=10,
                label="Top 10",
            )

            ax.set_xlim(left=0)
            ax.set_ylim(bottom=0)
            ax.set_xlabel("Z Position (mm) - Feet→Head")
            ax.set_ylabel("Hotspot Score (V²/m²)")
            ax.legend(fontsize=5, markerscale=2, loc="upper left", ncol=2)

            plt.tight_layout()
            self._save_figure(
                fig,
                "body_position",
                f"score_vs_z_{phantom}",
                title=f"Score vs Body Position - {PHANTOM_LABELS.get(phantom, phantom)}",
                caption=f"Hotspot score vs body position (Z-axis) for {PHANTOM_LABELS.get(phantom, phantom)}. Top 10 candidates marked with red stars.",
            )

            # === Figure 2: Peak Score by Body Region ===
            fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COLUMN_WIDTH, 2.5))

            # Compute phantom-specific z-range from actual data
            z_min = data["z_mm"].min()
            z_max = data["z_mm"].max()
            z_range_total = z_max - z_min

            # Define regions as percentages of total body height (feet=0%, head=100%)
            # These percentages are approximate and based on human anatomy
            region_percentages = {
                "Feet": (0.00, 0.05),  # Bottom 5%
                "Legs": (0.05, 0.45),  # 5-45%
                "Torso": (0.45, 0.75),  # 45-75%
                "Neck": (0.75, 0.85),  # 75-85%
                "Head": (0.85, 1.00),  # Top 15%
            }

            # Convert percentages to absolute z-coordinates for this phantom
            regions = {}
            for region, (pct_low, pct_high) in region_percentages.items():
                z_low = z_min + pct_low * z_range_total
                z_high = z_min + pct_high * z_range_total
                regions[region] = (z_low, z_high)

            # Arms/Hands handled separately via x-coordinate
            regions["Arms/Hands"] = None

            region_max = {}
            for region, z_range in regions.items():
                if z_range is not None:
                    region_data = data[(data["z_mm"] >= z_range[0]) & (data["z_mm"] < z_range[1])]
                else:
                    # Arms/Hands: high |x| values (use 50th percentile of |x| as threshold)
                    if "x_mm" in data.columns:
                        x_threshold = data["x_mm"].abs().quantile(0.75)
                        region_data = data[np.abs(data["x_mm"]) > x_threshold]
                    else:
                        continue

                if not region_data.empty:
                    region_max[region] = region_data["proxy_score"].max()

            if region_max:
                regions_ordered = ["Feet", "Legs", "Torso", "Arms/Hands", "Neck", "Head"]
                x_pos = []
                heights = []
                labels = []
                for r in regions_ordered:
                    if r in region_max:
                        x_pos.append(len(x_pos))
                        heights.append(region_max[r])
                        labels.append(r)

                bars = ax.bar(x_pos, heights, color=PHANTOM_COLORS.get(phantom, "gray"), edgecolor="black", linewidth=0.5)
                ax.set_xticks(x_pos)
                ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
                ax.set_ylim(bottom=0)
                ax.set_ylabel("Max Hotspot Score (V²/m²)")

                # Highlight max
                max_idx = heights.index(max(heights))
                bars[max_idx].set_color("red")

            plt.tight_layout()
            self._save_figure(
                fig,
                "body_position",
                f"peak_by_region_{phantom}",
                title=f"Peak Score by Body Region - {PHANTOM_LABELS.get(phantom, phantom)}",
                caption=f"Maximum hotspot score by body region for {PHANTOM_LABELS.get(phantom, phantom)}. Highest region highlighted in red.",
            )

            # === Figure 3: CDF ===
            fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COLUMN_WIDTH, 2.5))

            sorted_scores = np.sort(data["proxy_score"])
            cdf = np.arange(1, len(sorted_scores) + 1) / len(sorted_scores)
            ax.plot(sorted_scores, cdf, color="black", linewidth=1.5)
            ax.axhline(0.95, color="red", linestyle="--", linewidth=1, label="95th percentile")
            ax.axvline(data["proxy_score"].quantile(0.95), color="red", linestyle="--", linewidth=1, alpha=0.5)
            ax.set_xlim(left=0)
            ax.set_ylim(0, 1)
            ax.set_xlabel("Hotspot Score (V²/m²)")
            ax.set_ylabel("Cumulative Probability")
            ax.legend(fontsize=6)
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            self._save_figure(
                fig,
                "body_position",
                f"cdf_{phantom}",
                title=f"Cumulative Distribution Function - {PHANTOM_LABELS.get(phantom, phantom)}",
                caption=f"Cumulative distribution function of hotspot scores for {PHANTOM_LABELS.get(phantom, phantom)}.",
            )

    def plot_icnirp_comparison(self) -> None:
        """Create bar chart comparing worst-case SAPD to ICNIRP limit.

        Shows worst-case SAPD from this study vs the ICNIRP 20 W/m² limit
        on a logarithmic scale to highlight the safety margin.
        """
        if self.candidate_df.empty:
            return

        self.logger.info("  - Generating ICNIRP comparison bar chart...")

        # Get worst-case SAPD across all conditions (at 1 W/m² incident)
        worst_case_sapd_1w = self.candidate_df["peak_sapd"].max()  # W/m² at 1 W/m² incident
        icnirp_limit = 20.0  # W/m² (ICNIRP limit for SAPD)

        # At maximum reference level of 10 W/m², SAPD scales linearly
        worst_case_sapd_10w = worst_case_sapd_1w * 10  # W/m² at 10 W/m² incident

        # Create figure (IEEE single-column width)
        fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COLUMN_WIDTH, 2.5))

        # Bar positions and values
        categories = ["At 1 W/m²\n(normalized)", "At 10 W/m²\n(max ref. level)", "ICNIRP Limit"]
        values = [worst_case_sapd_1w, worst_case_sapd_10w, icnirp_limit]
        colors = ["#2ca02c", "#d62728", "#7f7f7f"]  # green for 1W, red for 10W, gray for limit

        bars = ax.bar(categories, values, color=colors, edgecolor="black", linewidth=0.5)

        # Add horizontal line at ICNIRP limit
        ax.axhline(y=icnirp_limit, color="black", linestyle="--", linewidth=1, alpha=0.7)

        ax.set_ylabel("SAPD (W/m²)")
        ax.set_ylim(0, max(worst_case_sapd_10w, icnirp_limit) * 1.3)

        # Add value labels on bars
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.annotate(
                f"{val:.2f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )

        # Add compliance annotation - use percentage for clarity
        pct_of_limit = (worst_case_sapd_10w / icnirp_limit) * 100
        if worst_case_sapd_10w > icnirp_limit:
            annotation_text = f"Exceeds limit\n({pct_of_limit:.1f}% of limit)"
            annotation_color = "lightcoral"
            edge_color = "red"
        else:
            annotation_text = f"{pct_of_limit:.1f}% of limit"
            annotation_color = "lightgreen"
            edge_color = "green"

        ax.annotate(
            annotation_text,
            xy=(0.5, 0.85),
            xycoords="axes fraction",
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=annotation_color, edgecolor=edge_color, alpha=0.8),
        )

        ax.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()

        self._save_figure(
            fig,
            "compliance",
            "icnirp_comparison",
            title="ICNIRP Compliance Comparison",
            caption=f"Comparison of worst-case SAPD at 1 W/m² incident ({worst_case_sapd_1w:.2f} W/m²) and at maximum ICNIRP reference level of 10 W/m² ({worst_case_sapd_10w:.2f} W/m²) with the ICNIRP limit (20 W/m²).",
        )

    def plot_icnirp_compliance_heatmap(self) -> None:
        """Create heatmap showing % of ICNIRP limit at 10 W/m² reference level.

        This shows how close each phantom/frequency combination is to the ICNIRP
        basic restriction when exposed at the maximum allowed reference level.
        """
        if self.candidate_df.empty:
            return

        self.logger.info("  - Generating ICNIRP compliance heatmap...")

        # Get worst-case SAPD per phantom/frequency (at 1 W/m² incident)
        worst_case = self.candidate_df.groupby(["phantom", "freq_ghz"])["peak_sapd"].max().unstack()

        # Reorder phantoms
        phantom_order = ["duke", "ella", "eartha", "thelonious"]
        worst_case = worst_case.reindex([p for p in phantom_order if p in worst_case.index])

        # Calculate % of ICNIRP limit at 10 W/m² reference level
        # SAPD at 10 W/m² = SAPD at 1 W/m² × 10
        # % of limit = (SAPD at 10 W/m² / 20 W/m²) × 100 = SAPD at 1 W/m² × 50
        pct_of_limit = worst_case * 50  # Equivalent to (worst_case * 10 / 20) * 100

        # Create figure (IEEE single-column width)
        fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COLUMN_WIDTH, 2.5))

        # Create diverging colormap centered at 100%
        # Green (<80%), Yellow (80-100%), Red (>100%)
        cmap = sns.diverging_palette(145, 10, s=80, l=55, center="light", as_cmap=True)

        # Create heatmap
        sns.heatmap(
            pct_of_limit,
            annot=True,
            fmt=".0f",
            cmap=cmap,
            center=100,
            vmin=20,
            vmax=110,
            cbar_kws={"label": "% of ICNIRP Limit"},
            ax=ax,
            linewidths=0.5,
        )

        # Labels
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel("")
        ax.set_yticklabels([PHANTOM_NAMES.get(p, p) for p in pct_of_limit.index], rotation=0)

        plt.tight_layout()
        self._save_figure(
            fig,
            "compliance",
            "icnirp_compliance_heatmap",
            title="ICNIRP Compliance at Maximum Reference Level",
            caption="Percentage of ICNIRP basic restriction (20 W/m²) for worst-case SAPD at maximum allowed reference level (10 W/m²). Values >100% exceed the limit.",
        )

    def plot_icnirp_compliance_by_frequency(self) -> None:
        """Create line plot showing compliance margin vs frequency for each phantom."""
        if self.candidate_df.empty:
            return

        self.logger.info("  - Generating ICNIRP compliance by frequency plot...")

        # Get worst-case SAPD per phantom/frequency (at 1 W/m² incident)
        worst_case = self.candidate_df.groupby(["phantom", "freq_ghz"])["peak_sapd"].max().unstack()

        # Calculate % of ICNIRP limit at 10 W/m² reference level
        pct_of_limit = worst_case * 50

        # Create figure
        fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COLUMN_WIDTH, 2.5))

        # Plot each phantom
        markers = self._get_academic_markers(len(pct_of_limit.index))
        for (phantom, row), marker in zip(pct_of_limit.iterrows(), markers):
            ax.plot(
                row.index,
                row.values,
                marker=marker,
                color=PHANTOM_COLORS.get(phantom, "gray"),
                label=PHANTOM_NAMES.get(phantom, phantom),
                linewidth=1.5,
                markersize=6,
            )

        # Add horizontal line at 100% (ICNIRP limit)
        ax.axhline(y=100, color="red", linestyle="--", linewidth=1.5, label="ICNIRP Limit")

        # Fill danger zone
        ax.axhspan(100, ax.get_ylim()[1] if ax.get_ylim()[1] > 100 else 110, alpha=0.2, color="red", label="_nolegend_")

        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel("% of ICNIRP Limit")
        ax.set_ylim(0, max(pct_of_limit.max().max() * 1.1, 110))
        ax.legend(fontsize=7, loc="upper right")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        self._save_figure(
            fig,
            "compliance",
            "icnirp_compliance_by_frequency",
            title="ICNIRP Compliance vs Frequency",
            caption="Percentage of ICNIRP basic restriction at maximum reference level (10 W/m²) as a function of frequency. Higher frequencies show better compliance margins.",
        )

    def _generate_results_tex(self) -> None:
        """Generate LaTeX results.tex file."""
        self.logger.info("  - Generating results.tex...")

        tex_path = self.paper_dir / "results.tex"

        # Compute relative path from paper_dir to output_dir (use forward slashes for LaTeX)
        try:
            rel_path = os.path.relpath(self.output_dir, self.paper_dir).replace("\\", "/")
        except ValueError:
            rel_path = str(self.output_dir).replace("\\", "/")

        lines = [
            r"\documentclass{IEEEtran}",
            r"\usepackage{graphicx}",
            r"\usepackage{booktabs}",
            r"\usepackage{float}",
            r"\usepackage{alphalph}",
            "",
            r"% Fix subsection counter",
            r"\makeatletter",
            r"\@addtoreset{subsection}{section}",
            r"\def\thesubsection{\alphalph{\value{subsection}}}",
            r"\def\thesubsectiondis{\thesection.\alphalph{\value{subsection}}}",
            r"\makeatother",
            "",
            r"\usepackage{hyperref}",
            "",
            r"\title{Auto-Induced Exposure Analysis Results}",
            r"\author{Robin Wydaeghe}",
            r"\date{" + datetime.now().strftime("%Y-%m-%d") + "}",
            "",
            r"\begin{document}",
            "",
            r"\maketitle",
            "",
            r"\tableofcontents",
            r"\newpage",
            "",
        ]

        # Group figures by subdir
        subdirs = {}
        for fig in self.generated_figures:
            subdir = fig["subdir"]
            if subdir not in subdirs:
                subdirs[subdir] = []
            subdirs[subdir].append(fig)

        fig_counter = 0
        for subdir, figures in subdirs.items():
            # Section header - use mapping for better names
            section_name = SECTION_MAPPING.get(subdir, subdir.replace("_", " ").title())
            lines.append(f"\\section{{{section_name}}}")
            lines.append("")

            for fig in figures:
                fig_counter += 1
                filename = fig["filename"].replace("\\", "/")
                title = fig["title"]
                caption = fig["caption"]

                # Escape LaTeX special characters
                caption_safe = caption.replace("_", r"\_").replace("%", r"\%").replace("²", r"$^2$")
                title_safe = title.replace("_", r"\_")

                lines.append(f"\\subsection{{{title_safe}}}")
                lines.append("")
                lines.append(f"{caption_safe}")
                lines.append("")
                lines.append(r"\begin{figure}[H]")
                lines.append(r"\centering")
                lines.append(f"\\includegraphics[width=\\columnwidth]{{{rel_path}/{filename}}}")
                lines.append(f"\\caption{{{caption_safe}}}")
                lines.append(f"\\label{{fig:auto_{fig_counter}}}")
                lines.append(r"\end{figure}")
                lines.append("")

            lines.append(r"\newpage")
            lines.append("")

        # Model parameters section
        lines.append(r"\section{Model Parameters}")
        lines.append("")

        # Linear model table
        lines.append(r"\subsection{Linear Model: Hotspot Score to SAPD}")
        lines.append("")
        lines.append(r"\begin{table}[H]")
        lines.append(r"\centering")
        lines.append(r"\begin{tabular}{lr}")
        lines.append(r"\toprule")
        lines.append(r"Parameter & Value \\")
        lines.append(r"\midrule")
        lines.append(f"Slope ($\\alpha$) & {self.model.get('slope_alpha', 0):.4f} \\\\")
        lines.append(f"Intercept ($\\beta$) & {self.model.get('intercept_beta', 0):.4f} \\\\")
        lines.append(f"$R^2$ & {self.model.get('r_squared', 0):.4f} \\\\")
        lines.append(f"$p$-value & {self.model.get('p_value', 0):.2e} \\\\")
        lines.append(r"\bottomrule")
        lines.append(r"\end{tabular}")
        lines.append(r"\caption{Linear model parameters for SAPD = $\alpha \times$ Hotspot Score + $\beta$}")
        lines.append(r"\label{tab:linear_model_params}")
        lines.append(r"\end{table}")
        lines.append("")

        # Exponential model table (if available)
        if self.exp_model:
            lines.append(r"\subsection{Exponential Model: Distribution Sharpening}")
            lines.append("")
            lines.append(r"\begin{table}[H]")
            lines.append(r"\centering")
            lines.append(r"\begin{tabular}{lr}")
            lines.append(r"\toprule")
            lines.append(r"Parameter & Value \\")
            lines.append(r"\midrule")
            lines.append(f"Amplitude ($a$) & {self.exp_model.get('a', 0):.4f} \\\\")
            lines.append(f"Decay rate ($b$) & {self.exp_model.get('b', 0):.4f} \\\\")
            lines.append(f"Offset ($c$) & {self.exp_model.get('c', 0):.4f} \\\\")
            lines.append(f"$R^2$ & {self.exp_model.get('r_squared', 0):.4f} \\\\")
            lines.append(r"\bottomrule")
            lines.append(r"\end{tabular}")
            lines.append(r"\caption{Exponential model parameters for $\sigma = a \cdot e^{-b \cdot f} + c$ where $f$ is frequency in GHz}")
            lines.append(r"\label{tab:exp_model_params}")
            lines.append(r"\end{table}")
            lines.append("")

        lines.append(r"\end{document}")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        self.logger.info(f"    - Saved: {tex_path}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main():
    """Main entry point for auto-induced analysis."""
    import argparse

    parser = argparse.ArgumentParser(description="Auto-induced exposure analysis")
    parser.add_argument(
        "--results-dir",
        type=str,
        default="results/auto_induced_FR3",
        help="Path to auto_induced_FR3 results directory",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="plots/auto_induced",
        help="Path to output directory for plots (default: plots/auto_induced)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["png", "pdf"],
        default="pdf",
        help="Output format for plots (default: pdf)",
    )
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    # Find base directory
    base_dir = Path(__file__).parent.parent.parent
    results_dir = base_dir / args.results_dir
    output_dir = base_dir / args.output_dir

    if not results_dir.exists():
        print(f"ERROR: Results directory not found: {results_dir}")
        return 1

    # Run analysis
    analyzer = AutoInducedAnalyzer(results_dir, output_dir, plot_format=args.format)
    analyzer.run_analysis()

    return 0


if __name__ == "__main__":
    exit(main())
