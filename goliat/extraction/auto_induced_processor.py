"""Auto-induced exposure processor for far-field studies.

This module orchestrates the auto-induced exposure analysis workflow:
1. Focus point search - find worst-case focus locations on skin
2. Field combination - combine E/H fields with optimal phases
3. SAPD extraction - extract peak SAPD using existing infrastructure

This is called as a post-processing step after all environmental simulations
for a (phantom, frequency) pair complete.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING

from ..logging_manager import LoggingMixin
from ..utils.field_combiner import combine_fields_sliced
from ..utils.focus_optimizer import find_focus_and_compute_weights

if TYPE_CHECKING:
    from ..studies.far_field_study import FarFieldStudy


class AutoInducedProcessor(LoggingMixin):
    """Processes auto-induced exposure using existing SAPD extraction infrastructure.

    Orchestrates focus search, field combination, and SAPD extraction for
    a completed set of environmental simulations.
    """

    def __init__(self, parent_study: "FarFieldStudy", phantom_name: str, freq: int):
        """Initialize the processor.

        Args:
            parent_study: Parent FarFieldStudy instance (provides loggers, profiler, config).
            phantom_name: Name of the phantom (e.g., "thelonious").
            freq: Frequency in MHz.
        """
        self.study = parent_study
        self.config = parent_study.config
        self.phantom_name = phantom_name
        self.freq = freq

        # Share loggers from parent study
        self.verbose_logger = parent_study.verbose_logger
        self.progress_logger = parent_study.progress_logger
        self.gui = parent_study.gui

    def process(
        self,
        h5_paths: list[Path],
        input_h5: Path,
        output_dir: Path,
    ) -> dict:
        """Run the auto-induced analysis pipeline.

        Args:
            h5_paths: List of _Output.h5 file paths (one per direction/polarization).
            input_h5: Path to any _Input.h5 file (for skin mask extraction).
            output_dir: Directory to write combined H5 files and results.

        Returns:
            Dict with analysis results including candidates, SAPD values, and worst-case.
        """
        auto_cfg = self.config["auto_induced"] or {}
        top_n = auto_cfg.get("top_n", 3)
        cube_size_mm = auto_cfg.get("cube_size_mm", 100)

        self._log(
            f"\n--- Auto-Induced Analysis: {self.phantom_name}, {self.freq}MHz ---",
            level="progress",
            log_type="header",
        )
        self._log(
            f"  Combining {len(h5_paths)} simulations, extracting top {top_n} candidates",
            level="progress",
            log_type="info",
        )

        os.makedirs(output_dir, exist_ok=True)

        # Step 1: Focus search
        with self.study.subtask("auto_induced_focus_search"):
            candidates = self._find_focus_candidates(h5_paths, input_h5, top_n)

        if not candidates:
            self._log("    ERROR: No focus candidates found", log_type="error")
            return {"error": "No focus candidates found", "candidates": []}

        # Step 2: Combine fields for each candidate
        with self.study.subtask("auto_induced_combine_fields"):
            combined_h5_paths = []
            for i, candidate in enumerate(candidates):
                combined_path = self._combine_fields_for_candidate(
                    h5_paths=h5_paths,
                    candidate=candidate,
                    output_dir=output_dir,
                    candidate_idx=i + 1,
                    cube_size_mm=cube_size_mm,
                )
                combined_h5_paths.append(combined_path)

        # Step 3: Extract SAPD for each candidate
        with self.study.subtask("auto_induced_extract_sapd"):
            sapd_results = []
            for i, combined_h5 in enumerate(combined_h5_paths):
                if combined_h5 and combined_h5.exists():
                    result = self._extract_sapd(
                        combined_h5=combined_h5,
                        candidate_idx=i + 1,
                        candidate=candidates[i],
                        cube_size_mm=cube_size_mm,
                        input_h5=input_h5,
                    )
                    sapd_results.append(result)
                else:
                    sapd_results.append({"error": f"Combined H5 not found: {combined_h5}"})

        # Find worst case
        worst_case = self._find_worst_case(sapd_results)

        if worst_case and worst_case.get("peak_sapd_w_m2"):
            self._log(
                f"  - Worst-case SAPD: {worst_case['peak_sapd_w_m2']:.2f} W/m2 (candidate #{worst_case.get('candidate_idx')})",
                level="progress",
                log_type="success",
            )

        return {
            "phantom": self.phantom_name,
            "frequency_mhz": self.freq,
            "candidates": candidates,
            "combined_h5_files": [str(p) for p in combined_h5_paths if p],
            "sapd_results": sapd_results,
            "worst_case": worst_case,
        }

    def _find_focus_candidates(
        self,
        h5_paths: list[Path],
        input_h5: Path,
        top_n: int,
    ) -> list[dict]:
        """Find top-N worst-case focus candidates.

        Args:
            h5_paths: List of _Output.h5 file paths.
            input_h5: Path to _Input.h5 for skin mask.
            top_n: Number of candidates to return.

        Returns:
            List of candidate dicts with voxel indices, magnitude sums, and phase weights.
        """
        import time

        import numpy as np

        from ..utils.focus_optimizer import compute_optimal_phases, compute_weights

        start_time = time.monotonic()

        try:
            # find_focus_and_compute_weights returns (focus_indices, weights, info)
            focus_indices, weights, info = find_focus_and_compute_weights(
                h5_paths=[str(p) for p in h5_paths],
                input_h5_path=str(input_h5),
                top_n=top_n,
            )

            # Build list of candidate dicts
            candidates: list[dict] = []
            all_indices = info.get("all_focus_indices", [focus_indices])
            all_mag_sums = info.get("all_magnitude_sums", [info.get("max_magnitude_sum", 0.0)])

            # Ensure we're working with arrays
            if not isinstance(all_indices, np.ndarray):
                all_indices = np.array([all_indices]) if top_n == 1 else np.array(all_indices)
            if not isinstance(all_mag_sums, np.ndarray):
                all_mag_sums = np.array([all_mag_sums]) if top_n == 1 else np.array(all_mag_sums)

            for i in range(min(top_n, len(all_indices))):
                voxel_idx = all_indices[i] if top_n > 1 else all_indices
                mag_sum = float(all_mag_sums[i]) if top_n > 1 else float(all_mag_sums[0])

                # Recompute weights for this specific candidate
                phases = compute_optimal_phases([str(p) for p in h5_paths], voxel_idx)
                candidate_weights = compute_weights(phases)

                candidates.append(
                    {
                        "voxel_idx": list(voxel_idx) if hasattr(voxel_idx, "__iter__") else voxel_idx,
                        "magnitude_sum": mag_sum,
                        "phase_weights": candidate_weights,
                    }
                )

            elapsed = time.monotonic() - start_time
            self.verbose_logger.info(f"Found {len(candidates)} focus candidate(s) in {elapsed:.2f}s")
            for i, c in enumerate(candidates):
                self.verbose_logger.info(f"  Candidate #{i + 1}: voxel {c['voxel_idx']}, Sum|E|={c['magnitude_sum']:.4e}")

            return candidates

        except Exception as e:
            self._log(f"    ERROR in focus search: {e}", log_type="error")
            import traceback

            self.verbose_logger.error(traceback.format_exc())
            return []

    def _combine_fields_for_candidate(
        self,
        h5_paths: list[Path],
        candidate: dict,
        output_dir: Path,
        candidate_idx: int,
        cube_size_mm: float,
    ) -> Path | None:
        """Combine E/H fields for a focus candidate.

        Args:
            h5_paths: List of _Output.h5 file paths.
            candidate: Candidate dict with voxel_idx and phase_weights.
            output_dir: Directory to write combined H5.
            candidate_idx: 1-based index for naming.
            cube_size_mm: Size of extraction cube in mm.

        Returns:
            Path to combined H5 file, or None if failed.
        """
        import time

        output_filename = f"combined_candidate{candidate_idx}_Output.h5"
        output_path = output_dir / output_filename

        start_time = time.monotonic()

        try:
            result = combine_fields_sliced(
                h5_paths=[str(p) for p in h5_paths],
                weights=candidate["phase_weights"],
                template_h5_path=str(h5_paths[0]),
                output_h5_path=str(output_path),
                center_idx=candidate["voxel_idx"],
                side_length_mm=cube_size_mm,
            )

            elapsed = time.monotonic() - start_time
            sliced_shape = result.get("sliced_shape", "unknown")
            self.verbose_logger.info(f"Candidate #{candidate_idx}: {sliced_shape} ({elapsed:.2f}s)")

            return output_path

        except Exception as e:
            self._log(f"      ERROR combining fields: {e}", log_type="error")
            return None

    def _extract_sapd(
        self,
        combined_h5: Path,
        candidate_idx: int,
        candidate: dict,
        cube_size_mm: float,
        input_h5: Path,
    ) -> dict:
        """Extract SAPD from a combined H5 file.

        Uses the existing SAPD extraction infrastructure. The project should
        already be open with the phantom geometry loaded.

        Args:
            combined_h5: Path to combined _Output.h5 file.
            candidate_idx: 1-based candidate index.
            candidate: Candidate dict with 'voxel_idx' for center location.
            cube_size_mm: Size of the bounding box for mesh slicing.
            input_h5: Path to an input H5 to read grid axes for voxel->mm conversion.

        Returns:
            Dict with SAPD extraction results.
        """
        import time

        import h5py

        from ..utils.mesh_slicer import slice_entity_to_box, voxel_idx_to_mm

        self.verbose_logger.info(f"Extracting SAPD from {combined_h5.name}")

        try:
            step_start = time.monotonic()

            # Import here to avoid circular imports and ensure Sim4Life is available
            import XCoreModeling
            import s4l_v1.analysis as analysis
            import s4l_v1.document as document
            import s4l_v1.model as model
            import s4l_v1.units as units

            # Read grid axes from input H5 for voxel->mm conversion
            x_axis = y_axis = z_axis = None
            with h5py.File(input_h5, "r") as f:
                for mesh_key in f["Meshes"].keys():
                    mesh = f[f"Meshes/{mesh_key}"]
                    if "axis_x" in mesh:
                        x_axis = mesh["axis_x"][:] * 1000  # m to mm
                        y_axis = mesh["axis_y"][:] * 1000
                        z_axis = mesh["axis_z"][:] * 1000
                        break

            if x_axis is None:
                return {
                    "candidate_idx": candidate_idx,
                    "error": "Could not read grid axes from input H5",
                }

            voxel_idx = candidate["voxel_idx"]
            center_mm = voxel_idx_to_mm(voxel_idx, (x_axis, y_axis, z_axis))
            self.verbose_logger.info(f"  Focus center: {center_mm} mm")

            # Create SimulationExtractor for the combined H5
            sim_extractor = analysis.extractors.SimulationExtractor(inputs=[])
            sim_extractor.Name = f"AutoInduced_Candidate{candidate_idx}"
            sim_extractor.FileName = str(combined_h5)
            sim_extractor.UpdateAttributes()
            document.AllAlgorithms.Add(sim_extractor)
            self.verbose_logger.info(f"  SimExtractor: {time.monotonic() - step_start:.2f}s")

            # Get EM sensor extractor
            t1 = time.monotonic()
            em_sensor_extractor = sim_extractor["Overall Field"]
            em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"
            em_sensor_extractor.UpdateAttributes()
            document.AllAlgorithms.Add(em_sensor_extractor)
            em_sensor_extractor.Update()
            self.verbose_logger.info(f"  EM Sensor Update: {time.monotonic() - t1:.2f}s")

            # Get skin entities from config
            t2 = time.monotonic()
            skin_entity_names = self._get_skin_entity_names()
            skin_entities = []
            all_entities = model.AllEntities()
            for name in skin_entity_names:
                if name in all_entities:
                    skin_entities.append(all_entities[name])

            if not skin_entities:
                return {
                    "candidate_idx": candidate_idx,
                    "error": "No skin entities found in project",
                }

            # Create surface entity (same pattern as SapdExtractor)
            if len(skin_entities) > 1:
                surface_entity = model.Unite([e.Clone() for e in skin_entities])
            else:
                surface_entity = skin_entities[0].Clone()
            surface_entity.Name = f"AutoInduced_Skin_{candidate_idx}"
            self.verbose_logger.info(f"  Unite skin: {time.monotonic() - t2:.2f}s")

            # Slice the skin mesh to a box around the focus point (critical for speed!)
            t_slice = time.monotonic()
            surface_entity, sliced = slice_entity_to_box(
                entity=surface_entity,
                center_mm=center_mm,
                side_len_mm=cube_size_mm,
                model_module=model,
                xcoremodeling_module=XCoreModeling,
                logger=self.verbose_logger,
            )
            if sliced:
                surface_entity.Name = f"AutoInduced_Skin_Sliced_{candidate_idx}"
                self.verbose_logger.info(f"  Mesh slicing: {time.monotonic() - t_slice:.2f}s")
            else:
                self.verbose_logger.warning("  Mesh slicing failed, using full skin mesh")

            # Create ModelToGridFilter (matching SapdExtractor pattern)
            t3 = time.monotonic()
            model_to_grid_filter = analysis.core.ModelToGridFilter(inputs=[])
            model_to_grid_filter.Name = f"AutoInduced_SkinSurface_{candidate_idx}"
            model_to_grid_filter.Entity = surface_entity
            model_to_grid_filter.UpdateAttributes()
            document.AllAlgorithms.Add(model_to_grid_filter)
            self.verbose_logger.info(f"  ModelToGrid: {time.monotonic() - t3:.2f}s")

            # Create SAPD evaluator with correct inputs (matching SapdExtractor)
            # Inputs: Poynting Vector S(x,y,z,f0) and Surface
            t4 = time.monotonic()
            inputs = [em_sensor_extractor.Outputs["S(x,y,z,f0)"], model_to_grid_filter.Outputs["Surface"]]
            sapd_evaluator = analysis.em_evaluators.GenericSAPDEvaluator(inputs=inputs)
            sapd_evaluator.AveragingArea = 4.0, units.SquareCentiMeters
            sapd_evaluator.Threshold = 0.01, units.Meters  # 10 mm
            sapd_evaluator.UpdateAttributes()
            document.AllAlgorithms.Add(sapd_evaluator)
            self.verbose_logger.info(f"  SAPD Evaluator setup: {time.monotonic() - t4:.2f}s")

            # Get report and update
            t5 = time.monotonic()
            sapd_report = sapd_evaluator.Outputs["Spatial-Averaged Power Density Report"]
            sapd_report.Update()
            self.verbose_logger.info(f"  SAPD Report Update: {time.monotonic() - t5:.2f}s")

            # Parse results from the DataSimpleDataCollection (matching SapdExtractor)
            data_collection = sapd_report.Data.DataSimpleDataCollection
            if not data_collection:
                return {
                    "candidate_idx": candidate_idx,
                    "error": "No SAPD data available",
                }

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

            self.verbose_logger.info(
                f"Candidate #{candidate_idx}: Peak SAPD = {peak_sapd:.4f} W/m2"
                if peak_sapd
                else f"Candidate #{candidate_idx}: Peak SAPD = None"
            )

            # DEBUG: Save smash file with all algorithms for inspection
            debug_smash_path = str(combined_h5).replace("_Output.h5", "_debug.smash")
            try:
                document.SaveAs(debug_smash_path)
                self.verbose_logger.info(f"  DEBUG: Saved project to {debug_smash_path}")
            except Exception as save_err:
                self.verbose_logger.warning(f"  DEBUG: Could not save project: {save_err}")

            return {
                "candidate_idx": candidate_idx,
                "peak_sapd_w_m2": float(peak_sapd) if peak_sapd else None,
                "peak_location_m": list(peak_loc) if peak_loc else None,
                "combined_h5": str(combined_h5),
            }

        except Exception as e:
            self._log(f"      ERROR extracting SAPD: {e}", log_type="error")
            import traceback

            self.verbose_logger.error(traceback.format_exc())
            return {
                "candidate_idx": candidate_idx,
                "error": str(e),
            }

    def _get_skin_entity_names(self) -> list[str]:
        """Get skin entity names from config.

        Returns:
            List of skin entity names (e.g., ["Skin", "Ear_skin"]).
        """
        try:
            material_mapping = self.config.get_material_mapping(self.phantom_name)
            tissue_groups = material_mapping.get("_tissue_groups", {})
            return tissue_groups.get("skin_group", ["Skin", "Ear_skin"])
        except Exception:
            return ["Skin", "Ear_skin"]

    def _find_worst_case(self, sapd_results: list[dict]) -> dict:
        """Find the worst-case (highest SAPD) result.

        Args:
            sapd_results: List of SAPD result dicts.

        Returns:
            The result dict with highest peak SAPD.
        """
        worst = None
        worst_sapd = -1.0

        for result in sapd_results:
            sapd = result.get("peak_sapd_w_m2")
            if sapd is not None and sapd > worst_sapd:
                worst_sapd = sapd
                worst = result

        return worst or {}
