import re
import traceback
from typing import TYPE_CHECKING

import pandas as pd

from ..logging_manager import LoggingMixin

if TYPE_CHECKING:
    import s4l_v1.analysis as analysis

    from ..results_extractor import ResultsExtractor


class SarExtractor(LoggingMixin):
    """Handles the extraction of SAR (Specific Absorption Rate) statistics."""

    def __init__(self, parent: "ResultsExtractor", results_data: dict):
        """Initializes the SarExtractor.

        Args:
            parent: The parent ResultsExtractor instance.
            results_data: The dictionary to store the extracted data.
        """
        self.parent = parent
        self.config = parent.config
        self.simulation = parent.simulation
        self.phantom_name = parent.phantom_name
        self.placement_name = parent.placement_name
        self.verbose_logger = parent.verbose_logger
        self.progress_logger = parent.progress_logger
        self.results_data = results_data

        import s4l_v1.analysis
        import s4l_v1.document
        import s4l_v1.units as units

        self.analysis = s4l_v1.analysis
        self.document = s4l_v1.document
        self.units = units

    def extract_sar_statistics(self, simulation_extractor: "analysis.Extractor"):
        """Extracts detailed SAR statistics for all tissues.

        Runs the `SarStatisticsEvaluator` and processes its output into a
        pandas DataFrame.

        Args:
            simulation_extractor: The results extractor from the simulation object.
        """
        self._log(
            "  - Extracting SAR statistics for all tissues...", log_type="progress"
        )
        with self.parent.study.subtask("extract_sar_statistics"):
            try:
                em_sensor_extractor = simulation_extractor["Overall Field"]
                em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"
                self.document.AllAlgorithms.Add(em_sensor_extractor)
                em_sensor_extractor.Update()

                inputs = [em_sensor_extractor.Outputs["EM E(x,y,z,f0)"]]
                sar_stats_evaluator = (
                    self.analysis.em_evaluators.SarStatisticsEvaluator(inputs=inputs)
                )
                sar_stats_evaluator.PeakSpatialAverageSAR = True
                sar_stats_evaluator.PeakSAR.TargetMass = 10.0, self.units.Unit("g")
                sar_stats_evaluator.UpdateAttributes()
                self.document.AllAlgorithms.Add(sar_stats_evaluator)
                sar_stats_evaluator.Update()

                stats_output = sar_stats_evaluator.Outputs
                results = (
                    stats_output.item_at(0).Data
                    if len(stats_output) > 0
                    and hasattr(stats_output.item_at(0), "Data")
                    else None
                )
                self.document.AllAlgorithms.Remove(sar_stats_evaluator)

                if not (
                    results
                    and hasattr(results, "NumberOfRows")
                    and results.NumberOfRows() > 0
                ):
                    self._log(
                        "  - WARNING: No SAR statistics data found.", log_type="warning"
                    )
                    return

                columns = ["Tissue"] + [cap for cap in results.ColumnMainCaptions]
                data = [
                    [
                        re.sub(r"\s*\(.*\)\s*$", "", results.RowCaptions[i])
                        .strip()
                        .replace(")", "")
                    ]
                    + [results.Value(i, j) for j in range(results.NumberOfColumns())]
                    for i in range(results.NumberOfRows())
                ]

                df = pd.DataFrame(data, columns=columns)
                numeric_cols = [col for col in df.columns if col != "Tissue"]
                df[numeric_cols] = (
                    df[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
                )

                tissue_groups = self._define_tissue_groups(df["Tissue"].tolist())
                group_sar_stats = self._calculate_group_sar(df, tissue_groups)

                for group, data in group_sar_stats.items():
                    self.results_data[f"{group}_weighted_avg_sar"] = data[
                        "weighted_avg_sar"
                    ]
                    self.results_data[f"{group}_peak_sar"] = data["peak_sar"]

                all_regions_row = df[df["Tissue"] == "All Regions"]
                if not all_regions_row.empty:
                    mass_averaged_sar = all_regions_row["Mass-Averaged SAR"].iloc[0]
                    if self.parent.study_type == "near_field":
                        sar_key = (
                            "head_SAR"
                            if self.placement_name.lower()
                            in ["front_of_eyes", "by_cheek"]
                            else "trunk_SAR"
                        )
                        self.results_data[sar_key] = float(mass_averaged_sar)
                    else:
                        self.results_data["whole_body_sar"] = float(mass_averaged_sar)

                    peak_sar_col_name = (
                        "Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)"
                    )
                    if peak_sar_col_name in all_regions_row.columns:
                        self.results_data["peak_sar_10g_W_kg"] = float(
                            all_regions_row[peak_sar_col_name].iloc[0]
                        )

                self.extract_peak_sar_details(em_sensor_extractor)
                self.results_data.update(
                    {
                        "_temp_sar_df": df,
                        "_temp_tissue_groups": tissue_groups,
                        "_temp_group_sar_stats": group_sar_stats,
                    }
                )

            except Exception as e:
                self._log(
                    f"  - ERROR: An unexpected error during all-tissue SAR statistics extraction: {e}",
                    level="progress",
                    log_type="error",
                )
                self.verbose_logger.error(traceback.format_exc())

    def _define_tissue_groups(self, available_tissues: list) -> dict:
        """Defines tissue groups from material mapping or keyword matching.

        Args:
            available_tissues: A list of tissue names available in the simulation.

        Returns:
            A dictionary where keys are group names and values are lists of tissue names.
        """
        material_mapping = self.config.get_material_mapping(self.phantom_name)

        if "_tissue_groups" in material_mapping:
            self._log(
                f"  - Loading tissue groups for '{self.phantom_name}' from material_name_mapping.json",
                log_type="info",
            )
            phantom_groups = material_mapping["_tissue_groups"]
            tissue_groups = {}

            for group_name, tissue_list in phantom_groups.items():
                s4l_names_in_group = set(tissue_list)
                tissue_groups[group_name] = [
                    t for t in available_tissues if t in s4l_names_in_group
                ]
            return tissue_groups

        self._log(
            "  - WARNING: '_tissue_groups' not found in material mapping. "
            "Falling back to keyword-based tissue grouping.",
            log_type="warning",
        )
        groups = {
            "eyes_group": ["eye", "cornea", "sclera", "lens", "vitreous"],
            "skin_group": ["skin"],
            "brain_group": [
                "brain",
                "commissura",
                "midbrain",
                "pineal",
                "hypophysis",
                "medulla_oblongata",
                "pons",
                "thalamus",
                "hippocampus",
                "cerebellum",
            ],
        }
        return {
            group: [
                t for t in available_tissues if any(k in t.lower() for k in keywords)
            ]
            for group, keywords in groups.items()
        }

    def _calculate_group_sar(self, df: pd.DataFrame, tissue_groups: dict) -> dict:
        """Calculates the weighted average and peak SAR for defined tissue groups.

        Args:
            df: The DataFrame with detailed SAR statistics.
            tissue_groups: A dictionary defining the composition of tissue groups.

        Returns:
            A dictionary with calculated SAR values for each group.
        """
        group_sar_data = {}
        peak_sar_col = "Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)"
        for group_name, tissues in tissue_groups.items():
            group_df = df[df["Tissue"].isin(tissues)]
            if not group_df.empty:
                total_mass = group_df["Total Mass"].sum()
                weighted_avg_sar = (
                    (group_df["Total Mass"] * group_df["Mass-Averaged SAR"]).sum()
                    / total_mass
                    if total_mass > 0
                    else 0
                )
                peak_sar = (
                    group_df[peak_sar_col].max()
                    if peak_sar_col in group_df.columns
                    else -1.0
                )
                group_sar_data[group_name] = {
                    "weighted_avg_sar": weighted_avg_sar,
                    "peak_sar": peak_sar,
                }
        return group_sar_data

    def extract_peak_sar_details(self, em_sensor_extractor: "analysis.Extractor"):
        """Extracts detailed information about the peak spatial-average SAR (psSAR).

        Args:
            em_sensor_extractor: The 'Overall Field' results extractor.
        """
        self._log("  - Extracting peak SAR details...", log_type="progress")
        try:
            inputs = [em_sensor_extractor.Outputs["SAR(x,y,z,f0)"]]
            average_sar_field_evaluator = (
                self.analysis.em_evaluators.AverageSarFieldEvaluator(inputs=inputs)
            )
            average_sar_field_evaluator.TargetMass = 10.0, self.units.Unit("g")
            average_sar_field_evaluator.UpdateAttributes()
            self.document.AllAlgorithms.Add(average_sar_field_evaluator)
            average_sar_field_evaluator.Update()

            peak_sar_output = average_sar_field_evaluator.Outputs[
                "Peak Spatial SAR (psSAR) Results"
            ]
            peak_sar_output.Update()

            data_collection = peak_sar_output.Data.DataSimpleDataCollection
            if data_collection:
                self.results_data["peak_sar_details"] = {
                    key: data_collection.FieldValue(key, 0)
                    for key in data_collection.Keys()
                }
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
