import os
import re
import json
import pickle
import logging
import traceback
import pandas as pd
import numpy as np

class ResultsExtractor:
    """
    Handles all post-processing and data extraction tasks.
    """
    def __init__(self, config, simulation, phantom_name, frequency_mhz, placement_name, study_type, verbose_logger, progress_logger, free_space=False, gui=None, study=None):
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
        
        import s4l_v1.document
        import s4l_v1.analysis
        import s4l_v1.units as units
        self.document = s4l_v1.document
        self.analysis = s4l_v1.analysis
        self.units = units

    def _log(self, message, level='verbose'):
        if level == 'progress':
            self.progress_logger.info(message)
            if self.gui:
                self.gui.log(message, level='progress')
        else:
            self.verbose_logger.info(message)
            if self.gui and level != 'progress':
                self.gui.log(message, level='verbose')

    def extract(self):
        """
        Extracts and saves the simulation results.
        """
        self._log("Extracting results...")
        if not self.simulation:
            self._log("  - ERROR: Simulation object not found. Skipping result extraction.")
            return

        results_data = {}
        simulation_extractor = self.simulation.Results()

        # Extract Input Power
        if self.gui:
            self.gui.update_stage_progress("Extracting Power", 50, 100)
        self._extract_input_power(simulation_extractor, results_data)

        # Extract SAR Statistics
        if not self.free_space:
            if self.gui:
                self.gui.update_stage_progress("Extracting SAR", 100, 100)
            self._extract_sar_statistics(simulation_extractor, results_data)
        else:
            self._log("  - Skipping SAR statistics for free-space simulation.")

        # Save final results
        if self.study_type == 'near_field':
            results_dir = os.path.join(self.config.base_dir, 'results', 'near_field', self.phantom_name, f"{self.frequency_mhz}MHz", self.placement_name)
        else:
            results_dir = os.path.join(self.config.base_dir, 'results', 'far_field', self.phantom_name, f"{self.frequency_mhz}MHz", self.placement_name)
        os.makedirs(results_dir, exist_ok=True)
        results_filepath = os.path.join(results_dir, 'sar_results.json')
        with open(results_filepath, 'w') as f:
            json.dump(results_data, f, indent=4)
        self._log(f"  - SAR results saved to: {results_filepath}")

    def _extract_input_power(self, simulation_extractor, results_data):
        """Extracts the input power from the simulation."""
        self._log("  - Extracting input power...")
        self.study.profiler.start_subtask("extract_input_power")
        try:
            input_power_extractor = simulation_extractor["Input Power"]
            self.document.AllAlgorithms.Add(input_power_extractor)
            input_power_extractor.Update()

            if hasattr(input_power_extractor, 'GetPower'):
                self._log("  - Using GetPower() to extract input power.")
                power_w, _ = input_power_extractor.GetPower(0)
                results_data['input_power_W'] = float(power_w)
                results_data['input_power_frequency_MHz'] = float(self.frequency_mhz)
            else:
                self._log("  - GetPower() not available, falling back to manual extraction.")
                input_power_output = input_power_extractor.Outputs["EM Input Power(f)"]
                input_power_output.Update()

                if hasattr(input_power_output, 'GetHarmonicData'):
                    self._log("  - Harmonic data detected. Extracting single power value.")
                    power_complex = input_power_output.GetHarmonicData(0)
                    input_power_w = abs(power_complex)
                    frequency_at_value_mhz = self.frequency_mhz
                    results_data['input_power_W'] = float(input_power_w)
                    results_data['input_power_frequency_MHz'] = float(frequency_at_value_mhz)
                else:
                    power_data = input_power_output.Data.GetComponent(0)
                    if power_data is not None and hasattr(power_data, 'size') and power_data.size > 0:
                        if power_data.size == 1:
                            input_power_w = power_data.item()
                            frequency_at_value_mhz = self.frequency_mhz
                        else:
                            center_frequency_hz = self.frequency_mhz * 1e6
                            axis = input_power_output.Data.Axis
                            min_diff = float('inf')
                            target_index = -1
                            for i, freq_hz in enumerate(axis):
                                diff = abs(freq_hz - center_frequency_hz)
                                if diff < min_diff:
                                    min_diff = diff
                                    target_index = i
                            if target_index != -1:
                                input_power_w = power_data[target_index]
                                frequency_at_value_mhz = axis[target_index] / 1e6
                            else:
                                input_power_w = -1
                                frequency_at_value_mhz = -1
                        results_data['input_power_W'] = float(input_power_w)
                        results_data['input_power_frequency_MHz'] = float(frequency_at_value_mhz)
                    else:
                        self._log("  - WARNING: Could not extract input power values.")
        except Exception as e:
            self._log(f"  - ERROR: An exception occurred during input power extraction: {e}", level='progress')
            traceback.print_exc()
        finally:
            elapsed = self.study.profiler.end_subtask()
            self._log(f"  - Input power extraction took {elapsed:.2f}s", level='progress')

    def _extract_sar_statistics(self, simulation_extractor, results_data):
        """Extracts SAR statistics for all tissues."""
        self._log("  - Extracting SAR statistics for all tissues...")
        self.study.profiler.start_subtask("extract_sar_statistics")
        try:
            em_sensor_extractor = simulation_extractor["Overall Field"]
            em_sensor_extractor.FrequencySettings.ExtractedFrequency = u"All"
            self.document.AllAlgorithms.Add(em_sensor_extractor)
            em_sensor_extractor.Update()

            inputs = [em_sensor_extractor.Outputs["EM E(x,y,z,f0)"]]
            sar_stats_evaluator = self.analysis.em_evaluators.SarStatisticsEvaluator(inputs=inputs)
            sar_stats_evaluator.PeakSpatialAverageSAR = True
            sar_stats_evaluator.PeakSAR.TargetMass = 10.0, self.units.Unit("g")
            sar_stats_evaluator.UpdateAttributes()
            self.document.AllAlgorithms.Add(sar_stats_evaluator)
            sar_stats_evaluator.Update()
 
            stats_output = sar_stats_evaluator.Outputs
            
            results = None
            if len(stats_output) > 0:
                # The results are in the first output port of the evaluator
                results_wrapper = stats_output.item_at(0)
                if hasattr(results_wrapper, 'Data'):
                    results = results_wrapper.Data
                else:
                    self._log("  - ERROR: AlgorithmOutput object does not have a .Data attribute.")
            else:
                self._log("  - ERROR: No output ports found in the SAR Statistics Evaluator.")

            # IMPORTANT: Clean up the algorithm to avoid issues when processing multiple simulations in the same project
            self.document.AllAlgorithms.Remove(sar_stats_evaluator)

            if not (results and hasattr(results, 'NumberOfRows') and results.NumberOfRows() > 0 and results.NumberOfColumns() > 0):
                self._log("  - WARNING: No SAR statistics data found.")
                return

            columns = ["Tissue"] + [cap for cap in results.ColumnMainCaptions]
            data = []
            for i in range(results.NumberOfRows()):
                row_caption = results.RowCaptions[i]
                clean_caption = re.sub(r'\s*\(.*\)\s*$', '', row_caption).strip().replace(')', '')
                row_data = [clean_caption] + [results.Value(i, j) for j in range(results.NumberOfColumns())]
                data.append(row_data)

            df = pd.DataFrame(data, columns=columns)
            numeric_cols = [col for col in df.columns if col != 'Tissue']
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

            tissue_groups = self._define_tissue_groups(df['Tissue'].tolist())
            group_sar_stats = self._calculate_group_sar(df, tissue_groups)
            
            for group, data in group_sar_stats.items():
                results_data[f"{group}_weighted_avg_sar"] = data['weighted_avg_sar']
                results_data[f"{group}_peak_sar"] = data['peak_sar']

            all_regions_row = df[df['Tissue'] == 'All Regions']
            if not all_regions_row.empty:
                mass_averaged_sar = all_regions_row['Mass-Averaged SAR'].iloc[0]
                if self.study_type == 'near_field':
                    sar_key = 'head_SAR' if self.placement_name.lower() in ['front_of_eyes', 'by_cheek'] else 'trunk_SAR'
                    results_data[sar_key] = float(mass_averaged_sar)
                else:
                    results_data['whole_body_sar'] = float(mass_averaged_sar)

                peak_sar_col_name = 'Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)'
                if peak_sar_col_name in all_regions_row.columns:
                    results_data['peak_sar_10g_W_kg'] = float(all_regions_row[peak_sar_col_name].iloc[0])

            self._save_reports(df, tissue_groups, group_sar_stats, results_data)

        except Exception as e:
            self._log(f"  - ERROR: An unexpected error during all-tissue SAR statistics extraction: {e}", level='progress')
            traceback.print_exc()
        finally:
            elapsed = self.study.profiler.end_subtask()
            self._log(f"  - SAR statistics extraction took {elapsed:.2f}s", level='progress')

    def _define_tissue_groups(self, available_tissues):
        """Defines tissue groups based on keywords."""
        groups = {
            "eyes_group": ["eye", "cornea", "sclera", "lens", "vitreous"],
            "skin_group": ["skin"],
            "brain_group": ["brain", "commissura", "midbrain", "pineal", "hypophysis", "medulla", "pons", "thalamus", "hippocampus", "cerebellum"]
        }
        tissue_groups = {group: [t for t in available_tissues if any(k in t.lower() for k in keywords)] for group, keywords in groups.items()}
        return tissue_groups

    def _calculate_group_sar(self, df, tissue_groups):
        """Calculates weighted average and peak SAR for tissue groups."""
        group_sar_data = {}
        peak_sar_col = 'Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)'
        for group_name, tissues in tissue_groups.items():
            group_df = df[df['Tissue'].isin(tissues)]
            if not group_df.empty:
                total_mass = group_df['Total Mass'].sum()
                weighted_avg_sar = (group_df['Total Mass'] * group_df['Mass-Averaged SAR']).sum() / total_mass if total_mass > 0 else 0
                peak_sar = group_df[peak_sar_col].max() if peak_sar_col in group_df.columns else -1.0
                group_sar_data[group_name] = {'weighted_avg_sar': weighted_avg_sar, 'peak_sar': peak_sar}
        return group_sar_data

    def _save_reports(self, df, tissue_groups, group_sar_stats, summary_results):
        """Saves detailed reports in Pickle and HTML format."""
        if self.study_type == 'near_field':
            results_dir = os.path.join(self.config.base_dir, 'results', 'near_field', self.phantom_name, f"{self.frequency_mhz}MHz", self.placement_name)
        else:
            results_dir = os.path.join(self.config.base_dir, 'results', 'far_field', self.phantom_name, f"{self.frequency_mhz}MHz", self.placement_name)
        os.makedirs(results_dir, exist_ok=True)
        
        pickle_data = {
            'detailed_sar_stats': df,
            'tissue_group_composition': tissue_groups,
            'grouped_sar_stats': group_sar_stats,
            'summary_results': summary_results
        }
        pickle_filepath = os.path.join(results_dir, 'sar_stats_all_tissues.pkl')
        with open(pickle_filepath, 'wb') as f:
            pickle.dump(pickle_data, f)
        self._log(f"  - Pickle report saved to: {pickle_filepath}")

        html_content = df.to_html(index=False, border=1)
        html_content += "<h2>Tissue Group Composition</h2>"
        html_content += pd.DataFrame.from_dict(tissue_groups, orient='index').to_html()
        html_content += "<h2>Grouped SAR Statistics</h2>"
        html_content += pd.DataFrame.from_dict(group_sar_stats, orient='index').to_html()
        
        html_filepath = os.path.join(results_dir, 'sar_stats_all_tissues.html')
        with open(html_filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        self._log(f"  - HTML report saved to: {html_filepath}")