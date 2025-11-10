import re
import traceback
from typing import TYPE_CHECKING

import pandas as pd

from ..logging_manager import LoggingMixin
from .tissue_grouping import TissueGrouper

if TYPE_CHECKING:
    import s4l_v1.analysis as analysis

    from ..results_extractor import ResultsExtractor


class SarExtractor(LoggingMixin):
    """Extracts SAR statistics from simulation results.

    Uses Sim4Life's SarStatisticsEvaluator to compute mass-averaged SAR,
    peak spatial-average SAR (10g), and tissue-specific metrics. Groups
    tissues into logical groups (eyes, skin, brain) for analysis.
    """

    def __init__(self, parent: "ResultsExtractor", results_data: dict):
        """Sets up the SAR extractor.

        Args:
            parent: Parent ResultsExtractor instance.
            results_data: Dict to store extracted SAR data.
        """
        self.parent = parent
        self.config = parent.config
        self.simulation = parent.simulation
        self.phantom_name = parent.phantom_name
        self.placement_name = parent.placement_name
        self.verbose_logger = parent.verbose_logger
        self.progress_logger = parent.progress_logger
        self.gui = parent.gui
        self.results_data = results_data

        import s4l_v1.analysis
        import s4l_v1.document
        import s4l_v1.units as units

        self.analysis = s4l_v1.analysis
        self.document = s4l_v1.document
        self.units = units

        self.tissue_grouper = TissueGrouper(self.config, self.phantom_name, self)

    def extract_sar_statistics(self, simulation_extractor: "analysis.Extractor"):  # type: ignore
        """Extracts comprehensive SAR statistics for all tissues.

        This is the main SAR extraction method that orchestrates the entire process.
        It uses Sim4Life's SarStatisticsEvaluator to compute standardized SAR metrics
        according to IEEE/IEC standards.

        The process:
        1. Extracts the 'Overall Field' E-field data from simulation results
        2. Creates a SarStatisticsEvaluator configured for 10g peak spatial-average SAR
        3. Processes the evaluator output into a pandas DataFrame
        4. Groups tissues into logical categories (eyes, skin, brain)
        5. Calculates weighted-average SAR for each group (mass-weighted)
        6. Extracts peak SAR details (location, coordinates, etc.)
        7. Stores both per-tissue and group-level results

        The results include mass-averaged SAR, peak spatial-average SAR (10g), and
        tissue-specific metrics. For near-field studies, also extracts head/trunk SAR
        based on placement scenario. For far-field, extracts whole-body SAR.

        Args:
            simulation_extractor: Results extractor from the simulation object.
        """
        self._log("    - Extract SAR statistics...", level="progress", log_type="progress")
        try:
            elapsed = 0.0
            if self.parent.study:
                with self.parent.study.profiler.subtask("extract_sar_statistics"):  # type: ignore
                    em_sensor_extractor = self._setup_em_sensor_extractor(simulation_extractor)
                    results = self._evaluate_sar_statistics(em_sensor_extractor)

                    if not results:
                        return

                    df = self._create_sar_dataframe(results)
                    tissue_groups = self.tissue_grouper.group_tissues(df["Tissue"].tolist())
                    group_sar_stats = self._calculate_group_sar(df, tissue_groups)

                    self._store_group_sar_results(group_sar_stats)
                    self._store_all_regions_sar(df)
                    self.extract_peak_sar_details(em_sensor_extractor)
                    self._store_temporary_data(df, tissue_groups, group_sar_stats)

                elapsed = self.parent.study.profiler.subtask_times["extract_sar_statistics"][-1]
            self._log(f"      - Subtask 'extract_sar_statistics' done in {elapsed:.2f}s", log_type="verbose")
            self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        except Exception as e:
            self._log(
                f"  - ERROR: An unexpected error during all-tissue SAR statistics extraction: {e}",
                level="progress",
                log_type="error",
            )
            self.verbose_logger.error(traceback.format_exc())

    def _setup_em_sensor_extractor(self, simulation_extractor: "analysis.Extractor") -> "analysis.Extractor":  # type: ignore
        """Sets up and updates the EM sensor extractor for SAR analysis.

        Args:
            simulation_extractor: Results extractor from the simulation object.

        Returns:
            Configured EM sensor extractor.
        """
        em_sensor_extractor = simulation_extractor["Overall Field"]
        em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"
        self.document.AllAlgorithms.Add(em_sensor_extractor)
        em_sensor_extractor.Update()
        return em_sensor_extractor

    def _evaluate_sar_statistics(self, em_sensor_extractor: "analysis.Extractor") -> object | None:  # type: ignore
        """Evaluates SAR statistics using Sim4Life's SarStatisticsEvaluator.

        Args:
            em_sensor_extractor: Configured EM sensor extractor.

        Returns:
            Results data object if available, None otherwise.
        """
        inputs = [em_sensor_extractor.Outputs["EM E(x,y,z,f0)"]]
        sar_stats_evaluator = self.analysis.em_evaluators.SarStatisticsEvaluator(inputs=inputs)
        sar_stats_evaluator.PeakSpatialAverageSAR = True
        sar_stats_evaluator.PeakSAR.TargetMass = 10.0, self.units.Unit("g")
        sar_stats_evaluator.UpdateAttributes()
        self.document.AllAlgorithms.Add(sar_stats_evaluator)
        sar_stats_evaluator.Update()

        stats_output = sar_stats_evaluator.Outputs
        results = stats_output.item_at(0).Data if len(stats_output) > 0 and hasattr(stats_output.item_at(0), "Data") else None
        self.document.AllAlgorithms.Remove(sar_stats_evaluator)

        if not (results and hasattr(results, "NumberOfRows") and results.NumberOfRows() > 0):
            self._log("  - WARNING: No SAR statistics data found.", log_type="warning")
            return None

        return results

    def _create_sar_dataframe(self, results: object) -> pd.DataFrame:
        """Creates a pandas DataFrame from SAR statistics results.

        Args:
            results: Results data object from SarStatisticsEvaluator.

        Returns:
            DataFrame with SAR statistics per tissue.
        """
        # Type ignore needed because Sim4Life API types are not fully typed
        columns = ["Tissue"] + [cap for cap in results.ColumnMainCaptions]  # type: ignore
        data = [
            [re.sub(r"\s*\(.*\)\s*$", "", results.RowCaptions[i]).strip().replace(")", "")]  # type: ignore
            + [results.Value(i, j) for j in range(results.NumberOfColumns())]  # type: ignore
            for i in range(results.NumberOfRows())  # type: ignore
        ]

        df = pd.DataFrame(data)
        df.columns = columns
        numeric_cols = [col for col in df.columns if col != "Tissue"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
        return df

    def _store_group_sar_results(self, group_sar_stats: dict) -> None:
        """Stores group-level SAR results in results_data.

        Args:
            group_sar_stats: Dict mapping group names to SAR statistics.
        """
        for group, data in group_sar_stats.items():
            self.results_data[f"{group}_weighted_avg_sar"] = data["weighted_avg_sar"]
            self.results_data[f"{group}_peak_sar"] = data["peak_sar"]

    def _store_all_regions_sar(self, df: pd.DataFrame) -> None:
        """Stores all-regions SAR results (head/trunk/whole-body and peak SAR).

        Args:
            df: DataFrame with SAR statistics per tissue.
        """
        all_regions_row = df[df["Tissue"] == "All Regions"]
        if not all_regions_row.empty:
            mass_averaged_sar = all_regions_row["Mass-Averaged SAR"].iloc[0]  # type: ignore
            if self.parent.study_type == "near_field":
                sar_key = "head_SAR" if self.placement_name.lower() in ["front_of_eyes", "by_cheek"] else "trunk_SAR"
                self.results_data[sar_key] = float(mass_averaged_sar)
            else:
                self.results_data["whole_body_sar"] = float(mass_averaged_sar)

            peak_sar_col_name = "Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)"
            if peak_sar_col_name in all_regions_row.columns:
                self.results_data["peak_sar_10g_W_kg"] = float(all_regions_row[peak_sar_col_name].iloc[0])  # type: ignore

    def _store_temporary_data(self, df: pd.DataFrame, tissue_groups: dict, group_sar_stats: dict) -> None:
        """Stores temporary data structures for later use.

        Args:
            df: DataFrame with SAR statistics.
            tissue_groups: Dict mapping group names to tissue lists.
            group_sar_stats: Dict mapping group names to SAR statistics.
        """
        self.results_data.update(
            {
                "_temp_sar_df": df,
                "_temp_tissue_groups": tissue_groups,
                "_temp_group_sar_stats": group_sar_stats,
            }
        )

    def _calculate_group_sar(self, df: pd.DataFrame, tissue_groups: dict) -> dict:
        """Calculates weighted average and peak SAR for tissue groups.

        Groups tissues into logical categories (e.g., all eye tissues into 'eyes_group')
        and computes aggregated SAR metrics. The weighted average uses tissue mass as
        the weighting factor, so larger tissues contribute more to the group average.

        Formula: weighted_avg = Σ(mass_i × SAR_i) / Σ(mass_i)

        Peak SAR is simply the maximum peak SAR value across all tissues in the group,
        which identifies the worst-case exposure within that anatomical region.

        Args:
            df: DataFrame with per-tissue SAR statistics including 'Total Mass' and
                'Mass-Averaged SAR' columns.
            tissue_groups: Dict mapping group names (e.g., 'eyes_group') to lists
                          of tissue names.

        Returns:
            Dict with 'weighted_avg_sar' and 'peak_sar' for each group. Groups with
            no matching tissues are skipped.
        """
        group_sar_data = {}
        peak_sar_col = "Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)"
        for group_name, tissues in tissue_groups.items():
            group_df = df[df["Tissue"].isin(tissues)]
            if not group_df.empty:
                total_mass = group_df["Total Mass"].sum()
                weighted_avg_sar = (group_df["Total Mass"] * group_df["Mass-Averaged SAR"]).sum() / total_mass if total_mass > 0 else 0
                peak_sar = group_df[peak_sar_col].max() if peak_sar_col in group_df.columns else -1.0
                group_sar_data[group_name] = {
                    "weighted_avg_sar": weighted_avg_sar,
                    "peak_sar": peak_sar,
                }
        return group_sar_data

    def extract_peak_sar_details(self, em_sensor_extractor: "analysis.Extractor"):  # type: ignore
        """Extracts detailed metadata about the peak spatial-average SAR location.

        While the main SAR extraction gives per-tissue statistics, this method
        provides detailed information about where the absolute peak SAR occurs.
        This includes 3D coordinates, the tissue/organ containing the peak, mass
        of the 10g averaging volume, and other metadata.

        This information is useful for:
        - Understanding which anatomical region has the highest exposure
        - Verifying that peak SAR is in an expected location
        - Debugging unexpected SAR hotspots
        - Reporting peak exposure location in compliance documentation

        Uses Sim4Life's AverageSarFieldEvaluator configured for 10g spatial averaging
        to find the peak location according to IEEE/IEC 62704-1 standards.

        Args:
            em_sensor_extractor: The 'Overall Field' results extractor containing
                               the SAR field data.
        """
        self._log("  - Extracting peak SAR details...", log_type="progress")
        try:
            inputs = [em_sensor_extractor.Outputs["SAR(x,y,z,f0)"]]
            average_sar_field_evaluator = self.analysis.em_evaluators.AverageSarFieldEvaluator(inputs=inputs)
            average_sar_field_evaluator.TargetMass = 10.0, self.units.Unit("g")
            average_sar_field_evaluator.UpdateAttributes()
            self.document.AllAlgorithms.Add(average_sar_field_evaluator)
            average_sar_field_evaluator.Update()

            peak_sar_output = average_sar_field_evaluator.Outputs["Peak Spatial SAR (psSAR) Results"]
            peak_sar_output.Update()  # type: ignore

            data_collection = peak_sar_output.Data.DataSimpleDataCollection  # type: ignore
            if data_collection:
                self.results_data["peak_sar_details"] = {key: data_collection.FieldValue(key, 0) for key in data_collection.Keys()}  # type: ignore
            else:
                self._log(
                    "  - WARNING: Could not extract peak SAR details.",
                    log_type="warning",
                )

            self.document.AllAlgorithms.Remove(average_sar_field_evaluator)

        except Exception as e:
            self._log(
                f"  - ERROR: An exception occurred during peak SAR detail extraction: {e}",
                log_type="error",
            )
            self.verbose_logger.error(traceback.format_exc())
