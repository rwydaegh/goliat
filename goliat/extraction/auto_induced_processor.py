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
from .field_combiner import combine_fields_sliced
from .focus_optimizer import find_focus_and_compute_weights

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
        top_n = auto_cfg.get("top_n", 10)
        cube_size_mm = auto_cfg.get("cube_size_mm", 100)
        save_intermediate_files = auto_cfg.get("save_intermediate_files", False)
        search_metric = auto_cfg.get("search_metric", "E_magnitude")
        extraction_metric = auto_cfg.get("extraction_metric", "sapd")
        full_volume = auto_cfg.get("full_volume_combination", False)
        combine_chunk_size = auto_cfg.get("combine_chunk_size", 50)
        # For SAR, only E-field is needed; for SAPD, both E and H
        field_types = ("E",) if extraction_metric == "sar" else ("E", "H")

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
            candidates = self._find_focus_candidates(h5_paths, input_h5, top_n, search_metric, output_dir)

        if not candidates:
            self._log("    ERROR: No focus candidates found", log_type="error")
            return {"error": "No focus candidates found", "candidates": []}

        # Step 2: Combine fields for each candidate
        with self.study.subtask("auto_induced_combine_fields"):
            combined_h5_paths = []
            from tqdm import tqdm
            from .focus_optimizer import FieldCache

            # Pre-load all source fields once, shared across all candidates.
            # FieldCache auto-detects available RAM:
            #   - Memory mode (RAM sufficient): loads all files into numpy arrays.
            #     Weighted sum per candidate is then pure numpy — no file I/O.
            #   - Streaming mode (low RAM): uses slab LRU cache, falls back to
            #     the original chunked approach.
            slab_cache_gb = (self.config["auto_induced"] or {}).get("search", {}).get("slab_cache_gb", 2.0)
            low_memory_mode = (self.config["auto_induced"] or {}).get("search", {}).get("low_memory_mode", None)

            # Only pre-load E (SAR) or E+H (SAPD) — same field types we'll combine
            # FieldCache only supports one field_type at a time, so load each separately
            field_caches = {}
            for ft in field_types:
                self._log(f"  Pre-loading {ft}-fields from {len(h5_paths)} files...", level="progress", log_type="info")
                field_caches[ft] = FieldCache(
                    h5_paths=[str(p) for p in h5_paths],
                    field_type=ft,
                    low_memory=low_memory_mode,
                    slab_cache_gb=slab_cache_gb,
                )
                mode = "streaming" if field_caches[ft].streaming_mode else "memory"
                self._log(f"    {ft}-field cache ready ({mode} mode)", level="progress", log_type="info")

            # Create outer progress bar for candidates
            candidates_pbar = tqdm(
                enumerate(candidates, start=1),
                total=len(candidates),
                desc="Combining fields",
                unit="candidate",
                leave=False,
            )

            for i, candidate in candidates_pbar:
                candidates_pbar.set_description(f"Combining fields (candidate {i}/{len(candidates)})")

                if full_volume:
                    # Full-volume combination — uses pre-loaded cache if in memory mode
                    combined_path = self._combine_fields_for_candidate(
                        h5_paths=h5_paths,
                        candidate=candidate,
                        output_dir=output_dir,
                        candidate_idx=i,
                        cube_size_mm=cube_size_mm,
                        combine_chunk_size=combine_chunk_size,
                        full_volume=True,
                        field_types=field_types,
                        field_caches=field_caches,
                    )
                    combined_h5_paths.append(combined_path)
                else:
                    # Sliced combination with component progress bar
                    n_components = len(field_types) * 3  # 3 spatial components per field type
                    with tqdm(
                        total=n_components,
                        desc=f"  Candidate #{i}",
                        unit="component",
                        leave=False,
                    ) as components_pbar:
                        combined_path = self._combine_fields_for_candidate(
                            h5_paths=h5_paths,
                            candidate=candidate,
                            output_dir=output_dir,
                            candidate_idx=i,
                            cube_size_mm=cube_size_mm,
                            progress_bar=components_pbar,
                            field_types=field_types,
                        )
                        combined_h5_paths.append(combined_path)

            candidates_pbar.close()

            # Clean up field caches (closes file handles in streaming mode)
            for fc in field_caches.values():
                fc.close()

        # Step 3: Extract dosimetric metric for each candidate
        metric_key = "peak_sar_10g_W_kg" if extraction_metric == "sar" else "peak_sapd_w_m2"
        metric_unit = "W/kg" if extraction_metric == "sar" else "W/m2"
        subtask_name = "auto_induced_extract_sar" if extraction_metric == "sar" else "auto_induced_extract_sapd"

        with self.study.subtask(subtask_name):
            extraction_results = []
            for i, combined_h5 in enumerate(combined_h5_paths):
                if combined_h5 and combined_h5.exists():
                    # Each candidate gets its own output subdirectory
                    candidate_output_dir = Path(output_dir) / f"candidate_{i + 1:02d}"
                    candidate_output_dir.mkdir(parents=True, exist_ok=True)

                    if extraction_metric == "sar":
                        result = self._extract_sar(
                            combined_h5=combined_h5,
                            candidate_idx=i + 1,
                            candidate=candidates[i],
                            input_h5=input_h5,
                            candidate_output_dir=candidate_output_dir,
                            save_intermediate_files=save_intermediate_files,
                        )
                    else:
                        result = self._extract_sapd(
                            combined_h5=combined_h5,
                            candidate_idx=i + 1,
                            candidate=candidates[i],
                            cube_size_mm=cube_size_mm,
                            input_h5=input_h5,
                            save_intermediate_files=save_intermediate_files,
                        )
                    extraction_results.append(result)

                    # Log per-candidate progress
                    metric_val = result.get(metric_key)
                    metric_str = f"{metric_val:.4e} {metric_unit}" if metric_val else "ERROR"
                    self._log(
                        f"    Candidate #{i + 1}/{len(candidates)}: {metric_str}",
                        level="progress",
                        log_type="info",
                    )
                else:
                    extraction_results.append({"error": f"Combined H5 not found: {combined_h5}"})

        # Find worst case
        worst_case = self._find_worst_case(extraction_results, metric_key=metric_key)

        if worst_case and worst_case.get(metric_key):
            metric_label = "SAR 10g" if extraction_metric == "sar" else "SAPD"
            self._log(
                f"  - Worst-case {metric_label}: {worst_case[metric_key]:.4e} {metric_unit} (candidate #{worst_case.get('candidate_idx')})",
                level="progress",
                log_type="success",
            )

        # Export proxy-metric correlation data
        correlation_data = []
        metric_col = "sar_10g_W_kg" if extraction_metric == "sar" else "sapd_w_m2"
        for i, (candidate, ext_result) in enumerate(zip(candidates, extraction_results)):
            proxy_score = candidate.get("hotspot_score", candidate.get("metric_sum", 0.0))
            metric_value = ext_result.get(metric_key)
            if metric_value is not None:
                entry = {
                    "candidate_idx": i + 1,
                    "voxel_x": candidate["voxel_idx"][0],
                    "voxel_y": candidate["voxel_idx"][1],
                    "voxel_z": candidate["voxel_idx"][2],
                    "proxy_score": proxy_score,
                    metric_col: metric_value,
                }
                # Add distance to skin if available
                if "distance_to_skin_mm" in candidate:
                    entry["distance_to_skin_mm"] = candidate["distance_to_skin_mm"]
                correlation_data.append(entry)
        if correlation_data:
            import csv

            corr_filename = f"proxy_{extraction_metric}_correlation.csv"
            corr_path = Path(output_dir) / corr_filename
            with open(corr_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=correlation_data[0].keys())
                writer.writeheader()
                writer.writerows(correlation_data)
            self.verbose_logger.info(f"  Exported proxy-{extraction_metric.upper()} correlation to {corr_path.name}")

        return {
            "phantom": self.phantom_name,
            "frequency_mhz": self.freq,
            "extraction_metric": extraction_metric,
            "candidates": candidates,
            "combined_h5_files": [str(p) for p in combined_h5_paths if p],
            "extraction_results": extraction_results,
            "worst_case": worst_case,
        }

    def _find_focus_candidates(
        self,
        h5_paths: list[Path],
        input_h5: Path,
        top_n: int,
        search_metric: str = "E_z_magnitude",
        output_dir: Path | None = None,
    ) -> list[dict]:
        """Find top-N worst-case focus candidates.

        Args:
            h5_paths: List of _Output.h5 file paths.
            input_h5: Path to _Input.h5 for skin mask.
            top_n: Number of candidates to return.
            search_metric: "E_z_magnitude" (MRT-style) or "poynting_z" (SAPD-style).
                Only used in skin mode.
            output_dir: Directory for output files (CSV exports).

        Returns:
            List of candidate dicts with voxel indices, scores, and phase weights.
        """
        import time

        import numpy as np

        from .focus_optimizer import compute_optimal_phases, compute_weights

        start_time = time.monotonic()

        # Get search config
        auto_cfg = self.config["auto_induced"] or {}
        search_cfg = auto_cfg.get("search", {})
        cube_size_mm = auto_cfg.get("cube_size_mm", 50.0)

        # Extract search parameters
        search_mode = search_cfg.get("mode", "skin")
        n_samples = search_cfg.get("n_samples", 100)
        random_seed = search_cfg.get("random_seed", None)
        shell_size_mm = search_cfg.get("shell_size_mm", 10.0)
        selection_percentile = search_cfg.get("selection_percentile", 95.0)
        min_candidate_distance_mm = search_cfg.get("min_candidate_distance_mm", 50.0)
        low_memory_mode = search_cfg.get("low_memory_mode", None)
        slab_cache_gb = search_cfg.get("slab_cache_gb", 2.0)

        self._log(
            f"  Search mode: {search_mode}",
            level="progress",
            log_type="info",
        )

        try:
            focus_indices, weights, info = find_focus_and_compute_weights(
                h5_paths=[str(p) for p in h5_paths],
                input_h5_path=str(input_h5),
                top_n=top_n,
                metric=search_metric,
                search_mode=search_mode,
                n_samples=n_samples,
                cube_size_mm=cube_size_mm,
                random_seed=random_seed,
                shell_size_mm=shell_size_mm,
                selection_percentile=selection_percentile,
                min_candidate_distance_mm=min_candidate_distance_mm,
                low_memory=low_memory_mode,
                slab_cache_gb=slab_cache_gb,
            )

            # Build list of candidate dicts
            candidates: list[dict] = []
            all_indices = info.get("all_focus_indices", [focus_indices])

            # Get score array based on search mode
            if search_mode == "air":
                all_scores = info.get("all_hotspot_scores", [info.get("max_hotspot_score", 0.0)])
                score_key = "hotspot_score"
            else:
                all_scores = info.get("all_metric_sums", [info.get("max_metric_sum", 0.0)])
                score_key = "metric_sum"

            # Ensure we're working with arrays
            if not isinstance(all_indices, np.ndarray):
                all_indices = np.array([all_indices]) if top_n == 1 else np.array(all_indices)
            if not isinstance(all_scores, np.ndarray):
                all_scores = np.array([all_scores]) if top_n == 1 else np.array(all_scores)

            # Get pre-computed phases/weights if available (air mode computes them while cache is alive)
            precomputed_weights = info.get("all_candidate_weights", None)
            # Get pre-computed distances for selected candidates (air mode only)
            candidate_distances = info.get("candidate_distances_mm", None)

            for i in range(min(top_n, len(all_indices))):
                voxel_idx = all_indices[i] if top_n > 1 else all_indices
                score = float(all_scores[i]) if top_n > 1 else float(all_scores[0])

                # Use pre-computed weights if available, otherwise compute (skin mode fallback)
                if precomputed_weights is not None and i < len(precomputed_weights):
                    candidate_weights = precomputed_weights[i]
                else:
                    # Fallback: compute phases (only needed for skin mode)
                    phases = compute_optimal_phases([str(p) for p in h5_paths], voxel_idx)
                    candidate_weights = compute_weights(phases)

                candidate_dict = {
                    "voxel_idx": list(voxel_idx) if hasattr(voxel_idx, "__iter__") else voxel_idx,
                    score_key: score,
                    # Keep metric_sum for backward compatibility
                    "metric_sum": score,
                    "phase_weights": candidate_weights,
                    "search_mode": search_mode,
                }

                # Add distance to skin if available (air mode only)
                if candidate_distances is not None and i < len(candidate_distances):
                    candidate_dict["distance_to_skin_mm"] = float(candidate_distances[i])

                candidates.append(candidate_dict)

            elapsed = time.monotonic() - start_time
            self.verbose_logger.info(f"Found {len(candidates)} focus candidate(s) in {elapsed:.2f}s")
            for i, c in enumerate(candidates):
                dist_str = f", dist={c['distance_to_skin_mm']:.1f}mm" if "distance_to_skin_mm" in c else ""
                self.verbose_logger.info(f"  Candidate #{i + 1}: voxel {c['voxel_idx']}, {score_key}={c[score_key]:.4e}{dist_str}")

            # Export all scores to CSV for distribution analysis
            all_scores_data = info.get("all_scores_data", [])
            if all_scores_data and output_dir:
                import csv

                csv_path = Path(output_dir) / "all_proxy_scores.csv"
                with open(csv_path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=all_scores_data[0].keys())
                    writer.writeheader()
                    writer.writerows(all_scores_data)
                self.verbose_logger.info(f"  Exported {len(all_scores_data)} proxy scores to {csv_path.name}")

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
        progress_bar=None,
        full_volume: bool = False,
        field_types: tuple = ("E", "H"),
        combine_chunk_size: int = 50,
        field_caches: dict | None = None,
    ) -> Path | None:
        """Combine E/H fields for a focus candidate.

        Args:
            h5_paths: List of _Output.h5 file paths.
            candidate: Candidate dict with voxel_idx and phase_weights.
            output_dir: Directory to write combined H5.
            candidate_idx: 1-based index for naming.
            cube_size_mm: Size of extraction cube in mm (only used for sliced mode).
            progress_bar: Optional tqdm progress bar to update (only used for sliced mode).
            full_volume: If True, combine full volume using chunked processing.
            field_types: Which field types to combine, e.g. ("E",) for SAR or ("E", "H") for SAPD.
            combine_chunk_size: Number of z-slices per chunk (fallback when no cache).
            field_caches: Dict mapping field_type -> FieldCache. If provided and cache
                is in memory mode, uses pre-loaded arrays (no file I/O per candidate).

        Returns:
            Path to combined H5 file, or None if failed.
        """
        import time

        output_filename = f"combined_candidate{candidate_idx}_Output.h5"
        output_path = output_dir / output_filename

        start_time = time.monotonic()

        try:
            if full_volume:
                from .field_combiner import combine_fields_chunked

                result: dict = {}
                for field_type in field_types:
                    fc = (field_caches or {}).get(field_type)
                    result = combine_fields_chunked(
                        h5_paths=[str(p) for p in h5_paths],
                        weights=candidate["phase_weights"],
                        template_h5_path=str(h5_paths[0]),
                        output_h5_path=str(output_path),
                        field_types=(field_type,),
                        chunk_size=combine_chunk_size,
                        field_cache=fc,
                    )
            else:
                result = combine_fields_sliced(
                    h5_paths=[str(p) for p in h5_paths],
                    weights=candidate["phase_weights"],
                    template_h5_path=str(h5_paths[0]),
                    output_h5_path=str(output_path),
                    center_idx=candidate["voxel_idx"],
                    side_length_mm=cube_size_mm,
                    field_types=field_types,
                    progress_bar=progress_bar,
                )

            elapsed = time.monotonic() - start_time
            shape_info = result.get("grid_shape", result.get("sliced_shape", "unknown"))
            mode_str = "full-volume" if full_volume else "sliced"
            self.verbose_logger.info(f"Candidate #{candidate_idx}: {shape_info} [{mode_str}] ({elapsed:.2f}s)")

            return output_path

        except Exception as e:
            self._log(f"      ERROR combining fields: {e}", log_type="error")
            return None

    def _extract_sar(
        self,
        combined_h5: Path,
        candidate_idx: int,
        candidate: dict,
        input_h5: Path,
        candidate_output_dir: Path | None = None,
        save_intermediate_files: bool = False,
    ) -> dict:
        """Run the full SAR extraction pipeline on a combined H5 file.

        Uses the existing SarExtractor and Reporter classes (via AutoInducedSarContext shim)
        to produce the same outputs as a normal simulation extraction:
          - sar_results.json  (full metrics: whole-body SAR, peak 10g, group SAR, peak details)
          - sar_stats_all_tissues.pkl  (tissue DataFrame + groups for programmatic access)
          - sar_stats_all_tissues.html  (human-readable tissue table)

        These are written to candidate_output_dir (e.g. auto_induced/candidate_01/).

        The project must already be open with phantom geometry loaded so that
        the SAR evaluator can map E-field to tissue conductivity.

        Args:
            combined_h5: Path to combined _Output.h5 file (full-volume, E-field only).
            candidate_idx: 1-based candidate index (used for naming and logging).
            candidate: Candidate dict (not used for SAR, kept for API consistency).
            input_h5: Path to an _Input.h5 file (not used for SAR, kept for API consistency).
            candidate_output_dir: Directory to write per-candidate results into.
                Defaults to combined_h5.parent / f"candidate_{candidate_idx:02d}".
            save_intermediate_files: If True, save the Sim4Life project after extraction
                for debugging.

        Returns:
            Dict with at minimum 'candidate_idx' and 'peak_sar_10g_W_kg'. On error,
            contains 'error' key instead of metric values.
        """
        from .auto_induced_sar_context import AutoInducedSarContext, AutoInducedReporter, save_candidate_json
        from .sar_extractor import SarExtractor

        if candidate_output_dir is None:
            candidate_output_dir = combined_h5.parent / f"candidate_{candidate_idx:02d}"
        candidate_output_dir.mkdir(parents=True, exist_ok=True)

        self.verbose_logger.info(f"Extracting SAR (full pipeline) from {combined_h5.name} -> {candidate_output_dir.name}/")

        try:
            import s4l_v1.analysis as analysis
            import s4l_v1.document as document

            # --- Step 1: Create SimulationExtractor from the combined H5 ---
            sim_extractor = analysis.extractors.SimulationExtractor(inputs=[])
            sim_extractor.Name = f"AutoInduced_SAR_Candidate{candidate_idx}"
            sim_extractor.FileName = str(combined_h5)
            sim_extractor.UpdateAttributes()
            document.AllAlgorithms.Add(sim_extractor)

            # --- Step 2: Build context shim and run SarExtractor ---
            context = AutoInducedSarContext(self, candidate_output_dir)
            results_data: dict = {}

            sar_extractor = SarExtractor(context, results_data)  # type: ignore[arg-type]
            sar_extractor.extract_sar_statistics(sim_extractor)

            # --- Step 3: Save reports if extraction succeeded ---
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

            # --- Step 4: Cleanup Sim4Life algorithms ---
            try:
                document.AllAlgorithms.Remove(sim_extractor)
            except Exception:
                pass

            # Optional: save debug project
            if save_intermediate_files:
                try:
                    debug_path = str(combined_h5).replace("_Output.h5", "_intermediate.smash")
                    document.SaveAs(debug_path)
                except Exception:
                    pass

            # Build return dict for worst-case comparison and summary JSON
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
            return {
                "candidate_idx": candidate_idx,
                "error": str(e),
            }

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

        Uses the existing SAPD extraction infrastructure. The project should
        already be open with the phantom geometry loaded.

        Args:
            combined_h5: Path to combined _Output.h5 file.
            candidate_idx: 1-based candidate index.
            candidate: Candidate dict with 'voxel_idx' for center location.
            cube_size_mm: Size of the bounding box for mesh slicing.
            input_h5: Path to an input H5 to read grid axes for voxel->mm conversion.
            save_intermediate_files: If True, save smash file after extraction for inspection.

        Returns:
            Dict with SAPD extraction results.
        """

        import h5py

        from ..utils.mesh_slicer import slice_entity_to_box, voxel_idx_to_mm

        self.verbose_logger.info(f"Extracting SAPD from {combined_h5.name}")

        try:
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

            # Get EM sensor extractor
            em_sensor_extractor = sim_extractor["Overall Field"]
            em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"
            em_sensor_extractor.UpdateAttributes()
            document.AllAlgorithms.Add(em_sensor_extractor)
            em_sensor_extractor.Update()

            # Try to load cached skin first (avoids duplicate entity name issues)
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
                    pass  # Fall through to create it

            if united_entity is None:
                # No cache - look up skin entities and unite them
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
                    united_entity = model.Unite([e.Clone() for e in skin_entities])
                else:
                    united_entity = skin_entities[0].Clone()

                # Save to cache for next time
                try:
                    os.makedirs(cache_dir, exist_ok=True)
                    model.Export([united_entity], cache_path)
                except Exception:
                    pass  # Caching is optional

            surface_entity = united_entity.Clone()  # Clone the cached entity for slicing
            surface_entity.Name = f"AutoInduced_Skin_{candidate_idx}"

            # Slice the skin mesh to a box around the focus point (critical for speed!)
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

            # Create ModelToGridFilter (matching SapdExtractor pattern)
            model_to_grid_filter = analysis.core.ModelToGridFilter(inputs=[])
            model_to_grid_filter.Name = f"AutoInduced_SkinSurface_{candidate_idx}"
            model_to_grid_filter.Entity = surface_entity
            model_to_grid_filter.UpdateAttributes()
            document.AllAlgorithms.Add(model_to_grid_filter)

            # Create SAPD evaluator with correct inputs (matching SapdExtractor)
            # Inputs: Poynting Vector S(x,y,z,f0) and Surface
            inputs = [em_sensor_extractor.Outputs["S(x,y,z,f0)"], model_to_grid_filter.Outputs["Surface"]]

            sapd_evaluator = analysis.em_evaluators.GenericSAPDEvaluator(inputs=inputs)
            sapd_evaluator.AveragingArea = 4.0, units.SquareCentiMeters
            sapd_evaluator.Threshold = 0.01, units.Meters  # 10 mm
            sapd_evaluator.UpdateAttributes()
            document.AllAlgorithms.Add(sapd_evaluator)

            # Get report and update
            sapd_report = sapd_evaluator.Outputs["Spatial-Averaged Power Density Report"]
            sapd_report.Update()

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

            # Optionally save debug smash file with focus center marker
            if save_intermediate_files:
                try:
                    focus_point = model.CreatePoint(model.Vec3(center_mm[0], center_mm[1], center_mm[2]))
                    focus_point.Name = f"Focus_Center_Candidate{candidate_idx}"
                except Exception:
                    pass
                debug_smash_path = str(combined_h5).replace("_Output.h5", "_intermediate.smash")
                try:
                    document.SaveAs(debug_smash_path)
                except Exception:
                    pass

            result = {
                "candidate_idx": candidate_idx,
                "peak_sapd_w_m2": float(peak_sapd) if peak_sapd else None,
                "peak_location_m": list(peak_loc) if peak_loc else None,
                "combined_h5": str(combined_h5),
            }

            # Cleanup: remove temporary entities and algorithms to avoid memory growth
            try:
                # Remove algorithms (in reverse order of creation)
                document.AllAlgorithms.Remove(sapd_evaluator)
                document.AllAlgorithms.Remove(model_to_grid_filter)
                document.AllAlgorithms.Remove(em_sensor_extractor)
                document.AllAlgorithms.Remove(sim_extractor)

                # Remove temporary model entities
                surface_entity.Delete()
                united_entity.Delete()
            except Exception:
                pass  # Cleanup is best-effort

            return result

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

    def _find_worst_case(self, results: list[dict], metric_key: str = "peak_sapd_w_m2") -> dict:
        """Find the worst-case (highest metric) result.

        Args:
            results: List of extraction result dicts.
            metric_key: Key to compare (e.g., "peak_sapd_w_m2" or "peak_sar_10g_W_kg").

        Returns:
            The result dict with highest metric value.
        """
        worst = None
        worst_val = -1.0

        for result in results:
            val = result.get(metric_key)
            if val is not None and val > worst_val:
                worst_val = val
                worst = result

        return worst or {}
