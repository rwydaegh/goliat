from typing import TYPE_CHECKING

from .base_setup import BaseSetup

if TYPE_CHECKING:
    from logging import Logger

    import s4l_v1.simulation.emfdtd as emfdtd

    from ..config import Config


class BoundarySetup(BaseSetup):
    """Configures the boundary conditions for the simulation."""

    def __init__(
        self,
        config: "Config",
        simulation: "emfdtd.Simulation",
        verbose_logger: "Logger",
        progress_logger: "Logger",
    ):
        super().__init__(config, verbose_logger, progress_logger)
        self.simulation = simulation

    def setup_boundary_conditions(self):
        """Configures PML boundary conditions from the solver settings.

        Sets the global boundary type (e.g., UPML/CPML) and PML strength
        (Low/Medium/High) based on the config.
        """
        self._log("Setting up boundary conditions...", log_type="progress")
        solver_settings = self.config["solver_settings"] or {}
        boundary_config = solver_settings.get("boundary_conditions", {})

        # Set Boundary Type (e.g., UpmlCpml)
        bc_type = boundary_config.get("type", "UpmlCpml")
        self._log(f"  - Setting global boundary conditions to: {bc_type}", log_type="info")

        global_boundaries = self.simulation.GlobalBoundarySettings
        if global_boundaries:
            bc_enum = global_boundaries.GlobalBoundaryType.enum
            if hasattr(bc_enum, bc_type):
                global_boundaries.GlobalBoundaryType = getattr(bc_enum, bc_type)
                self._log(
                    f"    - Successfully set GlobalBoundaryType to {bc_type}",
                    log_type="verbose",
                )
            else:
                self._log(
                    f"    - Warning: Invalid boundary condition type '{bc_type}'. Using default.",
                    log_type="warning",
                )
        else:
            self._log(
                "    - Warning: 'GlobalBoundarySettings' not found on simulation object.",
                log_type="warning",
            )

        # Set PML Strength
        strength = boundary_config.get("strength", "Medium").capitalize()
        self._log(f"  - Setting PML strength to: {strength}", log_type="info")

        boundary_settings_list = [x for x in self.simulation.AllSettings if isinstance(x, self.emfdtd.BoundarySettings)]
        if not boundary_settings_list:
            self._log(
                "  - No BoundarySettings found in simulation. Cannot set PML strength.",
                log_type="warning",
            )
            return

        boundary_settings = boundary_settings_list[0]

        strength_enum = boundary_settings.PmlStrength.enum
        if hasattr(strength_enum, strength):
            boundary_settings.PmlStrength = getattr(strength_enum, strength)
            self._log(f"    - Successfully set PmlStrength to {strength}", log_type="verbose")
        else:
            self._log(
                f"    - Warning: Invalid PML strength '{strength}'. Using default (Medium).",
                log_type="warning",
            )
            boundary_settings.PmlStrength = strength_enum.Medium
