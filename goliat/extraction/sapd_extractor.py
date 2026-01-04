import os
import traceback
from typing import TYPE_CHECKING, List

from ..logging_manager import LoggingMixin
from ..utils.h5_slicer import slice_h5_output

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
        self.gui = parent.gui

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
        if not self.config["extract_sapd"]:
            return

        self._log("    - Extract SAPD statistics...", level="progress", log_type="progress")

        try:
            elapsed = 0.0
            if self.parent.study:
                with self.parent.study.profiler.subtask("extract_sapd"):  # type: ignore
                    # 0. Slicing Optimization
                    # Find peak SAR location from results_data and create a sliced H5 for faster processing
                    peak_sar_details = self.results_data.get("peak_sar_details")
                    center_m = None
                    if peak_sar_details:
                        center_m = peak_sar_details.get("PeakLocation")

                    # Try to use sliced H5 for better performance
                    sliced_h5_path = None
                    sliced_extractor = None
                    if center_m:
                        sliced_h5_path = self._create_sliced_h5(center_m)

                    # Create extractor - use sliced H5 if available, otherwise use original
                    if sliced_h5_path:
                        # Create a new SimulationExtractor from the sliced H5 file
                        sliced_extractor = self.analysis.extractors.SimulationExtractor(inputs=[])
                        sliced_extractor.Name = "SAPD_Sliced_Extractor"
                        sliced_extractor.FileName = sliced_h5_path
                        sliced_extractor.UpdateAttributes()
                        self.document.AllAlgorithms.Add(sliced_extractor)
                        active_extractor = sliced_extractor
                        self._log("      - Using sliced H5 for SAPD calculation.", log_type="info")
                    else:
                        active_extractor = simulation_extractor

                    # 1. Get Skin Entities
                    skin_entities = self._get_skin_entities()
                    if not skin_entities:
                        self._log("      - WARNING: No skin entities found for SAPD extraction.", log_type="warning")
                        return

                    # 2. Create Surface Filter (ModelToGrid)
                    # We need to pass a single entity to ModelToGridFilter. If multiple skin parts exist,
                    # we must group them temporarily. We also slice the mesh to a smaller area around the peak SAR
                    # location to significantly speed up the SAPD calculation.

                    # Determine side length for mesh slicing (defaults to 100mm)
                    mesh_side_len_mm = float(self.config["simulation_parameters.sapd_mesh_slicing_side_length_mm"] or 100.0)  # type: ignore

                    # Convert center from meters (SAR output) to mm (Sim4Life model units)
                    center_mm = [c * 1000.0 for c in center_m] if center_m else None

                    surface_source_entity = self._prepare_skin_group(skin_entities, center_mm, mesh_side_len_mm)

                    # Create EM Sensor Extractor from the active extractor (sliced or original)
                    em_sensor_extractor = self._setup_em_sensor_extractor(active_extractor)

                    # Initialize with explicit inputs list to match working example
                    model_to_grid_filter = self.analysis.core.ModelToGridFilter(inputs=[])
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

                    # Parse results from the DataSimpleDataCollection
                    data_collection = sapd_report.Data.DataSimpleDataCollection
                    if not data_collection:
                        self._log("      - WARNING: No SAPD data available.", log_type="warning")
                        return

                    # Get keys and extract peak SAPD and location
                    keys = list(data_collection.Keys())
                    peak_sapd = None
                    peak_loc = None

                    def safe_get_value(key):
                        """Safely get value from data collection, handling nullptr."""
                        try:
                            return data_collection.FieldValue(key, 0)
                        except TypeError:
                            # C++ nullptr can't be converted to Python
                            return None

                    for key in keys:
                        val = safe_get_value(key)
                        if val is not None:
                            if "Peak" in key and "Power" in key:
                                peak_sapd = val
                            if "Peak" in key and "Location" in key:
                                peak_loc = val

                    if peak_sapd is None:
                        # Fallback: look for any power density value
                        for key in keys:
                            if "Power" in key or "Density" in key:
                                val = safe_get_value(key)
                                if val is not None:
                                    peak_sapd = val
                                    break

                    if peak_sapd is None:
                        self._log("      - WARNING: Could not extract peak SAPD value.", log_type="warning")
                        return

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

                    # Clean up algorithms
                    self.document.AllAlgorithms.Remove(sapd_evaluator)
                    self.document.AllAlgorithms.Remove(model_to_grid_filter)
                    if em_sensor_extractor:
                        self.document.AllAlgorithms.Remove(em_sensor_extractor)

                    # Clean up sliced extractor if we created one
                    if sliced_extractor is not None:
                        try:
                            self.document.AllAlgorithms.Remove(sliced_extractor)
                        except Exception:
                            pass

                elapsed = self.parent.study.profiler.subtask_times["extract_sapd"][-1]
            self._log(f"      - Subtask 'extract_sapd' done in {elapsed:.2f}s", log_type="verbose")
            self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

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

    def _get_results_dir(self) -> str:
        """Returns the results directory path for current simulation (same as Reporter)."""
        base_path = os.path.join(
            self.parent.config.base_dir,
            "results",
            self.parent.study_type,
            self.parent.phantom_name,
            f"{self.parent.frequency_mhz}MHz",
        )

        if self.parent.study_type == "far_field":
            return os.path.join(base_path, self.parent.placement_name)

        return os.path.join(base_path, self.parent.placement_name)

    def _create_sliced_h5(self, center_m: list) -> str | None:
        """Creates a sliced H5 file and returns its path.

        The sliced H5 contains only the data around the peak SAR location,
        significantly reducing the data size for faster SAPD calculation.

        Args:
            center_m: Peak SAR location in meters [x, y, z].

        Returns:
            Path to the sliced H5 file, or None if slicing failed.
        """
        try:
            # Find the original H5 file using project_manager pattern
            if self.parent.study is None:
                return None

            project_path = self.parent.study.project_manager.project_path
            if not project_path:
                return None

            project_dir = os.path.dirname(project_path)
            project_filename = os.path.basename(project_path)
            sim_results_dir = os.path.join(project_dir, project_filename + "_Results")

            if not os.path.exists(sim_results_dir):
                return None

            import glob

            output_files = glob.glob(os.path.join(sim_results_dir, "*_Output.h5"))
            if not output_files:
                return None

            original_h5_path = max(output_files, key=os.path.getmtime)

            # Determine output path in results directory
            results_dir = self._get_results_dir()
            os.makedirs(results_dir, exist_ok=True)

            sliced_filename = f"sliced_output_{self.parent.frequency_mhz}MHz.h5"
            sliced_h5_path = os.path.join(results_dir, sliced_filename)

            # Get slice size from config
            side_len_mm = float(self.config["simulation_parameters.sapd_slicing_side_length_mm"] or 100.0)  # type: ignore
            side_len_m = side_len_mm / 1000.0

            self._log(f"      - Slicing H5 ({side_len_mm}mm box around peak)...", log_type="info")
            slice_h5_output(original_h5_path, sliced_h5_path, tuple(center_m), side_len_m)
            self._log(f"      - Saved sliced H5: {sliced_filename}", log_type="info")

            return sliced_h5_path

        except Exception as e:
            self._log(f"      - H5 slicing failed: {e}. Using full H5.", log_type="warning")
            return None

    def _prepare_skin_group(self, entities: List["model.Entity"], center_mm=None, side_len_mm=None) -> "model.Entity":
        """Returns a single entity representing the skin, optionally sliced.

        1. Clones the input entities to preserve the original project geometry.
        2. Merges multiple skin entities into a single entity using Unite.
        3. If center_mm and side_len_mm are provided, slices the merged mesh to a cubic box
           using 6 PlanarCut operations (more robust than CSG Intersect).
        4. Cleans up the resulting mesh using RemoveBackToBackTriangles, RepairTriangleMesh,
           and RemeshTriangleMesh.

        Args:
            entities: List of skin entities to merge and optionally slice.
            center_mm: Center point in millimeters (Sim4Life model units). Optional.
            side_len_mm: Side length in millimeters. Optional.
        """
        import XCoreModeling

        if not entities:
            return None

        # Look for a cache of this entity in data/phantoms_skin/[phantom_name]_skin.sab
        cache_dir = os.path.join(self.parent.config.base_dir, "data", "phantoms_skin")
        cache_path = os.path.join(cache_dir, f"{self.phantom_name}_skin.sab")
        united_entity = None

        if os.path.exists(cache_path):
            self._log(f"      - Loading cached skin from {cache_path}...", log_type="info")
            try:
                imported_entities = list(self.model.Import(cache_path))
                if imported_entities:
                    united_entity = imported_entities[0]
                    self._temp_group = united_entity
            except Exception as e:
                self._log(f"      - WARNING: Could not import skin cache: {e}. Re-creating.", log_type="warning")

        if united_entity is None:
            self._log(f"      - Merging {len(entities)} skin entities into one (takes a while)...", log_type="info")
            # Always work on clones to avoid destroying the original phantom entities
            try:
                clones = [e.Clone() for e in entities]
            except Exception as e:
                self._log(f"      - WARNING: Could not clone skin entities: {e}. Using originals (destructive).", log_type="warning")
                clones = entities

            # Unite parts into a single entity
            if len(clones) > 1:
                try:
                    # Unite is required for ModelToGridFilter to work correctly on multiple pieces.
                    united_entity = self.model.Unite(clones)
                    self._temp_group = united_entity
                except Exception as e:
                    self._log(f"      - WARNING: Error uniting skin clones: {e}. Using first piece only.", log_type="warning")
                    united_entity = clones[0]
            else:
                united_entity = clones[0]

            # Export to cache
            try:
                os.makedirs(cache_dir, exist_ok=True)
                self.model.Export([united_entity], cache_path)
                self._log(f"      - Exported merged skin to cache: {cache_path}", log_type="info")
            except Exception as e:
                self._log(f"      - WARNING: Could not export skin cache: {e}", log_type="warning")

        # Name it for visibility in S4L
        merged_name = "Skin_Merged_For_SAPD"
        united_entity.Name = merged_name

        # Perform slicing if peak location is known
        if center_mm is not None and side_len_mm is not None:
            self._log(f"      - Slicing mesh to {side_len_mm:.1f}mm box around peak...", log_type="info")
            try:
                entity = united_entity
                half_side = side_len_mm / 2.0

                # Use 6 PlanarCut operations instead of CSG Intersect (more robust for complex meshes)
                # PlanarCut keeps the volume in the half-space along the plane normal

                # Cut -X side: keep everything with x > center_x - half_side
                entity = XCoreModeling.PlanarCut(
                    entity, self.model.Vec3(center_mm[0] - half_side, center_mm[1], center_mm[2]), self.model.Vec3(1, 0, 0)
                )

                # Cut +X side: keep everything with x < center_x + half_side
                entity = XCoreModeling.PlanarCut(
                    entity, self.model.Vec3(center_mm[0] + half_side, center_mm[1], center_mm[2]), self.model.Vec3(-1, 0, 0)
                )

                # Cut -Y side
                entity = XCoreModeling.PlanarCut(
                    entity, self.model.Vec3(center_mm[0], center_mm[1] - half_side, center_mm[2]), self.model.Vec3(0, 1, 0)
                )

                # Cut +Y side
                entity = XCoreModeling.PlanarCut(
                    entity, self.model.Vec3(center_mm[0], center_mm[1] + half_side, center_mm[2]), self.model.Vec3(0, -1, 0)
                )

                # Cut -Z side
                entity = XCoreModeling.PlanarCut(
                    entity, self.model.Vec3(center_mm[0], center_mm[1], center_mm[2] - half_side), self.model.Vec3(0, 0, 1)
                )

                # Cut +Z side
                entity = XCoreModeling.PlanarCut(
                    entity, self.model.Vec3(center_mm[0], center_mm[1], center_mm[2] + half_side), self.model.Vec3(0, 0, -1)
                )

                # Clean up the mesh after planar cuts
                self._log("      - Cleaning up sliced mesh...", log_type="info")
                self._cleanup_mesh(entity, XCoreModeling)

                entity.Name = "Skin_Sliced_For_SAPD"
                return entity

            except Exception as e:
                self._log(f"      - WARNING: Mesh slicing failed: {e}. Using unsliced group.", log_type="warning")
                return united_entity

        return united_entity

    def _cleanup_mesh(self, entity: "model.Entity", XCoreModeling) -> None:
        """Cleans up a mesh after slicing operations.

        Applies a 3-step cleanup pipeline:
        1. RemoveBackToBackTriangles - removes duplicate/overlapping triangles
        2. RepairTriangleMesh - fills holes and fixes self-intersections
        3. RemeshTriangleMesh - regenerates mesh with uniform edge length
        """
        try:
            # Step 1: Remove duplicate triangles
            XCoreModeling.RemoveBackToBackTriangles(entity)
        except Exception as e:
            self.verbose_logger.debug(f"RemoveBackToBackTriangles skipped: {e}")

        try:
            # Step 2: Repair holes and self-intersections
            XCoreModeling.RepairTriangleMesh(
                [entity],
                fill_holes=True,
                repair_intersections=True,
                min_components_size=10,  # Remove small disconnected pieces
            )
        except Exception as e:
            self.verbose_logger.debug(f"RepairTriangleMesh skipped: {e}")

        try:
            # Step 3: Remesh to uniform quality
            mesh_opts = XCoreModeling.MeshingOptions()
            mesh_opts.EdgeLength = 2.0  # 2mm target edge length
            mesh_opts.MinEdgeLength = 1.0  # 1mm minimum
            mesh_opts.FeatureAngle = 30.0  # Preserve edges at 30 degree angle
            mesh_opts.MaxSpanAngle = 20.0  # Curvature refinement
            mesh_opts.MergeCoincidentNodes = True
            mesh_opts.RepairIntersections = True
            XCoreModeling.RemeshTriangleMesh(entity, mesh_opts)
        except Exception as e:
            self.verbose_logger.debug(f"RemeshTriangleMesh skipped: {e}")

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
