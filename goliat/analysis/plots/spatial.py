"""Spatial/3D plot generators."""

import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .base import BasePlotter


class SpatialPlotter(BasePlotter):
    """Generates spatial/3D plots for SAR analysis."""

    def _calculate_axis_limits(self, peak_data: pd.DataFrame) -> dict:
        """Calculates axis limits from all peak locations (in millimeters).

        Args:
            peak_data: DataFrame with peak location data.

        Returns:
            Dictionary with 'x', 'y', 'z' keys containing (min, max) tuples in millimeters.
        """
        all_locations = []
        all_side_lengths = []

        for idx, row in peak_data.iterrows():
            if pd.isna(row.get("PeakLocation")) or pd.isna(row.get("PeakCubeSideLength")):
                continue

            location = row["PeakLocation"]
            if isinstance(location, str):
                try:
                    import ast

                    location = ast.literal_eval(location)
                except Exception:
                    continue

            if isinstance(location, (list, tuple)) and len(location) == 3:
                side_length = float(row.get("PeakCubeSideLength", 0.01))
                x, y, z = location
                all_locations.append([x, y, z])
                all_side_lengths.append(side_length)

        if not all_locations:
            return {"x": (0, 1000), "y": (0, 1000), "z": (0, 1000)}  # Default in mm

        locations = np.array(all_locations)
        max_half = max(all_side_lengths) / 2 if all_side_lengths else 0.01

        # Convert to millimeters and add padding
        return {
            "x": ((locations[:, 0].min() - max_half) * 1000, (locations[:, 0].max() + max_half) * 1000),
            "y": ((locations[:, 1].min() - max_half) * 1000, (locations[:, 1].max() + max_half) * 1000),
            "z": ((locations[:, 2].min() - max_half) * 1000, (locations[:, 2].max() + max_half) * 1000),
        }

    def plot_peak_location_3d_interactive(
        self,
        peak_data: pd.DataFrame,
        scenario_name: str | None = None,
        axis_limits: dict | None = None,
    ):
        """Creates an interactive 3D plot of peak SAR locations as wireframe boxes.

        Each box represents the spatial averaging cube (10g) centered at the peak location.
        Uses Plotly for interactive visualization (not affected by scienceplots).

        Args:
            peak_data: DataFrame with columns: ['PeakLocation', 'PeakCubeSideLength',
                      'PeakValue', 'placement', 'frequency_mhz', 'scenario']
            scenario_name: Optional scenario name for filtering and filename.
            axis_limits: Optional dict with 'x', 'y', 'z' keys containing (min, max) tuples.
                        If None, calculates from filtered data.
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            logging.getLogger("progress").warning(
                "Plotly not available. Skipping 3D interactive plot. Install with: pip install plotly",
                extra={"log_type": "warning"},
            )
            return

        if peak_data.empty:
            logging.getLogger("progress").warning(
                "No peak location data available for 3D plot.",
                extra={"log_type": "warning"},
            )
            return

        # Filter by scenario if provided
        plot_data = peak_data.copy()
        if scenario_name:
            plot_data = plot_data[plot_data["scenario"] == scenario_name].copy()

        if plot_data.empty:
            return

        # Calculate axis limits if not provided
        if axis_limits is None:
            axis_limits = self._calculate_axis_limits(plot_data)

        fig = go.Figure()
        colorscale = "jet"

        # Normalize PeakValue for color mapping
        if "PeakValue" in plot_data.columns:
            peak_values = plot_data["PeakValue"].values
            vmin, vmax = peak_values.min(), peak_values.max()
        else:
            vmin, vmax = 0, 1
            peak_values = np.zeros(len(plot_data))

        # Get unique scenarios for color coding
        if "scenario" in plot_data.columns:
            unique_scenarios = sorted(plot_data["scenario"].unique())
            scenario_colors = plt.cm.tab10(np.linspace(0, 1, len(unique_scenarios)))
            scenario_color_map = {scenario: tuple(scenario_colors[i][:3]) for i, scenario in enumerate(unique_scenarios)}
        else:
            scenario_color_map = {}

        for idx, row in plot_data.iterrows():
            if pd.isna(row.get("PeakLocation")) or pd.isna(row.get("PeakCubeSideLength")):
                continue

            location = row["PeakLocation"]
            if isinstance(location, str):
                try:
                    import ast

                    location = ast.literal_eval(location)
                except Exception:
                    continue

            if not isinstance(location, (list, tuple)) or len(location) != 3:
                continue

            x, y, z = location
            side_length = float(row.get("PeakCubeSideLength", 0.01))
            peak_val = float(row.get("PeakValue", 0))

            # Convert to millimeters
            x_mm, y_mm, z_mm = x * 1000, y * 1000, z * 1000
            side_length_mm = side_length * 1000

            # Create wireframe box vertices (in mm)
            half = side_length_mm / 2
            vertices = [
                [x_mm - half, y_mm - half, z_mm - half],
                [x_mm + half, y_mm - half, z_mm - half],
                [x_mm + half, y_mm + half, z_mm - half],
                [x_mm - half, y_mm + half, z_mm - half],
                [x_mm - half, y_mm - half, z_mm + half],
                [x_mm + half, y_mm - half, z_mm + half],
                [x_mm + half, y_mm + half, z_mm + half],
                [x_mm - half, y_mm + half, z_mm + half],
            ]

            # Define box edges
            edges = [
                [0, 1],
                [1, 2],
                [2, 3],
                [3, 0],  # bottom face
                [4, 5],
                [5, 6],
                [6, 7],
                [7, 4],  # top face
                [0, 4],
                [1, 5],
                [2, 6],
                [3, 7],  # vertical edges
            ]

            scenario = row.get("scenario", "unknown")
            placement = row.get("placement", "unknown")
            freq = row.get("frequency_mhz", "unknown")
            label = f"{scenario} | {placement} | {freq} MHz"

            # For aggregated plot: use scenario colors and show legend grouped by scenario
            # For individual scenario plot: use peak value colors, no legend
            if scenario_name is None and scenario in scenario_color_map:
                box_color = scenario_color_map[scenario]
                legend_name = scenario  # Group by scenario in aggregated plot
                show_legend = True
            else:
                normalized_val = (peak_val - vmin) / (vmax - vmin) if vmax > vmin else 0.5
                box_color = plt.cm.get_cmap(colorscale)(normalized_val)[:3]
                legend_name = label
                show_legend = False

            # Create a trace for this box (all edges together for legend)
            edge_x, edge_y, edge_z = [], [], []
            for edge in edges:
                v0, v1 = vertices[edge[0]], vertices[edge[1]]
                edge_x.extend([v0[0], v1[0], None])
                edge_y.extend([v0[1], v1[1], None])
                edge_z.extend([v0[2], v1[2], None])

            fig.add_trace(
                go.Scatter3d(
                    x=edge_x,
                    y=edge_y,
                    z=edge_z,
                    mode="lines",
                    line=dict(color=f"rgb({int(box_color[0] * 255)}, {int(box_color[1] * 255)}, {int(box_color[2] * 255)})", width=3),
                    name=legend_name,
                    showlegend=show_legend,
                    legendgroup=scenario if scenario_name is None else None,
                    hovertemplate=f"{label}<br>Peak SAR: {peak_val:.2f} mW/kg<br>Location: ({x_mm:.2f}, {y_mm:.2f}, {z_mm:.2f}) mm<extra></extra>",
                )
            )

        # Add colorbar for peak values (only if not using scenario colors)
        if scenario_name is not None or not scenario_color_map:
            fig.add_trace(
                go.Scatter3d(
                    x=[None],
                    y=[None],
                    z=[None],
                    mode="markers",
                    marker=dict(
                        colorscale=colorscale,
                        showscale=True,
                        cmin=vmin,
                        cmax=vmax,
                        colorbar=dict(title="Peak SAR (mW/kg)", len=0.5, y=0.5),
                    ),
                    showlegend=False,
                )
            )

        base_title = "3D peak SAR location visualization"
        title_with_phantom = self._get_title_with_phantom(base_title, scenario_name)
        # Title will be in caption file, not on plot
        fig.update_layout(
            title=title_with_phantom,
            scene=dict(
                xaxis_title="X (mm)",
                yaxis_title="Y (mm)",
                zaxis_title="Z (mm)",
                xaxis=dict(range=axis_limits["x"]),
                yaxis=dict(range=axis_limits["y"]),
                zaxis=dict(range=axis_limits["z"]),
                aspectmode="cube",
            ),
            width=1000,
            height=800,
        )

        subdir = self._get_subdir("spatial")
        filename = f"peak_location_3d_interactive_{scenario_name}.html" if scenario_name else "peak_location_3d_interactive_all.html"
        fig.write_html(os.path.join(subdir, filename))

        # Create caption file for HTML plot
        caption_filename = filename.replace(".html", ".txt")
        caption_path = os.path.join(subdir, caption_filename)
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The interactive 3D visualization shows peak SAR locations as wireframe boxes representing the spatial averaging cube (10g) centered at each peak location for the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario for {phantom_name_formatted}."
        with open(caption_path, "w", encoding="utf-8") as f:
            f.write(f"Title: {title_with_phantom}\n\n")
            f.write(f"Caption: {caption}\n")

        logging.getLogger("progress").info(
            f"  - Generated 3D interactive plot: {filename}",
            extra={"log_type": "success"},
        )

    def plot_peak_location_2d_projections(
        self,
        peak_data: pd.DataFrame,
        scenario_name: str | None = None,
    ):
        """Creates 2D scatter plots showing peak locations projected onto XY, XZ, YZ planes.

        Args:
            peak_data: DataFrame with columns: ['PeakLocation', 'PeakValue', 'placement',
                      'frequency_mhz', 'scenario']
            scenario_name: Optional scenario name for filtering and filename.
        """
        if peak_data.empty:
            return

        if scenario_name:
            peak_data = peak_data[peak_data["scenario"] == scenario_name].copy()

        if peak_data.empty:
            return

        # Extract coordinates
        locations = []
        peak_values = []
        for idx, row in peak_data.iterrows():
            if pd.isna(row.get("PeakLocation")):
                continue
            location = row["PeakLocation"]
            if isinstance(location, str):
                try:
                    import ast

                    location = ast.literal_eval(location)
                except Exception:
                    continue
            if isinstance(location, (list, tuple)) and len(location) == 3:
                locations.append(location)
                peak_values.append(float(row.get("PeakValue", 0)))

        if not locations:
            return

        locations = np.array(locations)
        peak_values = np.array(peak_values)

        # Convert from meters to millimeters
        locations_mm = locations * 1000

        # Vertical arrangement: 3 rows, 1 column, variable height
        subplot_height = 2.5  # Height per subplot
        total_height = 3 * subplot_height
        fig, axes = plt.subplots(3, 1, figsize=(3.5, total_height))  # IEEE single-column width, vertical arrangement

        # Auto-detect unit family based on max peak value
        max_val_raw = peak_values.max()
        unit_multiplier = 1.0
        unit_label = r"mW kg$^{-1}$"

        if max_val_raw < 1e-6:
            unit_multiplier = 1e9
            unit_label = r"nW kg$^{-1}$"
        elif max_val_raw < 1e-3:
            unit_multiplier = 1e6
            unit_label = r"$\mu$W kg$^{{-1}}$"
        elif max_val_raw < 1.0:
            unit_multiplier = 1e3
            unit_label = r"mW kg$^{-1}$"

        peak_values_scaled = peak_values * unit_multiplier
        vmin = 0.0 * unit_multiplier  # Start colormap at 0
        vmax = peak_values_scaled.max()

        # Transverse-XY plane (subplot title - keep it)
        scatter1 = axes[0].scatter(
            locations_mm[:, 0], locations_mm[:, 1], c=peak_values_scaled, cmap="jet", alpha=0.7, s=30, vmin=vmin, vmax=vmax
        )
        axes[0].set_xlabel(self._format_axis_label("X", "mm"))
        axes[0].set_ylabel(self._format_axis_label("Y", "mm"))
        axes[0].set_title("Transverse-XY plane")
        axes[0].grid(True, alpha=0.3)
        cbar1 = plt.colorbar(scatter1, ax=axes[0])
        cbar1.set_label(self._format_axis_label("Peak SAR", unit_label))

        # Sagittal-XZ plane (subplot title - keep it)
        scatter2 = axes[1].scatter(
            locations_mm[:, 0], locations_mm[:, 2], c=peak_values_scaled, cmap="jet", alpha=0.7, s=30, vmin=vmin, vmax=vmax
        )
        axes[1].set_xlabel(self._format_axis_label("X", "mm"))
        axes[1].set_ylabel(self._format_axis_label("Z", "mm"))
        axes[1].set_title("Sagittal-XZ plane")
        axes[1].grid(True, alpha=0.3)
        cbar2 = plt.colorbar(scatter2, ax=axes[1])
        cbar2.set_label(self._format_axis_label("Peak SAR", unit_label))

        # Coronal-YZ plane (subplot title - keep it)
        scatter3 = axes[2].scatter(
            locations_mm[:, 1], locations_mm[:, 2], c=peak_values_scaled, cmap="jet", alpha=0.7, s=30, vmin=vmin, vmax=vmax
        )
        axes[2].set_xlabel(self._format_axis_label("Y", "mm"))
        axes[2].set_ylabel(self._format_axis_label("Z", "mm"))
        axes[2].set_title("Coronal-YZ plane")
        axes[2].grid(True, alpha=0.3)
        cbar3 = plt.colorbar(scatter3, ax=axes[2])
        cbar3.set_label(self._format_axis_label("Peak SAR", unit_label))

        base_title = "peak SAR location 2D projections"
        title_full = self._get_title_with_phantom(base_title, scenario_name)
        # Don't set suptitle - will be in caption file

        # Add sample size annotation - top-right, simple box, black border
        n_samples = len(locations_mm)
        fig.text(
            0.95,
            0.95,
            f"n = {n_samples}",
            fontsize=8,
            transform=fig.transFigure,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="square,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.5, alpha=1.0),
        )
        plt.tight_layout()

        filename_base = f"peak_location_2d_{scenario_name}" if scenario_name else "peak_location_2d"
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The 2D projections show peak SAR locations onto Transverse-XY, Sagittal-XZ, and Coronal-YZ planes for the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario for {phantom_name_formatted}. Each point represents a peak location, colored by peak SAR value."
        filename = self._save_figure(fig, "spatial", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = pd.DataFrame(
            {"x_mm": locations_mm[:, 0], "y_mm": locations_mm[:, 1], "z_mm": locations_mm[:, 2], "peak_sar_mw_kg": peak_values}
        )
        self._save_csv_data(csv_data, "spatial", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated 2D projection plots: {filename}",
            extra={"log_type": "success"},
        )
