import os
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple, Any

from ..logging_manager import LoggingMixin
from ..utils.h5_slicer import slice_h5_output

if TYPE_CHECKING:
    import s4l_v1.analysis as analysis
    import s4l_v1.model as model
    from ..results_extractor import ResultsExtractor


@dataclass
class SapdExtractionContext:
    """Holds state during SAPD extraction to reduce method parameters."""

    center_m: Optional[List[float]] = None
    sliced_h5_path: Optional[str] = None
    sliced_extractor: Optional[Any] = None
    active_extractor: Optional[Any] = None
    em_sensor_extractor: Optional[Any] = None
    model_to_grid_filter: Optional[Any] = None
    sapd_evaluator: Optional[Any] = None


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
        # Check extraction flag (redundant safety check - results_extractor already gates this)
        extract_sapd = self.config["extraction.sapd"]
        if extract_sapd is None:
            extract_sapd = self.config["extract_sapd"]  # Legacy fallback
        if not extract_sapd:
            return

        self._log("    - Extract SAPD statistics...", level="progress", log_type="progress")

        try:
            elapsed = 0.0
            if self.parent.study:
                with self.parent.study.profiler.subtask("extract_sapd"):  # type: ignore
                    ctx = SapdExtractionContext()
                    self._run_extraction_pipeline(simulation_extractor, ctx)

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

    def _run_extraction_pipeline(self, simulation_extractor: "analysis.Extractor", ctx: SapdExtractionContext) -> None:
        """Runs the full SAPD extraction pipeline.

        Args:
            simulation_extractor: The simulation results extractor.
            ctx: Extraction context to store intermediate state.
        """
        # Check for cache flag: if 'use_this_sapd.txt' exists in the results dir,
        # skip phantom slicing / H5 creation and trust whatever is already on disk.
        results_dir = self._get_results_dir()
        cache_flag_path = os.path.join(results_dir, "use_this_sapd.txt")
        use_cache = os.path.exists(cache_flag_path)

        if use_cache:
            self._log(
                "      - SAPD cache flag found ('use_this_sapd.txt'). Skipping phantom slicing and H5 creation — trusting existing files.",
                log_type="info",
            )
            ctx.center_m = self._get_peak_sar_location()  # Still used for skin mesh slicing if available
            ctx.sliced_h5_path = self._get_cached_sliced_h5(results_dir)
        else:
            # Phase 0: Slicing optimization
            ctx.center_m = self._get_peak_sar_location()

            if ctx.center_m:
                ctx.sliced_h5_path = self._create_sliced_h5(ctx.center_m)

        # Phase 1: Setup extractors
        ctx.active_extractor, ctx.sliced_extractor = self._setup_extractor(simulation_extractor, ctx.sliced_h5_path)

        # Phase 2: Get and validate skin entities
        skin_entities = self._get_skin_entities()
        if not skin_entities:
            self._log("      - WARNING: No skin entities found for SAPD extraction.", log_type="warning")
            return

        # Phase 3: Setup surface and SAPD evaluator
        ctx.em_sensor_extractor = self._setup_em_sensor_extractor(ctx.active_extractor)
        ctx.model_to_grid_filter, ctx.sapd_evaluator = self._setup_sapd_evaluator(skin_entities, ctx.center_m, ctx.em_sensor_extractor)

        # Phase 4: Extract and store results
        success = self._extract_and_store_results(ctx.sapd_evaluator)

        # Phase 4b: Optional per-vertex SAPD field dump for AEGIS validation
        if success and self.config["extraction.sapd_field"]:
            try:
                self._dump_sapd_field(ctx.sapd_evaluator)
            except Exception as e:
                self._log(
                    f"      - WARNING: SAPD field dump failed: {e}",
                    log_type="warning",
                )
                self.verbose_logger.error(traceback.format_exc())

        # Phase 5: Cleanup
        self._cleanup_algorithms(ctx)

        if not success:
            return

    def _get_peak_sar_location(self) -> Optional[List[float]]:
        """Gets peak SAR location from results data."""
        peak_sar_details = self.results_data.get("peak_sar_details")
        if peak_sar_details:
            return peak_sar_details.get("PeakLocation")
        return None

    def _setup_extractor(self, simulation_extractor: "analysis.Extractor", sliced_h5_path: Optional[str]) -> Tuple[Any, Optional[Any]]:
        """Sets up the active extractor, using sliced H5 if available.

        Returns:
            Tuple of (active_extractor, sliced_extractor or None).
        """
        if sliced_h5_path:
            sliced_extractor = self.analysis.extractors.SimulationExtractor(inputs=[])
            sliced_extractor.Name = "SAPD_Sliced_Extractor"
            sliced_extractor.FileName = sliced_h5_path
            sliced_extractor.UpdateAttributes()
            self.document.AllAlgorithms.Add(sliced_extractor)
            self._log("      - Using sliced H5 for SAPD calculation.", log_type="info")
            return sliced_extractor, sliced_extractor
        return simulation_extractor, None

    def _setup_sapd_evaluator(
        self,
        skin_entities: List["model.Entity"],
        center_m: Optional[List[float]],
        em_sensor_extractor: "analysis.Extractor",
    ) -> Tuple[Any, Any]:
        """Sets up the ModelToGridFilter and GenericSAPDEvaluator.

        Returns:
            Tuple of (model_to_grid_filter, sapd_evaluator).
        """
        # Prepare skin surface
        mesh_side_cfg = self.config["simulation_parameters.sapd_mesh_slicing_side_length_mm"]
        mesh_side_len_mm = float(mesh_side_cfg) if isinstance(mesh_side_cfg, (int, float)) else 100.0
        center_mm = [c * 1000.0 for c in center_m] if center_m else None
        surface_source_entity = self._prepare_skin_group(skin_entities, center_mm, mesh_side_len_mm)

        # Create ModelToGridFilter
        model_to_grid_filter = self.analysis.core.ModelToGridFilter(inputs=[])
        model_to_grid_filter.Name = "Skin_Surface_Source"
        model_to_grid_filter.Entity = surface_source_entity
        model_to_grid_filter.UpdateAttributes()
        self.document.AllAlgorithms.Add(model_to_grid_filter)

        # Create SAPD evaluator
        inputs = [
            em_sensor_extractor.Outputs["S(x,y,z,f0)"],
            model_to_grid_filter.Outputs["Surface"],
        ]
        sapd_evaluator = self.analysis.em_evaluators.GenericSAPDEvaluator(inputs=inputs)
        sapd_evaluator.AveragingArea = 4.0, self.units.SquareCentiMeters
        sapd_evaluator.Threshold = 0.01, self.units.Meters  # 10 mm

        # When extraction.sapd_field is on, also expose the per-vertex APD
        # field port. SetAPD must be flipped before UpdateAttributes() so
        # the C++ side registers the extra output port.
        if self.config["extraction.sapd_field"]:
            sapd_evaluator.SetAPD = True
            self._log("      - SAPD field dump enabled (Outputs['APD(x,y,z,f0)']).", log_type="info")

        sapd_evaluator.UpdateAttributes()
        self.document.AllAlgorithms.Add(sapd_evaluator)

        # Diagnostic: with SetAPD=True the Outputs collection may swap the
        # "Spatial-Averaged Power Density Report" port out for "APD(x,y,z,f0)"
        # rather than add it. Log the actual port names so the downstream
        # extractor can adapt.
        if self.config["extraction.sapd_field"]:
            try:
                port_names = [getattr(p, "Name", "?") for p in sapd_evaluator.Outputs]
                self._log(f"      - SAPD evaluator output ports: {port_names}", log_type="info")
            except Exception as e:
                self._log(f"      - Could not enumerate SAPD output ports: {e}", log_type="warning")

        return model_to_grid_filter, sapd_evaluator

    def _extract_and_store_results(self, sapd_evaluator: Any) -> bool:
        """Extracts results from SAPD evaluator and stores them.

        Returns:
            True if extraction succeeded, False otherwise.
        """
        sapd_report = sapd_evaluator.Outputs["Spatial-Averaged Power Density Report"]
        if sapd_report is None:
            # SetAPD=True can swap the report port out for the field port.
            # Skip peak extraction; the field dump downstream still runs and
            # AEGIS-side analysis can derive peak/4cm^2 from the per-vertex data.
            self._log(
                "      - 'Spatial-Averaged Power Density Report' port absent (SetAPD=True swap); skipping peak SAPD extraction. Field dump will continue.",
                log_type="warning",
            )
            return True
        sapd_report.Update()

        data_collection = sapd_report.Data.DataSimpleDataCollection
        if not data_collection:
            self._log("      - WARNING: No SAPD data available.", log_type="warning")
            return False

        peak_sapd, peak_loc = self._parse_sapd_data(data_collection)

        if peak_sapd is None:
            self._log("      - WARNING: Could not extract peak SAPD value.", log_type="warning")
            return False

        self.results_data["sapd_results"] = {
            "peak_sapd_W_m2": peak_sapd,
            "peak_sapd_location_m": peak_loc,
        }
        self._log(f"      - Peak SAPD: {peak_sapd:.4f} W/m^2", log_type="info")
        return True

    def _parse_sapd_data(self, data_collection: Any) -> Tuple[Optional[float], Optional[Any]]:
        """Parses SAPD data collection to extract peak values.

        Returns:
            Tuple of (peak_sapd, peak_location).
        """
        keys = list(data_collection.Keys())
        peak_sapd = None
        peak_loc = None

        def safe_get_value(key: str) -> Optional[Any]:
            """Get value from data collection, returns None on TypeError."""
            try:
                return data_collection.FieldValue(key, 0)
            except TypeError:
                return None

        # Look for peak power and location
        for key in keys:
            val = safe_get_value(key)
            if val is not None:
                if "Peak" in key and "Power" in key:
                    peak_sapd = val
                if "Peak" in key and "Location" in key:
                    peak_loc = val

        # Fallback: any power density value
        if peak_sapd is None:
            for key in keys:
                if "Power" in key or "Density" in key:
                    val = safe_get_value(key)
                    if val is not None:
                        peak_sapd = val
                        break

        return peak_sapd, peak_loc

    def _dump_sapd_field(self, sapd_evaluator: Any) -> None:
        """Writes per-vertex APD field to <results_dir>/skin_apd.npz.

        Consumes the `APD(x,y,z,f0)` output port (only present when
        SetAPD=True on the evaluator). The port carries an XPostProcessor
        FloatFieldData with ValueLocation=kNode on a SurfaceGrid; we pull
        vertices and triangle connectivity from the underlying VTK
        unstructured grid. The renorm factor 753.46 = 2*eta_0 converts
        Sim4Life's E=1 V/m unit excitation to a Sinc=1 W/m^2 reference,
        matching what AEGIS uses internally.
        """
        import numpy as np

        port = sapd_evaluator.Outputs["APD(x,y,z,f0)"]
        port.Update()
        data = port.Data

        field = np.asarray(data.Field(0))
        apd = field if field.ndim == 1 else np.linalg.norm(field, axis=-1)
        apd = apd.astype(np.float32, copy=False)

        verts, faces = self._surface_grid_to_arrays(data.Grid)

        if apd.size != len(verts) and apd.size != len(faces):
            raise RuntimeError(
                f"APD has {apd.size} entries but mesh has V={len(verts)}, "
                f"T={len(faces)}; ValueLocation="
                f"{getattr(data, 'ValueLocation', '?')}"
            )

        renorm = 753.46  # 2 * eta_0 — converts E=1 V/m to Sinc=1 W/m^2
        out_dir = self._get_results_dir()
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "skin_apd.npz")
        np.savez(
            out_path,
            apd_w_m2=apd * renorm,
            vertices_m=verts,
            faces=faces,
            port_name="APD(x,y,z,f0)",
            value_location=str(getattr(data, "ValueLocation", "kNode")),
            algorithm="GenericSAPDEvaluator",
            renorm=renorm,
            n_vertices=len(verts),
            n_faces=len(faces),
        )
        self._log(
            f"      - Wrote SAPD field: {os.path.basename(out_path)} "
            f"(V={len(verts)}, T={len(faces)}, peak={float(apd.max()) * renorm:.4f} W/m^2)",
            log_type="info",
        )

    @staticmethod
    def _surface_grid_to_arrays(grid):
        """Pulls (vertices, faces) from an S4L SurfaceGrid via GetPoint/GetCellPoints.

        S4L's grid.GetVtkUnstructuredGrid() returns a raw C++ pointer
        (vtkUnstructuredGrid*) that Boost.Python's by-value converter cannot
        unwrap, so we stick to the documented iteration accessors. Cost is
        a few seconds on a ~50k-vertex thelonious skin; tolerable for Tier 1.
        """
        import numpy as np

        n_pts = grid.NumberOfPoints
        n_cells = grid.NumberOfCells
        verts = np.array([grid.GetPoint(i) for i in range(n_pts)], dtype=np.float64)
        faces = np.array([grid.GetCellPoints(i) for i in range(n_cells)], dtype=np.int32)
        if faces.ndim != 2 or faces.shape[1] != 3:
            raise ValueError(f"expected (T,3) triangle faces, got shape {faces.shape}")
        return verts, faces

    def _cleanup_algorithms(self, ctx: SapdExtractionContext) -> None:
        """Cleans up all algorithms created during extraction."""
        if ctx.sapd_evaluator:
            self.document.AllAlgorithms.Remove(ctx.sapd_evaluator)
        if ctx.model_to_grid_filter:
            self.document.AllAlgorithms.Remove(ctx.model_to_grid_filter)
        if ctx.em_sensor_extractor:
            self.document.AllAlgorithms.Remove(ctx.em_sensor_extractor)
        if ctx.sliced_extractor:
            try:
                self.document.AllAlgorithms.Remove(ctx.sliced_extractor)
            except Exception:
                pass

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
        return os.path.join(base_path, self.parent.placement_name)

    def _get_cached_sliced_h5(self, results_dir: str) -> Optional[str]:
        """Returns the path to a pre-existing sliced H5 file in the results directory.

        Looks for a file matching the expected sliced-H5 naming pattern
        (``sliced_output_<freq>MHz.h5``). Falls back to any ``*_Output.h5``
        or ``*sliced*.h5`` file found in the directory.

        Args:
            results_dir: The results directory for the current simulation.

        Returns:
            Absolute path to the sliced H5 file, or None if none is found.
        """
        import glob

        # Primary: canonical name produced by _create_sliced_h5
        canonical = os.path.join(results_dir, f"sliced_output_{self.parent.frequency_mhz}MHz.h5")
        if os.path.exists(canonical):
            self._log(f"      - Using cached sliced H5: {os.path.basename(canonical)}", log_type="info")
            return canonical

        # Fallback: any sliced H5 in the results dir
        sliced_files = glob.glob(os.path.join(results_dir, "sliced_output_*.h5"))
        if sliced_files:
            path = max(sliced_files, key=os.path.getmtime)
            self._log(f"      - Using cached sliced H5 (fallback): {os.path.basename(path)}", log_type="info")
            return path

        self._log(
            "      - WARNING: Cache flag set but no sliced H5 found in results dir. Will use full simulation H5.",
            log_type="warning",
        )
        return None

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

            results_dir = self._get_results_dir()
            os.makedirs(results_dir, exist_ok=True)

            sliced_filename = f"sliced_output_{self.parent.frequency_mhz}MHz.h5"
            sliced_h5_path = os.path.join(results_dir, sliced_filename)

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

        united_entity = self._get_or_create_united_skin(entities)
        united_entity.Name = "Skin_Merged_For_SAPD"

        if center_mm is not None and side_len_mm is not None:
            return self._slice_skin_mesh(united_entity, center_mm, side_len_mm, XCoreModeling)

        return united_entity

    def _get_or_create_united_skin(self, entities: List["model.Entity"]) -> "model.Entity":
        """Loads cached skin or creates united skin from entities."""

        cache_dir = os.path.join(self.parent.config.base_dir, "data", "phantom_skins")
        cache_path = os.path.join(cache_dir, f"{self.phantom_name}_skin.sab")

        # Try loading from cache
        if os.path.exists(cache_path):
            self._log(f"      - Loading cached skin from {cache_path}...", log_type="info")
            try:
                imported_entities = list(self.model.Import(cache_path))
                if imported_entities:
                    united_entity = imported_entities[0]
                    self._temp_group = united_entity
                    return united_entity
            except Exception as e:
                self._log(
                    f"      - WARNING: Could not import skin cache: {e}. Re-creating.",
                    log_type="warning",
                )

        # Create from scratch
        self._log(f"      - Merging {len(entities)} skin entities into one (takes a while)...", log_type="info")
        united_entity = self._unite_skin_entities(entities)

        # Export to cache
        try:
            os.makedirs(cache_dir, exist_ok=True)
            self.model.Export([united_entity], cache_path)
            self._log(f"      - Exported merged skin to cache: {cache_path}", log_type="info")
        except Exception as e:
            self._log(f"      - WARNING: Could not export skin cache: {e}", log_type="warning")

        return united_entity

    def _unite_skin_entities(self, entities: List["model.Entity"]) -> "model.Entity":
        """Clones and unites skin entities into a single entity."""
        try:
            clones = [e.Clone() for e in entities]
        except Exception as e:
            self._log(
                f"      - WARNING: Could not clone skin entities: {e}. Using originals (destructive).",
                log_type="warning",
            )
            clones = entities

        if len(clones) > 1:
            try:
                united_entity = self.model.Unite(clones)
                self._temp_group = united_entity
                return united_entity
            except Exception as e:
                self._log(
                    f"      - WARNING: Error uniting skin clones: {e}. Using first piece only.",
                    log_type="warning",
                )
                return clones[0]
        return clones[0]

    def _slice_skin_mesh(
        self,
        entity: "model.Entity",
        center_mm: List[float],
        side_len_mm: float,
        XCoreModeling,
    ) -> "model.Entity":
        """Slices skin mesh to a cube around center using planar cuts."""
        self._log(f"      - Slicing mesh to {side_len_mm:.1f}mm box around peak...", log_type="info")
        try:
            half_side = side_len_mm / 2.0
            Vec3 = self.model.Vec3

            # Apply 6 planar cuts to create a cube
            cuts = [
                (Vec3(center_mm[0] - half_side, center_mm[1], center_mm[2]), Vec3(1, 0, 0)),
                (Vec3(center_mm[0] + half_side, center_mm[1], center_mm[2]), Vec3(-1, 0, 0)),
                (Vec3(center_mm[0], center_mm[1] - half_side, center_mm[2]), Vec3(0, 1, 0)),
                (Vec3(center_mm[0], center_mm[1] + half_side, center_mm[2]), Vec3(0, -1, 0)),
                (Vec3(center_mm[0], center_mm[1], center_mm[2] - half_side), Vec3(0, 0, 1)),
                (Vec3(center_mm[0], center_mm[1], center_mm[2] + half_side), Vec3(0, 0, -1)),
            ]
            for point, normal in cuts:
                entity = XCoreModeling.PlanarCut(entity, point, normal)

            self._log("      - Cleaning up sliced mesh...", log_type="info")
            self._cleanup_mesh(entity, XCoreModeling)
            entity.Name = "Skin_Sliced_For_SAPD"
            return entity

        except Exception as e:
            self._log(f"      - WARNING: Mesh slicing failed: {e}. Using unsliced group.", log_type="warning")
            return entity

    def _cleanup_mesh(self, entity: "model.Entity", XCoreModeling) -> None:
        """Cleans up a mesh after slicing operations.

        Applies a 3-step cleanup pipeline:
        1. RemoveBackToBackTriangles - removes duplicate/overlapping triangles
        2. RepairTriangleMesh - fills holes and fixes self-intersections
        3. RemeshTriangleMesh - regenerates mesh with uniform edge length
        """
        try:
            XCoreModeling.RemoveBackToBackTriangles(entity)
        except Exception as e:
            self.verbose_logger.debug(f"RemoveBackToBackTriangles skipped: {e}")

        try:
            XCoreModeling.RepairTriangleMesh(
                [entity],
                fill_holes=True,
                repair_intersections=True,
                min_components_size=10,
            )
        except Exception as e:
            self.verbose_logger.debug(f"RepairTriangleMesh skipped: {e}")

        try:
            mesh_opts = XCoreModeling.MeshingOptions()
            mesh_opts.EdgeLength = 2.0
            mesh_opts.MinEdgeLength = 1.0
            mesh_opts.FeatureAngle = 30.0
            mesh_opts.MaxSpanAngle = 20.0
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
