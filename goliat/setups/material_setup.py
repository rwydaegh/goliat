import os
import time
from typing import TYPE_CHECKING

from .base_setup import BaseSetup

if TYPE_CHECKING:
    from logging import Logger

    import s4l_v1.simulation.emfdtd as emfdtd

    from ..antenna import Antenna
    from ..config import Config


class MaterialSetup(BaseSetup):
    """Assigns materials to phantom tissues and antenna components.

    Maps tissue names to IT'IS database materials and assigns antenna
    materials from config. Uses file locking for thread-safe database access.
    """

    def __init__(
        self,
        config: "Config",
        simulation: "emfdtd.Simulation",
        antenna: "Antenna",
        phantom_name: str,
        verbose_logger: "Logger",
        progress_logger: "Logger",
        free_space: bool = False,
        frequencies_mhz: list[int] | None = None,
    ):
        """Initializes the MaterialSetup.

        Args:
            config: Configuration object.
            simulation: The simulation object to assign materials to.
            antenna: Antenna object.
            phantom_name: Name of the phantom model.
            verbose_logger: Logger for detailed output.
            progress_logger: Logger for progress updates.
            free_space: Whether this is a free-space simulation.
            frequencies_mhz: List of frequencies for multisine dispersion fitting.
        """
        super().__init__(config, verbose_logger, progress_logger)
        self.simulation = simulation
        self.antenna = antenna
        self.phantom_name = phantom_name
        self.free_space = free_space
        self.frequencies_mhz = frequencies_mhz
        self.is_multisine = frequencies_mhz is not None and len(frequencies_mhz) > 1

        # Import required modules
        import s4l_v1.materials.database
        import XCoreModeling

        # Access material database - use s4l_v1.materials.database
        self.database = s4l_v1.materials.database
        self.XCoreModeling = XCoreModeling

    def assign_materials(self, antenna_components: dict | None = None, phantom_only: bool = False):
        """Assigns materials to simulation entities.

        Sets background to Air, then assigns phantom materials if not free-space,
        and antenna materials if not phantom_only mode.

        Args:
            antenna_components: Dict mapping component names to entities.
            phantom_only: If True, skips antenna material assignment.
        """
        self._log("Assigning materials...", log_type="progress")

        # Background material
        background_settings = self.simulation.raw.BackgroundMaterialSettings()  # type: ignore
        air_material = self.database["Generic 1.1"]["Air"]  # type: ignore
        self.simulation.raw.AssignMaterial(background_settings, air_material)  # type: ignore

        # Phantom materials
        if not self.free_space:
            if self.is_multisine:
                self._assign_phantom_materials_multisine()
            else:
                self._assign_phantom_materials()

        # Antenna materials
        if not phantom_only:
            if not antenna_components:
                raise ValueError("antenna_components must be provided when not in phantom_only mode.")
            self._assign_antenna_materials(antenna_components)

    def _assign_phantom_materials(self):
        """Assigns IT'IS materials to phantom tissues using file locking.

        Groups tissues by material name from config mapping, then assigns
        materials from IT'IS 4.2 database. Uses lock file to prevent
        concurrent database access issues.
        """
        lock_file_path = os.path.join(self.config.base_dir, "material_db.lock")

        # Acquire lock
        while True:
            try:
                # Use exclusive creation mode to atomically create the file
                with open(lock_file_path, "x"):
                    break  # Lock acquired
            except FileExistsError:
                time.sleep(0.5)  # Wait before retrying

        try:
            all_entities = self.model.AllEntities()
            phantom_parts = [e for e in all_entities if isinstance(e, self.XCoreModeling.TriangleMesh)]

            name_mapping = self.config.get_material_mapping(self.phantom_name)

            material_groups = {}
            for part in phantom_parts:
                base_name = part.Name.split("(")[0].strip()
                material_name = name_mapping.get(base_name, base_name.replace("_", " "))
                material_groups.setdefault(material_name, []).append(part)

            for material_name, entities in material_groups.items():
                try:
                    mat = self.database["IT'IS 4.2"][material_name]  # type: ignore
                    material_settings = self.emfdtd.MaterialSettings()
                    self.simulation.LinkMaterialWithDatabase(material_settings, mat)
                    self.simulation.Add(material_settings, entities)
                except KeyError:
                    self._log(
                        f"    - Warning: Could not find material '{material_name}' in IT'IS 4.2 database.",
                        log_type="warning",
                    )

        finally:
            # Release lock
            if os.path.exists(lock_file_path):
                os.remove(lock_file_path)

    def _assign_phantom_materials_multisine(self):
        """Assigns dispersive materials for multisine simulations.

        Fits dispersion models to match material properties at each
        excitation frequency, enabling accurate FDTD simulation across
        the full frequency range.

        Uses IT'IS V5.0 database for accurate frequency-dependent properties.
        """
        import time

        from ..dispersion import fit_dispersion, get_material_properties

        import XMaterials as xm

        self._log(
            f"  - Multisine mode: fitting dispersion models for frequencies {self.frequencies_mhz} MHz",
            log_type="info",
        )

        all_entities = self.model.AllEntities()
        phantom_parts = [e for e in all_entities if isinstance(e, self.XCoreModeling.TriangleMesh)]

        name_mapping = self.config.get_material_mapping(self.phantom_name)

        material_groups = {}
        for part in phantom_parts:
            base_name = part.Name.split("(")[0].strip()
            material_name = name_mapping.get(base_name, base_name.replace("_", " "))
            material_groups.setdefault(material_name, []).append(part)

        total_materials = len(material_groups)
        assigned_count = 0
        warning_count = 0
        t_start_all = time.perf_counter()

        assert self.frequencies_mhz is not None  # Guaranteed by is_multisine check

        for material_name, entities in material_groups.items():
            try:
                # Get properties from IT'IS database at each frequency
                props = get_material_properties(material_name, self.frequencies_mhz)
                eps_r_list = [p["eps_r"] for p in props]
                sigma_list = [p["sigma"] for p in props]
                frequencies_hz = [f * 1e6 for f in self.frequencies_mhz]

                # Fit Debye model (exact for 2 frequencies)
                params = fit_dispersion(frequencies_hz, eps_r_list, sigma_list)

                if params.fit_error > 0.01:
                    self._log(
                        f"    - WARNING: High fit error ({params.fit_error:.4f}) for '{material_name}'",
                        log_type="warning",
                    )
                    warning_count += 1

                # Create material with LinearDispersive model
                material_settings = self.emfdtd.MaterialSettings()
                material_settings.Name = f"{material_name} (Multisine)"
                material_settings.ElectricProps.MaterialModel = material_settings.ElectricProps.MaterialModel.enum.LinearDispersive

                # Access raw dispersion settings
                disp = material_settings.raw.ElectricDispersiveSettings
                disp.StartFrequency = params.start_freq_hz
                disp.EndFrequency = params.end_freq_hz
                disp.Permittivity = params.eps_inf
                disp.Conductivity = params.sigma_dc

                # Create and assign Debye poles (exact fit for 2 frequencies)
                poles = []
                for pole_fit in params.poles:
                    pole = xm.LinearDispersionPole()
                    pole.Active = True
                    pole.Type = xm.LinearDispersionPole.ePoleType.kDebye
                    pole[xm.LinearDispersionPole.ePoleProperty.kDebyeAmplitude] = 1.0
                    pole[xm.LinearDispersionPole.ePoleProperty.kDebyeStaticPermittivity] = pole_fit.delta_eps
                    pole[xm.LinearDispersionPole.ePoleProperty.kDebyeInfinityPermittivity] = 0.0
                    pole[xm.LinearDispersionPole.ePoleProperty.kDebyeDamping] = pole_fit.tau_s  # tau in seconds!
                    poles.append(pole)

                disp.Poles = poles
                self.simulation.Add(material_settings, entities)
                assigned_count += 1

            except KeyError:
                self._log(
                    f"    - Warning: '{material_name}' not in cache, using database fallback",
                    log_type="warning",
                )
                # Fallback to standard database linking
                try:
                    mat = self.database["IT'IS 4.2"][material_name]
                    material_settings = self.emfdtd.MaterialSettings()
                    self.simulation.LinkMaterialWithDatabase(material_settings, mat)
                    self.simulation.Add(material_settings, entities)
                except KeyError:
                    self._log(
                        f"    - Warning: Could not find material '{material_name}' in IT'IS 4.2 database.",
                        log_type="warning",
                    )
            except Exception as e:
                self._log(
                    f"    - ERROR fitting dispersion for '{material_name}': {e}",
                    log_type="error",
                )

        # Summary
        t_total = time.perf_counter() - t_start_all
        self._log(
            f"    - Assigned {assigned_count}/{total_materials} dispersive materials in {t_total:.2f}s",
            log_type="info",
        )
        if warning_count > 0:
            self._log(f"    - {warning_count} materials had high fit error", log_type="warning")

    def _assign_antenna_materials(self, antenna_components: dict):
        """Assigns materials to antenna components from config.

        Handles special case: forces PEC for Copper in Gaussian excitation
        (Sim4Life limitation). Otherwise uses IT'IS or Generic database based
        on material name.

        Args:
            antenna_components: Dict mapping component names to entities.
        """
        CHANGE_MATERIAL = False

        antenna_config = self.antenna.get_config_for_frequency()
        material_mappings = antenna_config.get("materials", {})

        for comp_name, mat_name in material_mappings.items():
            if comp_name in antenna_components:
                entity = antenna_components[comp_name]
                material_settings = self.emfdtd.MaterialSettings()

                excitation_type = self.config["simulation_parameters.excitation_type"]
                if excitation_type is None:
                    excitation_type = "Harmonic"
                excitation_type_lower = excitation_type.lower() if isinstance(excitation_type, str) else "harmonic"

                if "Copper" in mat_name and excitation_type_lower == "gaussian":
                    if CHANGE_MATERIAL:
                        material_settings.MaterialType = "PEC"
                        self.simulation.Add(material_settings, [entity])
                        self._log("\n" + "=" * 80, log_type="warning")
                        self._log(
                            f"  WARNING: Forcing material for '{comp_name}' to PEC.",
                            log_type="warning",
                        )
                        self._log(
                            "           This is a required workaround because Sim4Life does not yet support",
                            log_type="warning",
                        )
                        self._log(
                            "           Gaussian excitation with dispersive materials like Copper.",
                            log_type="warning",
                        )
                        self._log("=" * 80 + "\n", log_type="warning")
                elif mat_name.lower() == "pec":
                    material_settings.MaterialType = "PEC"
                    self.simulation.Add(material_settings, [entity])
                    self._log(f"  - Assigned 'PEC' to '{comp_name}'.", log_type="info")
                else:
                    try:
                        db_name = "IT'IS 4.2" if "Rogers" in mat_name else "Generic 1.1"
                        mat = self.database[db_name][mat_name]  # type: ignore
                        self.simulation.LinkMaterialWithDatabase(material_settings, mat)
                        self.simulation.Add(material_settings, [entity])
                        self._log(
                            f"  - Assigned '{mat_name}' to '{comp_name}'.",
                            log_type="info",
                        )
                    except KeyError:
                        self._log(
                            f"    - Warning: Could not find material '{mat_name}' in database.",
                            log_type="warning",
                        )
            else:
                self._log(
                    f"    - Warning: Could not find component '{comp_name}' to assign material.",
                    log_type="warning",
                )
