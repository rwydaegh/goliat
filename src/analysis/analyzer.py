import os
import pickle
import json
import pandas as pd
import numpy as np
from ..config import Config
from .plotter import Plotter

class Analyzer:
    """
    Analyzes the results of the phantom simulation studies.
    """
    def __init__(self, config: Config):
        self.config = config
        self.base_dir = config.base_dir
        self.phantom_name = "Thelonius"
        self.results_base_dir = os.path.join(self.base_dir, "results", self.phantom_name)
        self.plotter = Plotter(os.path.join(self.base_dir, 'plots'))
        self.all_results = []
        self.all_organ_results = []
        self.tissue_group_definitions = {
            "eyes_group": ["eye", "cornea", "sclera", "lens", "vitreous"],
            "skin_group": ["skin"],
            "brain_group": ["brain", "commissura", "midbrain", "pineal", "hypophysis", "medulla", "pons", "thalamus", "hippocampus", "cerebellum"]
        }

    def run_analysis(self):
        """
        Main method to run the full analysis pipeline.
        """
        print(f"--- Starting Results Analysis for Phantom: {self.phantom_name} ---")
        self._load_and_process_results()

        if not self.all_results:
            print("--- No results found to analyze. ---")
            return

        results_df = pd.DataFrame(self.all_results)
        all_organ_results_df = pd.DataFrame(self.all_organ_results)

        results_df = self._convert_units_and_cache(results_df, all_organ_results_df)
        self._export_reports(results_df, all_organ_results_df)
        self._generate_plots(results_df, all_organ_results_df)
        
        print("--- Analysis Finished ---")

    def _load_and_process_results(self):
        frequencies = self.config.get_antenna_config().keys()
        placement_scenarios = self.config.get_setting("placement_scenarios", {})

        for freq in frequencies:
            frequency_mhz = int(freq)
            for scenario_name, scenario_def in placement_scenarios.items():
                positions = scenario_def.get("positions", {})
                orientations = scenario_def.get("orientations", {})
                for pos_name in positions.keys():
                    for orient_name in orientations.keys():
                        self._process_single_result(frequency_mhz, scenario_name, pos_name, orient_name)

    def _process_single_result(self, frequency_mhz, scenario_name, pos_name, orient_name):
        detailed_placement_name = f"{scenario_name}_{pos_name}_{orient_name}"
        results_dir = os.path.join(self.results_base_dir, f"{frequency_mhz}MHz", detailed_placement_name)
        pickle_path = os.path.join(results_dir, "sar_stats_all_tissues.pkl")
        json_path = os.path.join(results_dir, "sar_results.json")

        if not (os.path.exists(pickle_path) and os.path.exists(json_path)):
            return

        print(f"  - Processing: {frequency_mhz}MHz, {detailed_placement_name}")
        try:
            with open(pickle_path, 'rb') as f:
                pickle_data = pickle.load(f)
            with open(json_path, 'r') as f:
                sar_results = json.load(f)

            simulated_power_w = sar_results.get('input_power_W', float('nan'))
            normalization_factor = self._get_normalization_factor(frequency_mhz, simulated_power_w)
            result_entry, organ_entries = self._extract_data(
                pickle_data, frequency_mhz, detailed_placement_name, scenario_name, 
                simulated_power_w, normalization_factor
            )
            result_entry = self._apply_bug_fixes(result_entry)
            self.all_results.append(result_entry)
            self.all_organ_results.extend(organ_entries)
        except Exception as e:
            print(f"    - ERROR: Could not process data for {detailed_placement_name} at {frequency_mhz}MHz: {e}")

    def _get_normalization_factor(self, frequency_mhz, simulated_power_w):
        antenna_configs = self.config.get_antenna_config()
        freq_config = antenna_configs.get(str(frequency_mhz), {})
        target_power_mw = freq_config.get('target_power_mW')
        if target_power_mw is not None and pd.notna(simulated_power_w) and simulated_power_w > 0:
            target_power_w = target_power_mw / 1000.0
            return target_power_w / simulated_power_w
        return 1.0

    def _extract_data(self, pickle_data, frequency_mhz, placement_name, scenario_name, sim_power, norm_factor):
        summary_results = pickle_data.get('summary_results', {})
        grouped_stats = pickle_data.get('grouped_sar_stats', {})
        detailed_df = pickle_data.get('detailed_sar_stats')
        result_entry = {
            'frequency_mhz': frequency_mhz, 'placement': placement_name, 'scenario': scenario_name,
            'input_power_w': sim_power,
            'SAR_head': summary_results.get('head_SAR', np.nan) * norm_factor,
            'SAR_trunk': summary_results.get('trunk_SAR', np.nan) * norm_factor,
        }
        for group_name, stats in grouped_stats.items():
            key = f"psSAR10g_{group_name.replace('_group', '')}"
            result_entry[key] = stats.get('peak_sar', np.nan) * norm_factor
        organ_entries = []
        if detailed_df is not None:
            peak_sar_col = 'Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)'
            for _, row in detailed_df.iterrows():
                organ_entries.append({
                    'frequency_mhz': frequency_mhz, 'placement': placement_name, 'tissue': row['Tissue'],
                    'mass_avg_sar_mw_kg': row['Mass-Averaged SAR'] * norm_factor * 1000,
                    'peak_sar_10g_mw_kg': row.get(peak_sar_col, np.nan) * norm_factor * 1000,
                    'min_local_sar_mw_kg': row.get('Min. local SAR', np.nan) * norm_factor * 1000,
                    'max_local_sar_mw_kg': row.get('Max. local SAR', np.nan) * norm_factor * 1000,
                })
        return result_entry, organ_entries

    def _apply_bug_fixes(self, result_entry):
        placement = result_entry['placement'].lower()
        if placement.startswith('front_of_eyes') or placement.startswith('by_cheek'):
            if pd.isna(result_entry.get('SAR_head')) and pd.notna(result_entry.get('SAR_trunk')):
                result_entry['SAR_head'] = result_entry['SAR_trunk']
                result_entry['SAR_trunk'] = np.nan
        return result_entry

    def _convert_units_and_cache(self, results_df, organ_results_df):
        """Converts SAR units to mW/kg and caches both summary and organ-level results."""
        sar_columns = [col for col in results_df.columns if 'SAR' in col]
        results_df[sar_columns] = results_df[sar_columns] * 1000

        output_pickle_path = os.path.join(self.results_base_dir, "aggregated_results.pkl")
        os.makedirs(os.path.dirname(output_pickle_path), exist_ok=True)

        # Cache both dataframes in a single pickle file for comprehensive reuse
        cached_data = {
            'summary_results': results_df,
            'organ_results': organ_results_df
        }
        with open(output_pickle_path, 'wb') as f:
            pickle.dump(cached_data, f)

        print(f"\n--- Aggregated summary and organ results (in mW/kg) cached to: {output_pickle_path} ---")
        return results_df

    def _export_reports(self, results_df, all_organ_results_df):
        results_for_export = results_df.drop(columns=['input_power_w', 'scenario'])
        print("\n--- Full Normalized Results per Simulation (in mW/kg) ---")
        with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000):
            print(results_for_export.sort_values(by=['frequency_mhz', 'placement']))
        summary_stats = self._calculate_summary_stats(results_df)
        print("\n--- Summary Statistics (Mean) of Normalized SAR per Scenario and Frequency (in mW/kg) ---")
        with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000):
            print(summary_stats)
        detailed_csv_path = os.path.join(self.results_base_dir, 'normalized_results_detailed.csv')
        summary_csv_path = os.path.join(self.results_base_dir, 'normalized_results_summary.csv')
        organ_csv_path = os.path.join(self.results_base_dir, 'normalized_results_organs.csv')
        results_for_export.to_csv(detailed_csv_path, index=False)
        summary_stats.to_csv(summary_csv_path)
        all_organ_results_df.to_csv(organ_csv_path, index=False)
        print(f"\n--- Detailed results saved to: {detailed_csv_path} ---")
        print(f"--- Summary statistics saved to: {summary_csv_path} ---")
        print(f"--- Organ-level results saved to: {organ_csv_path} ---")

    def _calculate_summary_stats(self, results_df):
        placement_scenarios = self.config.get_setting("placement_scenarios", {})
        placements_per_scenario = {}
        print("\n--- Calculating Total Possible Placements per Scenario ---")
        for name, definition in placement_scenarios.items():
            total = len(definition.get("positions", {})) * len(definition.get("orientations", {}))
            placements_per_scenario[name] = total
            print(f"- Scenario '{name}': {total} placements")
        summary_stats = results_df.groupby(['scenario', 'frequency_mhz']).mean(numeric_only=True)
        completion_counts = results_df.groupby(['scenario', 'frequency_mhz']).size()
        summary_stats['progress'] = summary_stats.index.map(
            lambda idx: f"{completion_counts.get(idx, 0)}/{placements_per_scenario.get(idx[0], 0)}"
        )
        return summary_stats

    def _generate_plots(self, results_df, all_organ_results_df):
        """Generates all plots using the Plotter class."""
        scenarios_with_results = results_df['scenario'].unique()
        summary_stats = self._calculate_summary_stats(results_df)

        for scenario_name in scenarios_with_results:
            print(f"\n--- Generating plots for scenario: {scenario_name} ---")
            scenario_results_df = results_df[results_df['scenario'] == scenario_name]
            scenario_summary_stats = summary_stats.loc[scenario_name]
            avg_results = scenario_summary_stats.drop(columns=['progress'])
            progress_info = scenario_summary_stats['progress']
            self.plotter.plot_average_sar_bar(scenario_name, avg_results, progress_info)
            self.plotter.plot_pssar_line(scenario_name, avg_results)
            self.plotter.plot_sar_distribution_boxplots(scenario_name, scenario_results_df)

        # --- Prepare data for heatmaps ---
        available_tissues = all_organ_results_df['tissue'].unique()
        tissue_groups = {
            group: [t for t in available_tissues if any(k in t.lower() for k in keywords)]
            for group, keywords in self.tissue_group_definitions.items()
        }

        # 1. SAR Data (Min, Avg, Max)
        organ_sar_df = all_organ_results_df.groupby(['tissue', 'frequency_mhz']).agg(
            min_sar=('min_local_sar_mw_kg', 'mean'),
            avg_sar=('mass_avg_sar_mw_kg', 'mean'),
            max_sar=('max_local_sar_mw_kg', 'mean')
        ).reset_index()

        # 2. psSAR10g Data
        organ_pssar_df = all_organ_results_df.groupby(['tissue', 'frequency_mhz'])['peak_sar_10g_mw_kg'].mean().reset_index()
        organ_pssar_df = organ_pssar_df.rename(columns={'peak_sar_10g_mw_kg': 'pssar_10g'})

        # 3. Group Summaries
        group_summary_data = []
        for group_name, tissues in tissue_groups.items():
            if not tissues: continue
            group_df = all_organ_results_df[all_organ_results_df['tissue'].isin(tissues)]
            if not group_df.empty:
                summary = group_df.groupby('frequency_mhz').agg(
                    avg_sar=('mass_avg_sar_mw_kg', 'mean'),
                    pssar_10g=('peak_sar_10g_mw_kg', 'mean')
                ).reset_index()
                summary['group'] = group_name.replace('_group', '').capitalize()
                group_summary_data.append(summary)
        
        group_summary_df = pd.concat(group_summary_data, ignore_index=True) if group_summary_data else pd.DataFrame()
        
        group_sar_summary = group_summary_df[['group', 'frequency_mhz', 'avg_sar']]
        group_pssar_summary = group_summary_df[['group', 'frequency_mhz', 'pssar_10g']]

        # --- Call Plotter ---
        self.plotter.plot_sar_heatmap(organ_sar_df, group_sar_summary, tissue_groups)
        self.plotter.plot_pssar_heatmap(organ_pssar_df, group_pssar_summary, tissue_groups)