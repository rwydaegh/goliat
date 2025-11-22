import logging
import os

from .plots.bar import BarPlotter
from .plots.base import BasePlotter, METRIC_LABELS, LEGEND_LABELS
from .plots.line import LinePlotter
from .plots.boxplot import BoxplotPlotter
from .plots.heatmap import HeatmapPlotter
from .plots.spatial import SpatialPlotter
from .plots.correlation import CorrelationPlotter
from .plots.bubble import BubblePlotter
from .plots.ranking import RankingPlotter
from .plots.power import PowerPlotter
from .plots.penetration import PenetrationPlotter
from .plots.tissue_analysis import TissueAnalysisPlotter
from .plots.cdf import CdfPlotter
from .plots.outliers import OutliersPlotter

# Re-export constants for backward compatibility
__all__ = ["Plotter", "METRIC_LABELS", "LEGEND_LABELS"]


class Plotter(BasePlotter):
    """Generates publication-ready plots from simulation results.

    Creates bar charts, line plots, boxplots, and heatmaps for SAR analysis.
    All plots are saved to the configured plots directory.

    Uses composition to delegate to specialized plot modules for better organization.
    """

    def __init__(self, plots_dir: str, phantom_name: str | None = None, plot_format: str = "pdf"):
        """Sets up the plotter and creates output directory.

        Args:
            plots_dir: Directory where all plots will be saved.
            phantom_name: Optional phantom model name for titles.
            plot_format: Output format for plots ('pdf' or 'png'), default 'pdf'.
        """
        super().__init__(plots_dir, phantom_name, plot_format)
        os.makedirs(self.plots_dir, exist_ok=True)

        # Initialize specialized plot modules
        self.bar = BarPlotter(plots_dir, phantom_name, plot_format)
        self.line = LinePlotter(plots_dir, phantom_name, plot_format)
        self.boxplot = BoxplotPlotter(plots_dir, phantom_name, plot_format)
        self.heatmap = HeatmapPlotter(plots_dir, phantom_name, plot_format)
        self.spatial = SpatialPlotter(plots_dir, phantom_name, plot_format)
        self.correlation = CorrelationPlotter(plots_dir, phantom_name, plot_format)
        self.bubble = BubblePlotter(plots_dir, phantom_name, plot_format)
        self.ranking = RankingPlotter(plots_dir, phantom_name, plot_format)
        self.power = PowerPlotter(plots_dir, phantom_name, plot_format)
        self.penetration = PenetrationPlotter(plots_dir, phantom_name, plot_format)
        self.tissue_analysis = TissueAnalysisPlotter(plots_dir, phantom_name, plot_format)
        self.cdf = CdfPlotter(plots_dir, phantom_name, plot_format)
        self.outliers = OutliersPlotter(plots_dir, phantom_name, plot_format)

        logging.getLogger("progress").info(
            f"--- Plots will be saved to '{self.plots_dir}' directory. ---",
            extra={"log_type": "info"},
        )

    # Delegate bar chart methods
    def plot_average_sar_bar(self, *args, **kwargs):
        """Creates a bar chart of average SAR values by frequency."""
        return self.bar.plot_average_sar_bar(*args, **kwargs)

    def plot_average_pssar_bar(self, *args, **kwargs):
        """Creates a bar chart of average psSAR10g values by frequency."""
        return self.bar.plot_average_pssar_bar(*args, **kwargs)

    def plot_whole_body_sar_bar(self, *args, **kwargs):
        """Creates a bar chart of average whole-body SAR by frequency."""
        return self.bar.plot_whole_body_sar_bar(*args, **kwargs)

    # Delegate line plot methods
    def plot_peak_sar_line(self, *args, **kwargs):
        """Plots peak SAR trend across frequencies."""
        return self.line.plot_peak_sar_line(*args, **kwargs)

    def plot_pssar_line(self, *args, **kwargs):
        """Plots average psSAR10g trends for tissue groups by frequency."""
        return self.line.plot_pssar_line(*args, **kwargs)

    def plot_sar_line(self, *args, **kwargs):
        """Plots average SAR trends for tissue groups by frequency."""
        return self.line.plot_sar_line(*args, **kwargs)

    def plot_pssar_line_individual_variations(self, *args, **kwargs):
        """Plots individual variation lines for each placement variation."""
        return self.line.plot_pssar_line_individual_variations(*args, **kwargs)

    def plot_sar_line_individual_variations(self, *args, **kwargs):
        """Plots individual variation lines for SAR metrics."""
        return self.line.plot_sar_line_individual_variations(*args, **kwargs)

    # Delegate boxplot methods
    def plot_sar_distribution_boxplots(self, *args, **kwargs):
        """Creates boxplots showing SAR value distributions across placements."""
        return self.boxplot.plot_sar_distribution_boxplots(*args, **kwargs)

    def plot_far_field_distribution_boxplot(self, *args, **kwargs):
        """Creates a boxplot showing distribution of a metric across directions/polarizations."""
        return self.boxplot.plot_far_field_distribution_boxplot(*args, **kwargs)

    # Delegate heatmap methods
    def plot_sar_heatmap(self, *args, **kwargs):
        """Creates a combined heatmap showing Min/Avg/Max SAR per tissue and frequency."""
        return self.heatmap.plot_sar_heatmap(*args, **kwargs)

    def plot_peak_sar_heatmap(self, *args, **kwargs):
        """Creates a heatmap for peak SAR values across tissues and frequencies."""
        return self.heatmap.plot_peak_sar_heatmap(*args, **kwargs)

    # Delegate spatial plot methods
    def plot_peak_location_3d_interactive(self, *args, **kwargs):
        """Creates an interactive 3D plot of peak SAR locations."""
        return self.spatial.plot_peak_location_3d_interactive(*args, **kwargs)

    def plot_peak_location_2d_projections(self, *args, **kwargs):
        """Creates 2D scatter plots showing peak locations projected onto XY, XZ, YZ planes."""
        return self.spatial.plot_peak_location_2d_projections(*args, **kwargs)

    # Delegate correlation plot methods
    def plot_correlation_head_vs_eye_sar(self, *args, **kwargs):
        """Creates scatter plot showing correlation between Head SAR and Eye psSAR10g."""
        return self.correlation.plot_correlation_head_vs_eye_sar(*args, **kwargs)

    def plot_tissue_group_correlation_matrix(self, *args, **kwargs):
        """Creates heatmap showing correlation coefficients between tissue group SAR values."""
        return self.correlation.plot_tissue_group_correlation_matrix(*args, **kwargs)

    # Delegate bubble plot methods
    def plot_bubble_mass_vs_sar(self, *args, **kwargs):
        """Creates bubble plot showing how tissue mass affects SAR values."""
        return self.bubble.plot_bubble_mass_vs_sar(*args, **kwargs)

    def plot_bubble_mass_vs_sar_interactive(self, *args, **kwargs):
        """Creates an interactive bubble plot with common axis limits across frequencies."""
        return self.bubble.plot_bubble_mass_vs_sar_interactive(*args, **kwargs)

    # Delegate ranking plot methods
    def plot_top20_tissues_ranking(self, *args, **kwargs):
        """Creates horizontal bar chart showing top 20 tissues ranked by various metrics."""
        return self.ranking.plot_top20_tissues_ranking(*args, **kwargs)

    # Delegate power plot methods
    def plot_power_efficiency_trends(self, *args, **kwargs):
        """Creates line plot showing antenna efficiency and power component percentages."""
        return self.power.plot_power_efficiency_trends(*args, **kwargs)

    def plot_power_absorption_distribution(self, *args, **kwargs):
        """Creates pie chart or stacked bar chart showing power distribution across tissue groups."""
        return self.power.plot_power_absorption_distribution(*args, **kwargs)

    def plot_power_balance_overview(self, *args, **kwargs):
        """Creates comprehensive power balance overview heatmap."""
        return self.power.plot_power_balance_overview(*args, **kwargs)

    def _prepare_power_data(self, *args, **kwargs):
        """Prepares power balance data for plotting."""
        return self.power._prepare_power_data(*args, **kwargs)

    # Delegate penetration plot methods
    def plot_penetration_depth_ratio(self, *args, **kwargs):
        """Creates line plot showing SAR penetration depth ratio (Brain/Skin) vs frequency."""
        return self.penetration.plot_penetration_depth_ratio(*args, **kwargs)

    # Delegate tissue analysis plot methods
    def plot_max_local_vs_pssar10g_scatter(self, *args, **kwargs):
        """Creates scatter plot showing relationship between Max Local SAR and psSAR10g."""
        return self.tissue_analysis.plot_max_local_vs_pssar10g_scatter(*args, **kwargs)

    def plot_tissue_frequency_response(self, *args, **kwargs):
        """Creates line plot showing how a specific tissue responds across frequencies."""
        return self.tissue_analysis.plot_tissue_frequency_response(*args, **kwargs)

    def plot_tissue_mass_volume_distribution(self, *args, **kwargs):
        """Creates histograms and scatter plot showing tissue mass and volume distributions."""
        return self.tissue_analysis.plot_tissue_mass_volume_distribution(*args, **kwargs)

    # Delegate CDF plot methods
    def plot_cdf(self, *args, **kwargs):
        """Creates CDF plot for a metric with optional aggregation by independent variables."""
        return self.cdf.plot_cdf(*args, **kwargs)

    # Delegate outlier detection methods
    def identify_outliers(self, *args, **kwargs):
        """Identifies and visualizes outliers in SAR metrics."""
        return self.outliers.identify_outliers(*args, **kwargs)
