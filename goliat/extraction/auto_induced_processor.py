"""Auto-induced exposure processor for far-field studies.

This module orchestrates the auto-induced exposure analysis workflow:
1. Focus point search - find worst-case focus locations on skin
2. Field combination - combine E/H fields with optimal phases
3. SAPD extraction - extract peak SAPD using existing infrastructure

This is called as a post-processing step after all environmental simulations
for a (phantom, frequency) pair complete.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..logging_manager import LoggingMixin
from .auto_induced_extractors import _AutoInducedExtractionMixin
from .field_combiner_sliced import combine_fields_sliced
from .focus_optimizer import find_focus_and_compute_weights

if TYPE_CHECKING:
    from ..studies.far_field_study import FarFieldStudy


@dataclass
class _CombineRequest:
    """Parameters for a single field combination operation."""

    h5_paths: list[Path]
    candidate: dict
    output_dir: Path
    candidate_idx: int
    cube_size_mm: float
    progress_bar: Any = field(default=None, repr=False)
    full_volume: bool = False
    field_types: tuple = ("E", "H")
    combine_chunk_size: int = 50
    field_caches: dict | None = None


class AutoInducedProcessor(LoggingMixin, _AutoInducedExtractionMixin):
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
            from .field_cache import FieldCache

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
                        _CombineRequest(
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
                            _CombineRequest(
                                h5_paths=h5_paths,
                                candidate=candidate,
                                output_dir=output_dir,
                                candidate_idx=i,
                                cube_size_mm=cube_size_mm,
                                progress_bar=components_pbar,
                                field_types=field_types,
                            )
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

    def _combine_fields_for_candidate(self, req: _CombineRequest) -> Path | None:
        """Combine E/H fields for a focus candidate.

        Args:
            req: All parameters for this combination operation.

        Returns:
            Path to combined H5 file, or None if failed.
        """
        import time

        output_path = req.output_dir / f"combined_candidate{req.candidate_idx}_Output.h5"
        start_time = time.monotonic()

        try:
            if req.full_volume:
                from .field_combiner import combine_fields_chunked

                result: dict = {}
                for field_type in req.field_types:
                    fc = (req.field_caches or {}).get(field_type)
                    result = combine_fields_chunked(
                        h5_paths=[str(p) for p in req.h5_paths],
                        weights=req.candidate["phase_weights"],
                        template_h5_path=str(req.h5_paths[0]),
                        output_h5_path=str(output_path),
                        field_types=(field_type,),
                        chunk_size=req.combine_chunk_size,
                        field_cache=fc,
                    )
            else:
                result = combine_fields_sliced(
                    h5_paths=[str(p) for p in req.h5_paths],
                    weights=req.candidate["phase_weights"],
                    template_h5_path=str(req.h5_paths[0]),
                    output_h5_path=str(output_path),
                    center_idx=req.candidate["voxel_idx"],
                    side_length_mm=req.cube_size_mm,
                    field_types=req.field_types,
                    progress_bar=req.progress_bar,
                )

            elapsed = time.monotonic() - start_time
            shape_info = result.get("grid_shape", result.get("sliced_shape", "unknown"))
            mode_str = "full-volume" if req.full_volume else "sliced"
            self.verbose_logger.info(f"Candidate #{req.candidate_idx}: {shape_info} [{mode_str}] ({elapsed:.2f}s)")

            return output_path

        except Exception as e:
            self._log(f"      ERROR combining fields: {e}", log_type="error")
            return None

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
