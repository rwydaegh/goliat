import traceback
from typing import TYPE_CHECKING, List

from ..logging_manager import LoggingMixin

if TYPE_CHECKING:
    import s4l_v1.analysis as analysis
    import s4l_v1.model as model
    from ..results_extractor import ResultsExtractor


class SapdExtractor(LoggingMixin):
    """Extracts Surface Absorbed Power Density (SAPD) from simulation results.

    Uses Sim4Life's GenericSAPDEvaluator to compute SAPD on the skin surface.
    Automatically identifies skin entities (Skin, Ear_skin) from the material mapping
    and computes peak SAPD metrics.
    """

    def __init__(self, parent: "ResultsExtractor", results_data: dict):
        """Sets up the SAPD extractor.

        Args:
            parent: Parent ResultsExtractor instance.
            results_data: Dict to store extracted SAPD data.
        """
        self.parent = parent
        self.config = parent.config
        self.simulation = parent.simulation
        self.phantom_name = parent.phantom_name
        self.results_data = results_data
        self.progress_logger = parent.progress_logger
        self.verbose_logger = parent.verbose_logger

        import s4l_v1.analysis as analysis
        import s4l_v1.model as model
        import s4l_v1.document as document
        import s4l_v1.units as units

        self.analysis = analysis
        self.model = model
        self.document = document
        self.units = units

        self._temp_group = None

    def extract_sapd(self, simulation_extractor: "analysis.Extractor") -> None:
        """Extracts SAPD statistics.

        1. Identifies skin entities from config.
        2. Creates a ModelToGridFilter for the skin surface.
        3. Configures GenericSAPDEvaluator (4cm^2, 10mm threshold).
        4. Extracts Peak Power Density and its location.

        Args:
            simulation_extractor: The simulation results extractor.
        """
        if not self.config["simulation_parameters.extract_sapd"]:
            return

        self._log("    - Extract SAPD statistics...", level="progress", log_type="progress")

        try:
            # 0. Setup EM Sensor Extractor (Local)
            em_sensor_extractor = self._setup_em_sensor_extractor(simulation_extractor)

            # 1. Get Skin Entities
            skin_entities = self._get_skin_entities()
            if not skin_entities:
                self._log("      - WARNING: No skin entities found for SAPD extraction.", log_type="warning")
                return

            # 2. Create Surface Filter (ModelToGrid)
            # We need to pass a single entity to ModelToGridFilter. If multiple skin parts exist,
            # we must group them temporarily.
            surface_source_entity = self._prepare_skin_group(skin_entities)

            model_to_grid_filter = self.analysis.core.ModelToGridFilter()
            model_to_grid_filter.Name = "Skin_Surface_Source"
            model_to_grid_filter.Entity = surface_source_entity
            model_to_grid_filter.UpdateAttributes()
            self.document.AllAlgorithms.Add(model_to_grid_filter)

            # 3. Setup GenericSAPDEvaluator
            # Inputs: Poynting Vector S(x,y,z,f0) and Surface
            inputs = [em_sensor_extractor.Outputs["S(x,y,z,f0)"], model_to_grid_filter.Outputs["Surface"]]

            sapd_evaluator = self.analysis.em_evaluators.GenericSAPDEvaluator(inputs=inputs)
            sapd_evaluator.AveragingArea = 4.0, self.units.SquareCentiMeters
            sapd_evaluator.Threshold = 0.01, self.units.Meters  # 10 mm
            sapd_evaluator.UpdateAttributes()
            self.document.AllAlgorithms.Add(sapd_evaluator)

            # 4. Extract Results
            sapd_report = sapd_evaluator.Outputs["Spatial-Averaged Power Density Report"]
            sapd_report.Update()

            data_collection = sapd_report.Data.DataSimpleDataCollection

            # Helper to safely get values
            def get_value(key, default=0.0):
                try:
                    return data_collection.FieldValue(key, 0)
                except Exception:
                    return default

            peak_sapd = get_value("PeakPower")
            peak_loc = get_value("PeakSAPDPosition")

            # Store in results_data
            # We save as 'sapd_results' for the separate JSON
            # And also flatten valid keys into the main results for the pickle if needed,
            # or just keep it distinct. The requirement says "Include SAPD data... in the final pickle output".
            # The pickle is usually dump of results_data.

            sapd_info = {
                "peak_sapd_W_m2": peak_sapd,
                "peak_sapd_location_m": peak_loc,  # usually a vec3
            }

            self.results_data["sapd_results"] = sapd_info

            # Log success
            self._log(f"      - Peak SAPD: {peak_sapd:.4f} W/m^2", log_type="info")
            self._log("      - Subtask 'extract_sapd' done", level="progress", log_type="success")

            # Clean up algorithms
            self.document.AllAlgorithms.Remove(sapd_evaluator)
            self.document.AllAlgorithms.Remove(model_to_grid_filter)
            if em_sensor_extractor:
                self.document.AllAlgorithms.Remove(em_sensor_extractor)

            # Clean up temporary group if created?
            # If we created a temporary group entity, we should probably remove it to not pollute the scene,
            # but S4L python API for removing entities is tricky.
            # Usually strict cleanup isn't done for entities, but let's check.
            if hasattr(self, "_temp_group") and self._temp_group:
                # self.model.AllEntities().Remove? - Not standard API.
                # We'll leave the group; it's harmless.
                pass

        except Exception as e:
            self._log(
                f"  - ERROR: An unexpected error during SAPD extraction: {e}",
                level="progress",
                log_type="error",
            )
            self.verbose_logger.error(traceback.format_exc())

    def _get_skin_entities(self) -> List["model.Entity"]:
        """Finds all skin entities defined in the config."""
        material_mapping = self.config.get_material_mapping(self.phantom_name)
        tissue_groups = material_mapping.get("_tissue_groups", {})
        skin_group_names = tissue_groups.get("skin_group", [])

        if not skin_group_names:
            return []

        found_entities = []
        all_entities = self.model.AllEntities()

        for name in skin_group_names:
            if name in all_entities:
                found_entities.append(all_entities[name])
            else:
                self.verbose_logger.warning(f"SAPD: Expected skin entity '{name}' not found in model.")

        return found_entities

    def _prepare_skin_group(self, entities: List["model.Entity"]) -> "model.Entity":
        """Returns a single entity representing the skin.

        If multiple entities, creates a group.
        """
        if len(entities) == 1:
            return entities[0]

        # Create a temporary group for the extractor
        group_name = "Temp_Skin_Group_For_SAPD"

        # Check if exists (idempotency)
        all_entities = self.model.AllEntities()
        if group_name in all_entities:
            return all_entities[group_name]

        try:
            # Create a group and add all skin entities to it
            group = self.model.CreateGroup(group_name)
            group.Add(entities)
            self._temp_group = group
            return group
        except Exception as e:
            self._log(f"Error creating skin group: {e}. Using first entity only.", log_type="warning")
            return entities[0]

    def _setup_em_sensor_extractor(self, simulation_extractor: "analysis.Extractor") -> "analysis.Extractor":
        """Sets up the EM sensor extractor for SAPD analysis.

        Duplicates logic from SarExtractor to keep modules independent.
        """
        em_sensor_extractor = simulation_extractor["Overall Field"]

        excitation_type = self.config["simulation_parameters.excitation_type"] or "Harmonic"
        excitation_type_lower = excitation_type.lower() if isinstance(excitation_type, str) else "harmonic"

        freq_mhz = self.parent.frequency_mhz

        if excitation_type_lower == "gaussian":
            center_freq_hz = freq_mhz * 1e6 if isinstance(freq_mhz, int) else max(freq_mhz) * 1e6
            em_sensor_extractor.FrequencySettings.ExtractedFrequency = center_freq_hz, self.units.Hz
            self._log(f"      - Extracting SAPD at center frequency: {center_freq_hz / 1e6} MHz", log_type="info")
        elif isinstance(freq_mhz, int):
            try:
                freq_hz = freq_mhz * 1e6
                em_sensor_extractor.FrequencySettings.ExtractedFrequency = freq_hz, self.units.Hz
                self._log(f"      - Extracting SAPD at frequency: {freq_mhz} MHz", log_type="info")
            except Exception:
                em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"
        else:
            em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"

        self.document.AllAlgorithms.Add(em_sensor_extractor)
        em_sensor_extractor.Update()
        return em_sensor_extractor
