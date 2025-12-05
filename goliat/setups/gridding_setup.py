from typing import TYPE_CHECKING

import numpy as np

from .base_setup import BaseSetup

if TYPE_CHECKING:
    from logging import Logger

    import s4l_v1.simulation.emfdtd as emfdtd

    from ..antenna import Antenna
    from ..config import Config


class GriddingSetup(BaseSetup):
    """Configures simulation grid resolution and subgridding.

    Sets up main grid (automatic or manual) with padding, and optional
    antenna-specific subgrids for fine details.
    """

    def __init__(
        self,
        config: "Config",
        simulation: "emfdtd.Simulation",
        placement_name: str,
        antenna: "Antenna",
        verbose_logger: "Logger",
        progress_logger: "Logger",
        frequency_mhz: int | None = None,
    ):
        """Initializes the GriddingSetup.

        Args:
            config: Configuration object.
            simulation: The simulation object to configure gridding for.
            placement_name: Name of the placement scenario.
            antenna: Antenna object.
            verbose_logger: Logger for detailed output.
            progress_logger: Logger for progress updates.
            frequency_mhz: Simulation frequency in MHz (optional).
        """
        super().__init__(config, verbose_logger, progress_logger)
        self.simulation = simulation
        self.placement_name = placement_name
        self.antenna = antenna
        self.frequency_mhz = frequency_mhz

        import s4l_v1.units

        self.units = s4l_v1.units

    def setup_gridding(self, antenna_components: dict | None = None):
        """Sets up main grid and optional antenna subgrids.

        Args:
            antenna_components: Dict mapping component names to entities.
        """
        self._log("Setting up gridding...", log_type="progress")
        self._setup_main_grid()
        if antenna_components:
            self._setup_subgrids(antenna_components)
        else:
            self._log(
                "  - No antenna components provided, skipping subgridding.",
                log_type="info",
            )

    def _get_simulation_bbox_name(self) -> str:
        """Determines the name of the simulation bounding box based on simulation type."""
        if self.simulation.Name.endswith("_freespace"):
            return "freespace_simulation_bbox"
        elif self.placement_name:
            return f"{self.placement_name.lower()}_simulation_bbox"
        else:  # Far-field case
            return "far_field_simulation_bbox"

    def _find_simulation_bbox_entity(self, sim_bbox_name: str):
        """Finds the simulation bounding box entity by name."""
        self._log(
            f"  - Looking for global grid bounding box: '{sim_bbox_name}'",
            log_type="verbose",
        )
        sim_bbox_entity = next(
            (e for e in self.model.AllEntities() if hasattr(e, "Name") and e.Name == sim_bbox_name),
            None,
        )
        if not sim_bbox_entity:
            raise RuntimeError(f"Could not find simulation bounding box: '{sim_bbox_name}'")
        return sim_bbox_entity

    def _validate_grid_size(self, grid_size_mm: float, source: str):
        """Validates that grid size does not exceed 3 mm maximum."""
        if grid_size_mm > 3.0:
            error_msg = (
                f"ERROR: Manual grid size of {grid_size_mm} mm ({source}) exceeds the 3 mm maximum.\n"
                "GOLIAT refuses to continue because:\n"
                "- The model will be poorly voxelized, leading to inaccurate results\n"
                "- Even though 3 mm may be acceptable from an FDTD standpoint at low frequencies, "
                "coarser grids cause downstream issues in GOLIAT\n"
                "- Critical features like peak SAR cube computation require adequate voxelization quality\n"
                "Please reduce your manual grid size to 3 mm or smaller.\n"
                "See docs/troubleshooting.md for more details."
            )
            self._log(error_msg, log_type="error")
            raise ValueError(error_msg)

    def _validate_all_per_frequency_grids(self, per_freq_gridding: dict | None):
        """Validates all per-frequency grid sizes."""
        if per_freq_gridding and isinstance(per_freq_gridding, dict):
            for freq_key, grid_size_mm in per_freq_gridding.items():
                self._validate_grid_size(grid_size_mm, f"frequency {freq_key} MHz")

    def _get_manual_grid_resolution(self, gridding_params: dict, global_gridding_params: dict) -> tuple[float, str]:
        """Gets manual grid resolution from config, preferring per-frequency settings."""
        per_freq_gridding = gridding_params.get("global_gridding_per_frequency")
        global_grid_res_mm = None
        log_source = "default"

        # Try to get per-frequency gridding first
        if self.frequency_mhz and per_freq_gridding and isinstance(per_freq_gridding, dict):
            freq_key = str(int(self.frequency_mhz))
            if freq_key in per_freq_gridding:
                global_grid_res_mm = per_freq_gridding[freq_key]
                log_source = f"frequency-specific ({self.frequency_mhz}MHz)"

        # Fallback to global gridding if per-frequency is not found
        if global_grid_res_mm is None:
            global_grid_res_mm = global_gridding_params.get("manual_fallback_max_step_mm", 3.0)
            log_source = "global"

        return global_grid_res_mm, log_source

    def _setup_automatic_grid(self, sim_bbox_entity, global_gridding_params: dict):
        """Sets up automatic gridding mode."""
        self._log("  - Using automatic gridding.", log_type="info")
        self.simulation.GlobalGridSettings.DiscretizationMode = "Automatic"

        # Add the required grid object for the simulation box
        added_grid_settings = self.simulation.AddAutomaticGridSettings([sim_bbox_entity])

        # Map user-friendly refinement names to Sim4Life enums
        refinement_mapping = {
            "Very Fine": "AutoRefinementVeryFine",
            "Fine": "AutoRefinementFine",
            "Default": "AutoRefinementDefault",
            "Coarse": "AutoRefinementCoarse",
            "Very Coarse": "AutoRefinementVeryCoarse",
        }

        # Set refinement based on config, with a default value
        user_refinement_level = global_gridding_params.get("refinement", "Default")
        s4l_refinement_level = refinement_mapping.get(user_refinement_level, "AutoRefinementDefault")

        # Apply the same setting to both the global and the added grid
        self.simulation.GlobalGridSettings.AutoRefinement = s4l_refinement_level
        added_grid_settings.AutoRefinement = s4l_refinement_level
        self._log(
            f"  - Global and added automatic grid set with refinement level: {user_refinement_level} ({s4l_refinement_level})",
            log_type="verbose",
        )

    def _setup_manual_grid(self, sim_bbox_entity, gridding_params: dict, global_gridding_params: dict):
        """Sets up manual gridding mode."""
        self._log("  - Using manual gridding.", log_type="info")
        self.simulation.GlobalGridSettings.DiscretizationMode = "Manual"

        # Add the required grid object for the simulation box
        added_manual_grid = self.simulation.AddManualGridSettings([sim_bbox_entity])

        # Validate manual grid sizes - check all per-frequency values first
        per_freq_gridding = gridding_params.get("global_gridding_per_frequency")
        self._validate_all_per_frequency_grids(per_freq_gridding)

        # Get grid resolution
        global_grid_res_mm, log_source = self._get_manual_grid_resolution(gridding_params, global_gridding_params)

        # Validate the grid size that will actually be used
        self._validate_grid_size(global_grid_res_mm, log_source)

        max_step_setting = (
            np.array([global_grid_res_mm] * 3),
            self.units.MilliMeters,
        )

        # Apply the same setting to both the global and the added grid
        self.simulation.GlobalGridSettings.MaxStep = max_step_setting
        added_manual_grid.MaxStep = max_step_setting
        self._log(
            f"  - Global and added manual grid set with {log_source} resolution: {global_grid_res_mm} mm.",
            log_type="verbose",
        )

    def _setup_padding(self, padding_params: dict):
        """Sets up padding mode (automatic or manual)."""
        padding_mode = padding_params.get("padding_mode", "automatic")
        global_grid_settings = self.simulation.GlobalGridSettings

        if padding_mode == "manual":
            self._log("  - Using manual padding.", log_type="info")
            global_grid_settings.PaddingMode = global_grid_settings.PaddingMode.enum.Manual

            bottom_padding = np.array(padding_params.get("manual_bottom_padding_mm", [0, 0, 0]))
            top_padding = np.array(padding_params.get("manual_top_padding_mm", [0, 0, 0]))

            global_grid_settings.BottomPadding = bottom_padding, self.units.MilliMeters
            global_grid_settings.TopPadding = top_padding, self.units.MilliMeters
            self._log(
                f"    - Manual padding set: Bottom={bottom_padding}mm, Top={top_padding}mm",
                log_type="verbose",
            )
        else:
            self._log("  - Using automatic padding.", log_type="info")
            global_grid_settings.PaddingMode = global_grid_settings.PaddingMode.enum.Automatic

    def _setup_main_grid(self):
        """Configures main grid mode, resolution, and padding."""
        gridding_params = self.config["gridding_parameters"] or {}
        global_gridding_params = gridding_params.get("global_gridding", {})
        gridding_mode = global_gridding_params.get("grid_mode", "automatic")

        # Find the bounding box entity
        sim_bbox_name = self._get_simulation_bbox_name()
        sim_bbox_entity = self._find_simulation_bbox_entity(sim_bbox_name)

        # Apply global grid settings
        self.simulation.GlobalGridSettings.BoundingBox = self.model.GetBoundingBox([sim_bbox_entity])

        # Setup gridding mode
        if gridding_mode == "automatic":
            self._setup_automatic_grid(sim_bbox_entity, global_gridding_params)
        elif gridding_mode == "manual":
            self._setup_manual_grid(sim_bbox_entity, gridding_params, global_gridding_params)
        else:
            raise ValueError(f"Unsupported gridding_mode: {gridding_mode}")

        # Setup Padding
        padding_params = gridding_params.get("padding", {})
        self._setup_padding(padding_params)

    def _setup_automatic_component_grids(self, gridding_config: dict, antenna_components: dict):
        """Sets up automatic gridding for antenna components."""
        automatic_components = [antenna_components[name] for name in gridding_config.get("automatic", []) if name in antenna_components]
        if automatic_components:
            self.simulation.AddAutomaticGridSettings(automatic_components)

    def _setup_manual_component_grids(self, gridding_config: dict, antenna_components: dict, subgridded_components: list):
        """Sets up manual gridding for antenna components."""
        manual_grid_step = gridding_config.get("manual_grid_step", {})
        resolution = gridding_config.get("resolution", {})

        for grid_type, comp_names in gridding_config.get("manual", {}).items():
            # Exclude components that are already set for subgridding
            components_for_manual_grid = [name for name in comp_names if name not in subgridded_components]
            components_to_grid = [antenna_components[name] for name in components_for_manual_grid if name in antenna_components]

            if components_to_grid:
                if grid_type not in manual_grid_step:
                    continue

                res = manual_grid_step[grid_type]
                geom_res = resolution.get(grid_type, [1.0, 1.0, 1.0])

                if self.placement_name == "by_cheek":
                    oriented_res = [res, res, res]
                    oriented_geom_res = [geom_res, geom_res, geom_res]
                else:
                    oriented_res = res
                    oriented_geom_res = geom_res

                manual_grid = self.simulation.AddManualGridSettings(components_to_grid)
                manual_grid.MaxStep = np.array(oriented_res), self.units.MilliMeters
                manual_grid.Resolution = (
                    np.array(oriented_geom_res),
                    self.units.MilliMeters,
                )

    def _apply_subgridding(self, subgridding_config: dict, antenna_components: dict, subgridded_components: list):
        """Applies subgridding settings to specified components."""
        components_to_subgrid = [antenna_components[name] for name in subgridded_components if name in antenna_components]

        if not components_to_subgrid:
            return

        import s4l_v1.simulation.emfdtd as emfdtd

        self._log("  - Applying subgridding settings...", log_type="info")
        automatic_grid_settings = next(
            (x for x in self.simulation.AllSettings if isinstance(x, emfdtd.AutomaticGridSettings) and x.Name == "Automatic"),
            None,
        )

        if automatic_grid_settings:
            self.simulation.Add(automatic_grid_settings, components_to_subgrid)

            subgrid_mode = subgridding_config.get("SubGridMode", "Box")
            subgrid_level = subgridding_config.get("SubGridLevel", "x9")
            auto_refinement = subgridding_config.get("AutoRefinement", "AutoRefinementVeryFine")

            automatic_grid_settings.SubGridMode = getattr(automatic_grid_settings.SubGridMode.enum, subgrid_mode)
            automatic_grid_settings.SubGridLevel = getattr(automatic_grid_settings.SubGridLevel.enum, subgrid_level)
            automatic_grid_settings.AutoRefinement = getattr(automatic_grid_settings.AutoRefinement.enum, auto_refinement)

            self._log(f"    - Mode: {subgrid_mode}, Level: {subgrid_level}, Refinement: {auto_refinement}", log_type="verbose")
        else:
            self._log("  - Could not find 'Automatic' grid settings to apply subgridding.", log_type="warning")

    def _setup_subgrids(self, antenna_components: dict):
        """Sets up antenna component subgrids for fine details.

        Handles automatic grids, manual grids, and subgridding modes.
        Adjusts resolution for 'by_cheek' orientation if needed.

        Args:
            antenna_components: Dict mapping component names to entities.
        """
        if not self.antenna:
            self._log("  - No antenna provided, skipping subgridding.", log_type="info")
            return

        antenna_config = self.antenna.get_config_for_frequency()
        gridding_config = antenna_config.get("gridding")
        if gridding_config:
            # Automatic settings
            self._setup_automatic_component_grids(gridding_config, antenna_components)

            # Subgridding settings
            subgridding_config = gridding_config.get("subgridding", {})
            subgridded_components = subgridding_config.get("components", [])

            # Manual settings
            self._setup_manual_component_grids(gridding_config, antenna_components, subgridded_components)

            # Apply Subgridding settings
            if subgridding_config:
                self._apply_subgridding(subgridding_config, antenna_components, subgridded_components)
        else:
            source_entity = antenna_components[self.antenna.get_source_entity_name()]
            self.simulation.AddAutomaticGridSettings([source_entity])
