import json
import os
import pickle
import re
import traceback

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .logging_manager import LoggingMixin


class ResultsExtractor(LoggingMixin):
    """
    Handles all post-processing and data extraction from simulation results.

    This class is responsible for extracting various metrics such as input power,
    SAR statistics, power balance, and point sensor data from a completed
    Sim4Life simulation. It also generates and saves reports in multiple formats.
    """

    def __init__(
        self,
        config,
        simulation,
        phantom_name,
        frequency_mhz,
        placement_name,
        study_type,
        verbose_logger,
        progress_logger,
        free_space=False,
        gui=None,
        study=None,
    ):
        """
        Initializes the ResultsExtractor.

        Args:
            config (Config): The configuration object for the study.
            simulation (s4l_v1.simulation.emfdtd.Simulation): The simulation object to extract results from.
            phantom_name (str): The name of the phantom model used.
            frequency_mhz (int): The simulation frequency in MHz.
            placement_name (str): The name of the placement scenario.
            study_type (str): The type of the study (e.g., 'near_field').
            verbose_logger (logging.Logger): Logger for detailed output.
            progress_logger (logging.Logger): Logger for progress updates.
            free_space (bool): Flag indicating if the simulation was run in free space.
            gui (QueueGUI, optional): The GUI proxy for updates.
            study (BaseStudy, optional): The parent study object.
        """
        self.config = config
        self.simulation = simulation
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        self.placement_name = placement_name
        self.study_type = study_type
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        self.free_space = free_space
        self.gui = gui
        self.study = study

        import s4l_v1.analysis
        import s4l_v1.document
        import s4l_v1.units as units

        self.document = s4l_v1.document
        self.analysis = s4l_v1.analysis
        self.units = units

    def extract(self):
        """
        Orchestrates the extraction of all relevant data from the simulation.

        This is the main entry point for the class, which calls specialized
        methods to extract input power, SAR statistics, power balance, and
        point sensor data, then saves the compiled results.
        """
        self._log("Extracting results...", log_type="progress")
        if not self.simulation:
            self._log(
                "  - ERROR: Simulation object not found. Skipping result extraction.",
                log_type="error",
            )
            return

        results_data = {}
        simulation_extractor = self.simulation.Results()

        if self.gui:
            self.gui.update_stage_progress("Extracting Power", 50, 100)
        self._extract_input_power(simulation_extractor, results_data)

        if not self.free_space:
            if self.gui:
                self.gui.update_stage_progress("Extracting SAR", 100, 100)
            self._extract_sar_statistics(simulation_extractor, results_data)
            self._extract_power_balance(simulation_extractor, results_data)
        else:
            self._log(
                "  - Skipping SAR statistics for free-space simulation.",
                log_type="info",
            )

        if (
            self.config.get_setting("simulation_parameters.number_of_point_sensors", 0)
            > 0
        ):
            if self.gui:
                self.gui.update_stage_progress("Extracting Point Sensors", 75, 100)
            self._extract_point_sensor_data(simulation_extractor, results_data)

        if not self.free_space and "_temp_sar_df" in results_data:
            self._save_reports(
                results_data.pop("_temp_sar_df"),
                results_data.pop("_temp_tissue_groups"),
                results_data.pop("_temp_group_sar_stats"),
                results_data,
            )

        results_dir = os.path.join(
            self.config.base_dir,
            "results",
            self.study_type,
            self.phantom_name,
            f"{self.frequency_mhz}MHz",
            self.placement_name,
        )
        os.makedirs(results_dir, exist_ok=True)
        results_filepath = os.path.join(results_dir, "sar_results.json")

        final_results_data = {
            k: v for k, v in results_data.items() if not k.startswith("_temp")
        }

        with open(results_filepath, "w") as f:
            json.dump(final_results_data, f, indent=4)
        self._log(f"  - SAR results saved to: {results_filepath}", log_type="info")

    def _extract_input_power(self, simulation_extractor, results_data):
        """
        Extracts the input power from the simulation results.

        For far-field studies, it calculates a theoretical input power based on
        the plane wave source. For near-field, it extracts the power from the
        simulation's port sensor.

        Args:
            simulation_extractor: The results extractor from the simulation object.
            results_data (dict): The dictionary to store the extracted data.
        """
        self._log("  - Extracting input power...", log_type="progress")
        with self.study.subtask("extract_input_power"):
            try:
                if self.study_type == "far_field":
                    self._log(
                        "  - Far-field study: using theoretical model for input power.",
                        log_type="info",
                    )
                    import s4l_v1.model

                    try:
                        bbox_entity = next(
                            (
                                e
                                for e in s4l_v1.model.AllEntities()
                                if hasattr(e, "Name")
                                and e.Name == "far_field_simulation_bbox"
                            ),
                            None,
                        )
                        if not bbox_entity:
                            raise RuntimeError(
                                "Could not find 'far_field_simulation_bbox' entity in the project."
                            )
                        sim_bbox = s4l_v1.model.GetBoundingBox([bbox_entity])
                    except RuntimeError as e:
                        self._log(
                            f"  - WARNING: Could not calculate theoretical input power. {e}",
                            log_type="warning",
                        )
                        return
                    sim_min, sim_max = np.array(sim_bbox[0]), np.array(sim_bbox[1])
                    padding_bottom = np.array(
                        self.config.get_setting(
                            "gridding_parameters.padding.manual_bottom_padding_mm",
                            [0, 0, 0],
                        )
                    )
                    padding_top = np.array(
                        self.config.get_setting(
                            "gridding_parameters.padding.manual_top_padding_mm",
                            [0, 0, 0],
                        )
                    )
                    total_min, total_max = (
                        sim_min - padding_bottom,
                        sim_max + padding_top,
                    )

                    e_field_v_m, z0 = 1.0, 377.0
                    power_density_w_m2 = (e_field_v_m**2) / (2 * z0)

                    direction = self.placement_name.split("_")[1]
                    dims = total_max - total_min
                    if direction == "x":
                        area_m2 = (dims[1] * dims[2]) / 1e6
                    elif direction == "y":
                        area_m2 = (dims[0] * dims[2]) / 1e6
                    else:
                        area_m2 = (dims[0] * dims[1]) / 1e6

                    total_input_power = power_density_w_m2 * area_m2
                    results_data.update(
                        {
                            "input_power_W": total_input_power,
                            "input_power_frequency_MHz": float(self.frequency_mhz),
                        }
                    )
                    self._log(
                        f"  - Calculated theoretical input power: {total_input_power:.4e} W",
                        log_type="highlight",
                    )
                    return

                input_power_extractor = simulation_extractor["Input Power"]
                self.document.AllAlgorithms.Add(input_power_extractor)
                input_power_extractor.Update()

                if hasattr(input_power_extractor, "GetPower"):
                    power_w, _ = input_power_extractor.GetPower(0)
                    results_data.update(
                        {
                            "input_power_W": float(power_w),
                            "input_power_frequency_MHz": float(self.frequency_mhz),
                        }
                    )
                else:
                    self._log(
                        "  - GetPower() not available, falling back to manual extraction.",
                        log_type="warning",
                    )
                    input_power_output = input_power_extractor.Outputs[
                        "EM Input Power(f)"
                    ]
                    input_power_output.Update()

                    if hasattr(input_power_output, "GetHarmonicData"):
                        power_complex = input_power_output.GetHarmonicData(0)
                        results_data.update(
                            {
                                "input_power_W": float(abs(power_complex)),
                                "input_power_frequency_MHz": float(self.frequency_mhz),
                            }
                        )
                    else:
                        power_data = input_power_output.Data.GetComponent(0)
                        if power_data is not None and power_data.size > 0:
                            if power_data.size == 1:
                                input_power_w, freq_mhz = (
                                    power_data.item(),
                                    self.frequency_mhz,
                                )
                            else:
                                center_freq_hz = self.frequency_mhz * 1e6
                                axis = input_power_output.Data.Axis
                                target_index = np.argmin(np.abs(axis - center_freq_hz))
                                input_power_w, freq_mhz = (
                                    power_data[target_index],
                                    axis[target_index] / 1e6,
                                )
                            results_data.update(
                                {
                                    "input_power_W": float(input_power_w),
                                    "input_power_frequency_MHz": float(freq_mhz),
                                }
                            )
                        else:
                            self._log(
                                "  - WARNING: Could not extract input power values.",
                                log_type="warning",
                            )
            except Exception as e:
                self._log(
                    f"  - ERROR: An exception occurred during input power extraction: {e}",
                    level="progress",
                    log_type="error",
                )
                traceback.print_exc()

    def _extract_sar_statistics(self, simulation_extractor, results_data):
        """
        Extracts detailed SAR statistics for all tissues in the simulation.

        This involves running the `SarStatisticsEvaluator` and processing its
        output into a pandas DataFrame.

        Args:
            simulation_extractor: The results extractor from the simulation object.
            results_data (dict): The dictionary to store the extracted data.
        """
        self._log(
            "  - Extracting SAR statistics for all tissues...", log_type="progress"
        )
        with self.study.subtask("extract_sar_statistics"):
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
                    results_data[f"{group}_weighted_avg_sar"] = data["weighted_avg_sar"]
                    results_data[f"{group}_peak_sar"] = data["peak_sar"]

                all_regions_row = df[df["Tissue"] == "All Regions"]
                if not all_regions_row.empty:
                    mass_averaged_sar = all_regions_row["Mass-Averaged SAR"].iloc[0]
                    if self.study_type == "near_field":
                        sar_key = (
                            "head_SAR"
                            if self.placement_name.lower()
                            in ["front_of_eyes", "by_cheek"]
                            else "trunk_SAR"
                        )
                        results_data[sar_key] = float(mass_averaged_sar)
                    else:
                        results_data["whole_body_sar"] = float(mass_averaged_sar)

                    peak_sar_col_name = (
                        "Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)"
                    )
                    if peak_sar_col_name in all_regions_row.columns:
                        results_data["peak_sar_10g_W_kg"] = float(
                            all_regions_row[peak_sar_col_name].iloc[0]
                        )

                self._extract_peak_sar_details(em_sensor_extractor, results_data)
                results_data.update(
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
                traceback.print_exc()

    def _define_tissue_groups(self, available_tissues):
        """
        Defines tissue groups based on the material mapping file or falls back to keyword matching.

        Args:
            available_tissues (list): A list of tissue names available in the simulation.

        Returns:
            dict: A dictionary where keys are group names and values are lists of tissue names.
        """
        material_mapping = self.config.get_material_mapping(self.phantom_name)

        if "_tissue_groups" in material_mapping:
            self._log(
                f"  - Loading tissue groups for '{self.phantom_name}' from material_name_mapping.json",
                log_type="info",
            )
            phantom_groups = material_mapping["_tissue_groups"]
            tissue_groups = {}
            reverse_mapping = {
                v: k for k, v in material_mapping.items() if not k.startswith("_")
            }
            for group_name, tissue_list in phantom_groups.items():
                s4l_names_in_group = set(tissue_list)
                tissue_groups[group_name] = [
                    t
                    for t in available_tissues
                    if reverse_mapping.get(t) in s4l_names_in_group
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

    def _calculate_group_sar(self, df, tissue_groups):
        """
        Calculates the weighted average and peak SAR for defined tissue groups.

        Args:
            df (pd.DataFrame): The DataFrame with detailed SAR statistics.
            tissue_groups (dict): A dictionary defining the composition of tissue groups.

        Returns:
            dict: A dictionary with calculated SAR values for each group.
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

    def _save_reports(self, df, tissue_groups, group_sar_stats, results_data):
        """
        Saves detailed reports in Pickle and HTML formats.

        Args:
            df (pd.DataFrame): DataFrame with detailed SAR statistics.
            tissue_groups (dict): Dictionary defining tissue groups.
            group_sar_stats (dict): Dictionary with grouped SAR statistics.
            results_data (dict): Dictionary with summary results.
        """
        results_dir = os.path.join(
            self.config.base_dir,
            "results",
            self.study_type,
            self.phantom_name,
            f"{self.frequency_mhz}MHz",
            self.placement_name,
        )
        os.makedirs(results_dir, exist_ok=True)

        pickle_data = {
            "detailed_sar_stats": df,
            "tissue_group_composition": tissue_groups,
            "grouped_sar_stats": group_sar_stats,
            "summary_results": results_data,
            "peak_sar_details": results_data.get("peak_sar_details", {}),
            "point_sensor_data": results_data.get("point_sensor_data", {}),
        }
        pickle_filepath = os.path.join(results_dir, "sar_stats_all_tissues.pkl")
        with open(pickle_filepath, "wb") as f:
            pickle.dump(pickle_data, f)
        self._log(f"  - Pickle report saved to: {pickle_filepath}", log_type="info")

        html_content = df.to_html(index=False, border=1)
        html_content += "<h2>Tissue Group Composition</h2>"
        html_content += pd.DataFrame.from_dict(tissue_groups, orient="index").to_html()
        html_content += "<h2>Grouped SAR Statistics</h2>"
        html_content += pd.DataFrame.from_dict(
            group_sar_stats, orient="index"
        ).to_html()

        html_content += "<h2>Peak SAR Details</h2>"
        peak_sar_df = pd.DataFrame.from_dict(
            results_data.get("peak_sar_details", {}), orient="index", columns=["Value"]
        )
        peak_sar_df.index.name = "Parameter"
        html_content += peak_sar_df.to_html()

        html_filepath = os.path.join(results_dir, "sar_stats_all_tissues.html")
        with open(html_filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        self._log(f"  - HTML report saved to: {html_filepath}", log_type="info")

    def _extract_peak_sar_details(self, em_sensor_extractor, results_data):
        """
        Extracts detailed information about the peak spatial-average SAR (psSAR),
        including its location.

        Args:
            em_sensor_extractor: The 'Overall Field' results extractor.
            results_data (dict): The dictionary to store the extracted data.
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
                results_data["peak_sar_details"] = {
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
            traceback.print_exc()

    def _extract_power_balance(self, simulation_extractor, results_data):
        """
        Extracts the power balance from the simulation to verify energy conservation.

        Args:
            simulation_extractor: The results extractor from the simulation object.
            results_data (dict): The dictionary to store the extracted data.
        """
        self._log("  - Extracting power balance...", log_type="progress")
        try:
            em_sensor_extractor = simulation_extractor["Overall Field"]
            power_balance_extractor = em_sensor_extractor.Outputs["Power Balance"]
            power_balance_extractor.Update()

            power_balance_data = {
                key: power_balance_extractor.Data.DataSimpleDataCollection.FieldValue(
                    key, 0
                )
                for key in power_balance_extractor.Data.DataSimpleDataCollection.Keys()
                if key != "Balance"
            }

            if self.study_type == "far_field" and "input_power_W" in results_data:
                power_balance_data["Pin"] = results_data["input_power_W"]
                self._log(
                    f"    - Overwriting Pin with theoretical value: {power_balance_data['Pin']:.4e} W",
                    log_type="info",
                )

            pin = power_balance_data.get("Pin", 0.0)
            p_out = power_balance_data.get("DielLoss", 0.0) + power_balance_data.get(
                "RadPower", 0.0
            )
            balance = 100 * (p_out / pin) if pin > 1e-9 else float("nan")

            power_balance_data["Balance"] = balance
            self._log(f"    - Final Balance: {balance:.2f}%", log_type="highlight")
            results_data["power_balance"] = power_balance_data

        except Exception as e:
            self._log(
                f"  - WARNING: Could not extract power balance: {e}", log_type="warning"
            )
            traceback.print_exc()

    def _extract_point_sensor_data(self, simulation_extractor, results_data):
        """
        Extracts time-domain E-field data from point sensors, plots the
        magnitude, and saves the raw data.

        Args:
            simulation_extractor: The results extractor from the simulation object.
            results_data (dict): The dictionary to store the extracted data.
        """
        self._log("  - Extracting point sensor data...", log_type="progress")
        with self.study.subtask("extract_point_sensor_data"):
            try:
                num_sensors = self.config.get_setting(
                    "simulation_parameters.number_of_point_sensors", 0
                )
                if num_sensors == 0:
                    return

                plt.ioff()
                plt.style.use("science")
                plt.rcParams.update({"text.usetex": False})
                fig, ax = plt.subplots()
                ax.grid(True, which="major", axis="y", linestyle="--")

                point_source_order = self.config.get_setting(
                    "simulation_parameters.point_source_order", []
                )
                point_sensor_results = {}

                for i in range(num_sensors):
                    if i >= len(point_source_order):
                        self._log(
                            f"    - WARNING: Not enough entries in 'point_source_order' for sensor {i+1}. Skipping.",
                            log_type="warning",
                        )
                        continue

                    corner_name = point_source_order[i]
                    full_sensor_name = f"Point Sensor Entity {i+1} ({corner_name})"

                    try:
                        em_sensor_extractor = simulation_extractor[full_sensor_name]
                        if not em_sensor_extractor:
                            self._log(
                                f"    - WARNING: Could not find sensor extractor for '{full_sensor_name}'",
                                log_type="warning",
                            )
                            continue
                    except Exception as e:
                        self._log(
                            f"    - WARNING: Could not retrieve sensor '{full_sensor_name}'. Error: {e}",
                            log_type="warning",
                        )
                        continue

                    self.document.AllAlgorithms.Add(em_sensor_extractor)

                    if "EM E(t)" not in em_sensor_extractor.Outputs:
                        self._log(
                            f"    - WARNING: 'EM E(t)' output not found for sensor '{full_sensor_name}'",
                            log_type="warning",
                        )
                        self.document.AllAlgorithms.Remove(em_sensor_extractor)
                        continue

                    em_output = em_sensor_extractor.Outputs["EM E(t)"]
                    em_output.Update()

                    time_axis = em_output.Data.Axis
                    ex, ey, ez = (em_output.Data.GetComponent(i) for i in range(3))
                    label = corner_name.replace("_", " ").title()

                    if time_axis is not None and time_axis.size > 0:
                        e_mag = np.sqrt(ex**2 + ey**2 + ez**2)
                        ax.plot(time_axis, e_mag, label=label)
                        point_sensor_results[label] = {
                            "time_s": time_axis.tolist(),
                            "Ex_V_m": ex.tolist(),
                            "Ey_V_m": ey.tolist(),
                            "Ez_V_m": ez.tolist(),
                            "E_mag_V_m": e_mag.tolist(),
                        }
                    else:
                        self._log(
                            f"    - WARNING: No data found for sensor '{full_sensor_name}'",
                            log_type="warning",
                        )

                    self.document.AllAlgorithms.Remove(em_sensor_extractor)

                if point_sensor_results:
                    results_data["point_sensor_data"] = point_sensor_results

                ax.set(
                    xlabel="Time (s)",
                    ylabel="|E-Field| (V/m)",
                    title=f"Point Sensor E-Field Magnitude vs. Time ({self.frequency_mhz} MHz)",
                )
                ax.legend()

                results_dir = os.path.join(
                    self.config.base_dir,
                    "results",
                    self.study_type,
                    self.phantom_name,
                    f"{self.frequency_mhz}MHz",
                    self.placement_name,
                )
                plot_filepath = os.path.join(results_dir, "point_sensor_data.png")
                plt.savefig(plot_filepath, dpi=300)
                plt.close(fig)
                self._log(
                    f"  - Point sensor plot saved to: {plot_filepath}", log_type="info"
                )

            except Exception as e:
                self._log(
                    f"  - ERROR: An exception occurred during point sensor data extraction: {e}",
                    level="progress",
                    log_type="error",
                )
                traceback.print_exc()
