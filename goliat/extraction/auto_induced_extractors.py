"""Extraction helpers for AutoInducedProcessor.

Mixin providing SAR and SAPD extraction methods. Kept separate to avoid
bloating auto_induced_processor.py with Sim4Life API calls.
"""

import logging
import os
from pathlib import Path
from typing import Any


class _AutoInducedExtractionMixin:
    """Extraction methods for SAR and SAPD from combined H5 files.

    Expects the host class to provide:
        self.config, self.phantom_name, self.verbose_logger, self._log()
    """

    # Attributes provided by the host class (AutoInducedProcessor)
    config: Any
    phantom_name: str
    verbose_logger: logging.Logger

    def _log(self, message: str, level: str = "verbose", log_type: str = "default") -> None: ...

    def _read_grid_axes(self, input_h5: Path) -> "tuple | None":
        """Read grid axis arrays from input H5, returning (x, y, z) in mm, or None."""
        import h5py

        with h5py.File(input_h5, "r") as f:
            for mesh_key in f["Meshes"].keys():
                mesh = f[f"Meshes/{mesh_key}"]
                if "axis_x" in mesh:
                    return (
                        mesh["axis_x"][:] * 1000,
                        mesh["axis_y"][:] * 1000,
                        mesh["axis_z"][:] * 1000,
                    )
        return None

    def _resolve_skin_entity(self, candidate_idx: int, model) -> Any:
        """Return a united skin entity from cache or by uniting model entities.

        Returns None if no skin entities are found.
        """
        cache_dir = os.path.join(self.config.base_dir, "data", "phantom_skins")
        cache_path = os.path.join(cache_dir, f"{self.phantom_name}_skin.sab")
        united_entity = None

        if os.path.exists(cache_path):
            try:
                imported_entities = list(model.Import(cache_path))
                if imported_entities:
                    united_entity = imported_entities[0]
                    united_entity.Name = f"AutoInduced_CachedSkin_{candidate_idx}"
            except Exception:
                pass

        if united_entity is None:
            skin_entity_names = self._get_skin_entity_names()
            all_entities = model.AllEntities()
            skin_entities = [all_entities[n] for n in skin_entity_names if n in all_entities]

            if not skin_entities:
                return None

            united_entity = model.Unite([e.Clone() for e in skin_entities]) if len(skin_entities) > 1 else skin_entities[0].Clone()

            try:
                os.makedirs(cache_dir, exist_ok=True)
                model.Export([united_entity], cache_path)
            except Exception:
                pass

        return united_entity

    @staticmethod
    def _parse_sapd_data_collection(data_collection) -> "tuple[Any, Any]":
        """Extract peak SAPD value and location from a DataSimpleDataCollection."""

        def _safe_get(key):
            try:
                return data_collection.FieldValue(key, 0)
            except TypeError:
                return None

        keys = list(data_collection.Keys())
        peak_sapd = peak_loc = None

        for key in keys:
            val = _safe_get(key)
            if val is not None:
                if "Peak" in key and "Power" in key:
                    peak_sapd = val
                if "Peak" in key and "Location" in key:
                    peak_loc = val

        if peak_sapd is None:
            for key in keys:
                if "Power" in key or "Density" in key:
                    val = _safe_get(key)
                    if val is not None:
                        peak_sapd = val
                        break

        return peak_sapd, peak_loc

    def _get_skin_entity_names(self) -> list:
        """Get skin entity names from config."""
        try:
            material_mapping = self.config.get_material_mapping(self.phantom_name)
            tissue_groups = material_mapping.get("_tissue_groups", {})
            return tissue_groups.get("skin_group", ["Skin", "Ear_skin"])
        except Exception:
            return ["Skin", "Ear_skin"]

    def _extract_sar(
        self,
        combined_h5: Path,
        candidate_idx: int,
        candidate: dict,
        input_h5: Path,
        candidate_output_dir: "Path | None" = None,
        save_intermediate_files: bool = False,
    ) -> dict:
        """Run the full SAR extraction pipeline on a combined H5 file.

        Args:
            combined_h5: Path to combined _Output.h5 file (full-volume, E-field only).
            candidate_idx: 1-based candidate index.
            candidate: Candidate dict (kept for API consistency).
            input_h5: Path to an _Input.h5 file (kept for API consistency).
            candidate_output_dir: Directory to write per-candidate results into.
            save_intermediate_files: If True, save the Sim4Life project after extraction.

        Returns:
            Dict with at minimum 'candidate_idx' and 'peak_sar_10g_W_kg'.
        """
        from .auto_induced_sar_context import AutoInducedReporter, AutoInducedSarContext, save_candidate_json
        from .sar_extractor import SarExtractor

        if candidate_output_dir is None:
            candidate_output_dir = combined_h5.parent / f"candidate_{candidate_idx:02d}"
        candidate_output_dir.mkdir(parents=True, exist_ok=True)

        self.verbose_logger.info(f"Extracting SAR (full pipeline) from {combined_h5.name} -> {candidate_output_dir.name}/")

        try:
            import s4l_v1.analysis as analysis
            import s4l_v1.document as document

            sim_extractor = analysis.extractors.SimulationExtractor(inputs=[])
            sim_extractor.Name = f"AutoInduced_SAR_Candidate{candidate_idx}"
            sim_extractor.FileName = str(combined_h5)
            sim_extractor.UpdateAttributes()
            document.AllAlgorithms.Add(sim_extractor)

            context = AutoInducedSarContext(self, candidate_output_dir)  # type: ignore[arg-type]
            results_data: dict = {}

            sar_extractor = SarExtractor(context, results_data)  # type: ignore[arg-type]
            sar_extractor.extract_sar_statistics(sim_extractor)

            if "_temp_sar_df" in results_data:
                reporter = AutoInducedReporter(context)  # type: ignore[arg-type]
                reporter.save_reports(
                    results_data.pop("_temp_sar_df"),
                    results_data.pop("_temp_tissue_groups"),
                    results_data.pop("_temp_group_sar_stats"),
                    results_data,
                )
                save_candidate_json(results_data, candidate_output_dir)
            else:
                self._log(
                    f"      Candidate #{candidate_idx}: SarExtractor produced no data (check logs)",
                    log_type="warning",
                )

            try:
                document.AllAlgorithms.Remove(sim_extractor)
            except Exception:
                pass

            if save_intermediate_files:
                try:
                    debug_path = str(combined_h5).replace("_Output.h5", "_intermediate.smash")
                    document.SaveAs(debug_path)
                except Exception:
                    pass

            result = {
                "candidate_idx": candidate_idx,
                "peak_sar_10g_W_kg": results_data.get("peak_sar_10g_W_kg"),
                "whole_body_sar_W_kg": results_data.get("whole_body_sar"),
                "combined_h5": str(combined_h5),
                "output_dir": str(candidate_output_dir),
            }

            peak = result["peak_sar_10g_W_kg"]
            self._log(
                f"      Candidate #{candidate_idx}: peak SAR 10g = {peak:.4e} W/kg"
                if peak is not None
                else f"      Candidate #{candidate_idx}: SAR extraction produced no peak value",
                log_type="info",
            )

            return result

        except Exception as e:
            self._log(f"      ERROR extracting SAR for candidate #{candidate_idx}: {e}", log_type="error")
            import traceback

            self.verbose_logger.error(traceback.format_exc())
            return {"candidate_idx": candidate_idx, "error": str(e)}

    def _extract_sapd(
        self,
        combined_h5: Path,
        candidate_idx: int,
        candidate: dict,
        cube_size_mm: float,
        input_h5: Path,
        save_intermediate_files: bool = False,
    ) -> dict:
        """Extract SAPD from a combined H5 file.

        Args:
            combined_h5: Path to combined _Output.h5 file.
            candidate_idx: 1-based candidate index.
            candidate: Candidate dict with 'voxel_idx' for center location.
            cube_size_mm: Size of the bounding box for mesh slicing.
            input_h5: Path to an input H5 to read grid axes.
            save_intermediate_files: If True, save smash file after extraction.

        Returns:
            Dict with SAPD extraction results.
        """
        from ..utils.mesh_slicer import slice_entity_to_box, voxel_idx_to_mm

        self.verbose_logger.info(f"Extracting SAPD from {combined_h5.name}")

        try:
            import XCoreModeling
            import s4l_v1.analysis as analysis
            import s4l_v1.document as document
            import s4l_v1.model as model
            import s4l_v1.units as units

            axes = self._read_grid_axes(input_h5)
            if axes is None:
                return {"candidate_idx": candidate_idx, "error": "Could not read grid axes from input H5"}

            center_mm = voxel_idx_to_mm(candidate["voxel_idx"], axes)
            self.verbose_logger.info(f"  Focus center: {center_mm} mm")

            sim_extractor = analysis.extractors.SimulationExtractor(inputs=[])
            sim_extractor.Name = f"AutoInduced_Candidate{candidate_idx}"
            sim_extractor.FileName = str(combined_h5)
            sim_extractor.UpdateAttributes()
            document.AllAlgorithms.Add(sim_extractor)

            em_sensor_extractor = sim_extractor["Overall Field"]
            em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"
            em_sensor_extractor.UpdateAttributes()
            document.AllAlgorithms.Add(em_sensor_extractor)
            em_sensor_extractor.Update()

            united_entity = self._resolve_skin_entity(candidate_idx, model)
            if united_entity is None:
                return {"candidate_idx": candidate_idx, "error": "No skin entities found in project"}

            surface_entity = united_entity.Clone()
            surface_entity.Name = f"AutoInduced_Skin_{candidate_idx}"
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
            else:
                self.verbose_logger.warning("  Mesh slicing failed, using full skin mesh")

            model_to_grid_filter = analysis.core.ModelToGridFilter(inputs=[])
            model_to_grid_filter.Name = f"AutoInduced_SkinSurface_{candidate_idx}"
            model_to_grid_filter.Entity = surface_entity
            model_to_grid_filter.UpdateAttributes()
            document.AllAlgorithms.Add(model_to_grid_filter)

            inputs = [em_sensor_extractor.Outputs["S(x,y,z,f0)"], model_to_grid_filter.Outputs["Surface"]]
            sapd_evaluator = analysis.em_evaluators.GenericSAPDEvaluator(inputs=inputs)
            sapd_evaluator.AveragingArea = 4.0, units.SquareCentiMeters
            sapd_evaluator.Threshold = 0.01, units.Meters
            sapd_evaluator.UpdateAttributes()
            document.AllAlgorithms.Add(sapd_evaluator)

            sapd_report = sapd_evaluator.Outputs["Spatial-Averaged Power Density Report"]
            sapd_report.Update()

            data_collection = sapd_report.Data.DataSimpleDataCollection
            if not data_collection:
                return {"candidate_idx": candidate_idx, "error": "No SAPD data available"}

            peak_sapd, peak_loc = self._parse_sapd_data_collection(data_collection)

            if save_intermediate_files:
                try:
                    focus_point = model.CreatePoint(model.Vec3(center_mm[0], center_mm[1], center_mm[2]))
                    focus_point.Name = f"Focus_Center_Candidate{candidate_idx}"
                except Exception:
                    pass
                try:
                    document.SaveAs(str(combined_h5).replace("_Output.h5", "_intermediate.smash"))
                except Exception:
                    pass

            result = {
                "candidate_idx": candidate_idx,
                "peak_sapd_w_m2": float(peak_sapd) if peak_sapd else None,
                "peak_location_m": list(peak_loc) if peak_loc else None,
                "combined_h5": str(combined_h5),
            }

            try:
                document.AllAlgorithms.Remove(sapd_evaluator)
                document.AllAlgorithms.Remove(model_to_grid_filter)
                document.AllAlgorithms.Remove(em_sensor_extractor)
                document.AllAlgorithms.Remove(sim_extractor)
                surface_entity.Delete()
                united_entity.Delete()
            except Exception:
                pass

            return result

        except Exception as e:
            self._log(f"      ERROR extracting SAPD: {e}", log_type="error")
            import traceback

            self.verbose_logger.error(traceback.format_exc())
            return {"candidate_idx": candidate_idx, "error": str(e)}
