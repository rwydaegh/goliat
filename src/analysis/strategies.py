from abc import ABC, abstractmethod
import os
import pandas as pd

class BaseAnalysisStrategy(ABC):
    """
    Abstract base class for analysis strategies.
    """
    def __init__(self, config, phantom_name):
        self.config = config
        self.phantom_name = phantom_name
        self.base_dir = config.base_dir

    @abstractmethod
    def get_results_base_dir(self):
        pass

    @abstractmethod
    def get_plots_dir(self):
        pass

    @abstractmethod
    def load_and_process_results(self, analyzer):
        pass

    @abstractmethod
    def get_normalization_factor(self, frequency_mhz, simulated_power_w):
        pass

    @abstractmethod
    def extract_data(self, pickle_data, frequency_mhz, detailed_name, scenario_name, sim_power, norm_factor):
        pass

    @abstractmethod
    def apply_bug_fixes(self, result_entry):
        return result_entry

    @abstractmethod
    def calculate_summary_stats(self, results_df):
        pass

    @abstractmethod
    def generate_plots(self, analyzer, plotter, results_df, all_organ_results_df):
        pass


class NearFieldAnalysisStrategy(BaseAnalysisStrategy):
    """
    Analysis strategy for near-field simulations.
    """
    def get_results_base_dir(self):
        return os.path.join(self.base_dir, "results", "near_field", self.phantom_name)

    def get_plots_dir(self):
        return os.path.join(self.base_dir, 'plots', 'near_field', self.phantom_name)

    def load_and_process_results(self, analyzer):
        frequencies = self.config.get_antenna_config().keys()
        placement_scenarios = self.config.get_setting("placement_scenarios", {})

        for freq in frequencies:
            frequency_mhz = int(freq)
            for scenario_name, scenario_def in placement_scenarios.items():
                positions = scenario_def.get("positions", {})
                orientations = scenario_def.get("orientations", {})
                for pos_name in positions.keys():
                    for orient_name in orientations.keys():
                        analyzer._process_single_result(frequency_mhz, scenario_name, pos_name, orient_name)

    def get_normalization_factor(self, frequency_mhz, simulated_power_w):
        antenna_configs = self.config.get_antenna_config()
        freq_config = antenna_configs.get(str(frequency_mhz), {})
        target_power_mw = freq_config.get('target_power_mW')
        if target_power_mw is not None and pd.notna(simulated_power_w) and simulated_power_w > 0:
            target_power_w = target_power_mw / 1000.0
            return target_power_w / simulated_power_w
        return 1.0

    def extract_data(self, pickle_data, frequency_mhz, placement_name, scenario_name, sim_power, norm_factor):
        summary_results = pickle_data.get('summary_results', {})
        grouped_stats = pickle_data.get('grouped_sar_stats', {})
        detailed_df = pickle_data.get('detailed_sar_stats')
        result_entry = {
            'frequency_mhz': frequency_mhz, 'placement': placement_name, 'scenario': scenario_name,
            'input_power_w': sim_power,
            'SAR_head': summary_results.get('head_SAR', pd.NA) * norm_factor,
            'SAR_trunk': summary_results.get('trunk_SAR', pd.NA) * norm_factor,
        }
        for group_name, stats in grouped_stats.items():
            key = f"psSAR10g_{group_name.replace('_group', '')}"
            result_entry[key] = stats.get('peak_sar', pd.NA) * norm_factor
        
        organ_entries = []
        if detailed_df is not None:
            peak_sar_col = 'Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)'
            for _, row in detailed_df.iterrows():
                organ_entries.append({
                    'frequency_mhz': frequency_mhz, 'placement': placement_name, 'tissue': row['Tissue'],
                    'mass_avg_sar_mw_kg': row['Mass-Averaged SAR'] * norm_factor * 1000,
                    'peak_sar_10g_mw_kg': row.get(peak_sar_col, pd.NA) * norm_factor * 1000,
                    'min_local_sar_mw_kg': row.get('Min. local SAR', pd.NA) * norm_factor * 1000,
                    'max_local_sar_mw_kg': row.get('Max. local SAR', pd.NA) * norm_factor * 1000,
                })
        return result_entry, organ_entries

    def apply_bug_fixes(self, result_entry):
        placement = result_entry['placement'].lower()
        if placement.startswith('front_of_eyes') or placement.startswith('by_cheek'):
            if pd.isna(result_entry.get('SAR_head')) and pd.notna(result_entry.get('SAR_trunk')):
                result_entry['SAR_head'] = result_entry['SAR_trunk']
                result_entry['SAR_trunk'] = pd.NA
        return result_entry

    def calculate_summary_stats(self, results_df):
        placement_scenarios = self.config.get_setting("placement_scenarios", {})
        placements_per_scenario = {}
        logging.getLogger('progress').info("\n--- Calculating Total Possible Placements per Scenario ---", extra={'log_type': 'header'})
        for name, definition in placement_scenarios.items():
            total = len(definition.get("positions", {})) * len(definition.get("orientations", {}))
            placements_per_scenario[name] = total
            logging.getLogger('progress').info(f"- Scenario '{name}': {total} placements", extra={'log_type': 'info'})
        summary_stats = results_df.groupby(['scenario', 'frequency_mhz']).mean(numeric_only=True)
        completion_counts = results_df.groupby(['scenario', 'frequency_mhz']).size()
        summary_stats['progress'] = summary_stats.index.map(
            lambda idx: f"{completion_counts.get(idx, 0)}/{placements_per_scenario.get(idx[0], 0)}"
        )
        return summary_stats

    def generate_plots(self, analyzer, plotter, results_df, all_organ_results_df):
        scenarios_with_results = results_df['scenario'].unique()
        summary_stats = self.calculate_summary_stats(results_df)

        for scenario_name in scenarios_with_results:
            logging.getLogger('progress').info(f"\n--- Generating plots for scenario: {scenario_name} ---", extra={'log_type': 'header'})
            scenario_results_df = results_df[results_df['scenario'] == scenario_name]
            scenario_summary_stats = summary_stats.loc[scenario_name]
            avg_results = scenario_summary_stats.drop(columns=['progress'])
            progress_info = scenario_summary_stats['progress']
            plotter.plot_average_sar_bar(scenario_name, avg_results, progress_info)
            plotter.plot_pssar_line(scenario_name, avg_results)
            plotter.plot_sar_distribution_boxplots(scenario_name, scenario_results_df)


class FarFieldAnalysisStrategy(BaseAnalysisStrategy):
    """
    Analysis strategy for far-field simulations.
    """
    def get_results_base_dir(self):
        return os.path.join(self.base_dir, "results", "far_field", self.phantom_name)

    def get_plots_dir(self):
        return os.path.join(self.base_dir, 'plots', 'far_field', self.phantom_name)

    def load_and_process_results(self, analyzer):
        frequencies = self.config.get_setting('frequencies_mhz', [])
        far_field_params = self.config.get_setting('far_field_setup/environmental', {})
        incident_directions = far_field_params.get('incident_directions', [])
        polarizations = far_field_params.get('polarizations', [])

        for freq in frequencies:
            for direction_name in incident_directions:
                for polarization_name in polarizations:
                    placement_name = f"environmental_{direction_name}_{polarization_name}"
                    analyzer._process_single_result(freq, "environmental", placement_name, "")

    def get_normalization_factor(self, frequency_mhz, simulated_power_w):
        # For far-field, we normalize to a power density of 1 W/m^2
        # This should be handled in the simulation results, so factor is 1.0 here.
        return 1.0

    def extract_data(self, pickle_data, frequency_mhz, placement_name, scenario_name, sim_power, norm_factor):
        summary_results = pickle_data.get('summary_results', {})
        detailed_df = pickle_data.get('detailed_sar_stats')
        
        result_entry = {
            'frequency_mhz': frequency_mhz,
            'placement': placement_name,
            'scenario': scenario_name,
            'input_power_w': sim_power,
            'SAR_whole_body': summary_results.get('whole_body_sar', pd.NA),
            'peak_sar': summary_results.get('peak_sar_10g_W_kg', pd.NA),
        }

        organ_entries = []
        if detailed_df is not None:
            peak_sar_col = 'Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)'
            for _, row in detailed_df.iterrows():
                organ_entries.append({
                    'frequency_mhz': frequency_mhz,
                    'placement': placement_name,
                    'tissue': row['Tissue'],
                    'mass_avg_sar_mw_kg': row['Mass-Averaged SAR'] * 1000, # Already normalized in extractor
                    'peak_sar_10g_mw_kg': row.get(peak_sar_col, pd.NA) * 1000, # Already normalized
                })
        return result_entry, organ_entries

    def apply_bug_fixes(self, result_entry):
        return result_entry

    def calculate_summary_stats(self, results_df):
        return results_df.groupby('frequency_mhz').mean(numeric_only=True)

    def generate_plots(self, analyzer, plotter, results_df, all_organ_results_df):
        logging.getLogger('progress').info("\n--- Generating plots for far-field analysis ---", extra={'log_type': 'header'})
        summary_stats = self.calculate_summary_stats(results_df)
        plotter.plot_whole_body_sar_bar(summary_stats)
        plotter.plot_peak_sar_line(summary_stats)
        plotter.plot_far_field_distribution_boxplot(results_df, metric='SAR_whole_body')
        plotter.plot_far_field_distribution_boxplot(results_df, metric='peak_sar')

        # Prepare data for heatmaps
        organ_sar_df = all_organ_results_df.groupby(['tissue', 'frequency_mhz']).agg(
            avg_sar=('mass_avg_sar_mw_kg', 'mean')
        ).reset_index()

        organ_pssar_df = all_organ_results_df.groupby(['tissue', 'frequency_mhz'])['peak_sar_10g_mw_kg'].mean().reset_index()
        
        group_summary_data = []
        # tissue_groups defined in analyzer
        for group_name, tissues in analyzer.tissue_group_definitions.items():
            if not tissues: continue
            # Create a case-insensitive regex pattern to match any of the tissue keywords
            pattern = '|'.join(tissues)
            group_df = all_organ_results_df[all_organ_results_df['tissue'].str.contains(pattern, case=False, na=False)]
            
            if not group_df.empty:
                summary = group_df.groupby('frequency_mhz').agg(
                    avg_sar=('mass_avg_sar_mw_kg', 'mean'),
                    peak_sar_10g_mw_kg=('peak_sar_10g_mw_kg', 'mean')
                ).reset_index()
                summary['group'] = group_name.replace('_group', '').capitalize()
                group_summary_data.append(summary)
        
        group_summary_df = pd.concat(group_summary_data, ignore_index=True) if group_summary_data else pd.DataFrame()

        if not group_summary_df.empty:
            group_sar_summary = group_summary_df[['group', 'frequency_mhz', 'avg_sar']]
            group_pssar_summary = group_summary_df[['group', 'frequency_mhz', 'peak_sar_10g_mw_kg']]

            plotter.plot_peak_sar_heatmap(organ_sar_df, group_sar_summary, analyzer.tissue_group_definitions, value_col='avg_sar', title='Average SAR')
            plotter.plot_peak_sar_heatmap(organ_pssar_df, group_pssar_summary, analyzer.tissue_group_definitions, value_col='peak_sar_10g_mw_kg', title='Peak SAR 10g')
        else:
            logging.getLogger('progress').warning("  - WARNING: No data found for tissue groups, skipping heatmaps.", extra={'log_type': 'warning'})