import os
import re
import numpy as np
import json
import subprocess
import glob
import pandas as pd
import pickle

from .antenna import Antenna
from .utils import ensure_s4l_running, open_project

class NearFieldProject:
    """
    Manages the setup, execution, and result extraction for a single near-field simulation.
    """
    def __init__(self, project_name, phantom_name, frequency_mhz, placement_name, config, verbose=True, force_setup=False):
        self.project_name = project_name
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        self.placement_name = placement_name
        self.config = config
        self.verbose = verbose
        self.force_setup = force_setup
        self.antenna = Antenna(config, frequency_mhz)
        self.simulation = None
        
        # Ensure the results directory exists and set the project path
        results_dir = os.path.join(self.config.base_dir, 'results')
        os.makedirs(results_dir, exist_ok=True)
        self.project_path = os.path.join(results_dir, f"{self.project_name}.smash")
        
        # Defer S4L imports until after the application is running
        self._import_s4l_modules()

    def _log(self, message):
        if self.verbose:
            print(message)

    def _import_s4l_modules(self):
        """Imports Sim4Life modules and attaches them to the instance."""
        ensure_s4l_running()
        import s4l_v1
        from s4l_v1 import Unit
        import s4l_v1.document
        import s4l_v1.model
        import s4l_v1.simulation.emfdtd
        import s4l_v1.units
        import s4l_v1.materials.database
        import s4l_v1.data
        import s4l_v1.analysis
        import s4l_v1.analysis.em_evaluators
        import s4l_v1.analysis.extractors
        import XCoreModeling

        self.s4l_v1 = s4l_v1
        self.Unit = Unit
        self.document = s4l_v1.document
        self.model = s4l_v1.model
        self.emfdtd = s4l_v1.simulation.emfdtd
        self.units = s4l_v1.units
        self.database = s4l_v1.materials.database
        self.data = s4l_v1.data
        self.analysis = s4l_v1.analysis
        self.em_evaluators = s4l_v1.analysis.em_evaluators
        self.extractors = s4l_v1.analysis.extractors
        self.XCoreModeling = XCoreModeling

    def _run_isolve_manual(self):
        """Finds iSolve.exe, runs it, and reloads the results."""
        self._log("Attempting to run simulation with iSolve.exe...")
        
        s4l_path_candidates = glob.glob("C:/Program Files/Sim4Life_*.*/")
        if not s4l_path_candidates:
            raise FileNotFoundError("Could not find Sim4Life installation directory.")
        
        s4l_path_candidates.sort(reverse=True)
        isolve_path = os.path.join(s4l_path_candidates[0], "Solvers", "iSolve.exe")
        if not os.path.exists(isolve_path):
            raise FileNotFoundError(f"iSolve.exe not found at {isolve_path}")
            
        if not hasattr(self.simulation, 'GetInputFileName'):
            raise RuntimeError("Could not get input file name from simulation object.")

        relative_path = self.simulation.GetInputFileName()
        project_dir = os.path.dirname(self.project_path)
        input_file_path = os.path.join(project_dir, relative_path)
        self._log(f"Found input file path from API: {input_file_path}")

        if not os.path.exists(input_file_path):
             raise FileNotFoundError(f"Solver input file not found at: {input_file_path}")

        command = [isolve_path, "-i", input_file_path]
        self._log(f"Executing command: {' '.join(command)}")

        try:
            # Using subprocess.run without capturing output lets it stream directly.
            # check=True will still raise an error if the process fails.
            subprocess.run(command, check=True)
            
            self._log("iSolve.exe completed successfully.")
            
            # After the simulation, the project must be reloaded to see the results
            self._log("Re-opening project to load results...")
            self.document.Close()
            open_project(self.project_path)
            
            # Re-acquire the simulation object from the reloaded document
            sim_name = f"EM_FDTD_{self.phantom_name}_{self.antenna.get_model_name()}_{self.placement_name}"
            self.simulation = next((s for s in self.document.AllSimulations if s.Name == sim_name), None)
            if not self.simulation:
                raise RuntimeError(f"Could not find simulation '{sim_name}' after re-opening project.")
            self._log("Project reloaded and results are available.")

        except subprocess.CalledProcessError as e:
            error_message = (
                f"iSolve.exe failed with return code {e.returncode}.\n"
                "Check the console output above for more details."
            )
            self._log(error_message)
            raise RuntimeError(error_message)
        except Exception as e:
            self._log(f"An unexpected error occurred while running iSolve.exe: {e}")
            raise


    def setup(self):
        """
        Sets up the entire simulation environment in Sim4Life.
        If the project already exists, it will just be opened.
        """
        # Always start with a clean project to avoid file lock issues
        if os.path.exists(self.project_path):
            self._log(f"Deleting existing project file at {self.project_path}")
            os.remove(self.project_path)

        if not os.path.exists(self.project_path):
            self._log("Creating and saving a new empty project.")
            self.document.New()
            self.save()  # Save immediately to establish the path
            
            self._log("Running full setup...")
            self._ensure_phantom_is_loaded()
            self._setup_bounding_boxes()
            self._place_antenna()
            self._setup_simulation()
            self.simulation.UpdateGrid()
            self.simulation.CreateVoxels()
            self.save()
        else:
            self._log("Project already exists, opening it.")
            open_project(self.project_path)
            # Still need to get the simulation object from the document
            sim_name = f"EM_FDTD_{self.phantom_name}_{self.antenna.get_model_name()}_{self.placement_name}"
            self.simulation = next((s for s in self.document.AllSimulations if s.Name == sim_name), None)
            if not self.simulation:
                self._log(f"Warning: Could not find simulation '{sim_name}' in existing project.")
    
    def open_for_extraction(self):
        """
        Opens an existing project and ensures the simulation object is loaded,
        bypassing the full setup process.
        """
        self._log("Opening project for result extraction...")
        # The project is now reloaded in _run_isolve_manual, so we just need to open it here.
        open_project(self.project_path)
        sim_name = f"EM_FDTD_{self.phantom_name}_{self.antenna.get_model_name()}_{self.placement_name}"
        self.simulation = next((s for s in self.document.AllSimulations if s.Name == sim_name), None)
        if not self.simulation:
            raise RuntimeError(f"Could not find simulation '{sim_name}' in existing project.")

        # This method now simply opens the project. All result loading is handled
        # by the extract_results method to ensure it's self-contained.

    def run(self):
        """
        Runs the simulation, either via S4L API or iSolve executable.
        """
        self._log(f"Running simulation for {self.project_name}...")
        if not self.simulation:
            self._log(f"ERROR: Simulation object not found.")
            return

        if hasattr(self.simulation, "WriteInputFile"):
            self._log("Writing solver input file...")
            self.simulation.WriteInputFile()
            self.save() # Force a save to flush files before running the solver
        
        if self.config.get_manual_isolve():
            self._run_isolve_manual()
        else:
            self.simulation.RunSimulation(wait=True)
            self._log("Simulation finished.")

    def extract_results(self):
        """
        Extracts and saves the simulation results.
        """
        self._log("Extracting results...")
        if not self.simulation:
            self._log("  - ERROR: Simulation object not found. Skipping result extraction.")
            return
        
        results_data = {}

        simulation_extractor = self.simulation.Results()

        # The peak SAR will be extracted from the all-tissue statistics later
        results_data['peak_sar_10g_W_kg'] = -1.0


        # --- Extract Input Power ---
        self._log("  - Extracting input power...")
        try:
            # The extractor for Input Power is different from the main field extractor
            input_power_extractor = simulation_extractor["Input Power"]
            self.document.AllAlgorithms.Add(input_power_extractor)
            input_power_extractor.Update() # Ensure the extractor itself is updated
            
            # The output port is named "EM Input Power(f)"
            input_power_output = input_power_extractor.Outputs["EM Input Power(f)"]
            input_power_output.Update() # Ensure the output port data is up-to-date
            
            # The .Data property gives us a FloatXYData object
            input_power_field = input_power_output.Data
            
            # A FloatXYData object contains one or more SimpleSeries. For input power, there's one.
            # GetComponent(0) returns a numpy array of (frequency, power) tuples.
            power_data = input_power_field.GetComponent(0)

            if power_data is not None and power_data.size > 0:
                # For a single frequency simulation, GetComponent(0) returns a flat numpy array,
                # often just [power_value] or sometimes [frequency, power_value, ...].
                if power_data.size == 1:
                    input_power_w = power_data.item() # Get scalar from 0-dim array
                    frequency_at_value_mhz = self.frequency_mhz # Assume simulation frequency
                elif power_data.size >= 2:
                    # Assuming the format is [freq, power, freq, power, ...]
                    # We find the value closest to our simulation frequency.
                    center_frequency_hz = self.frequency_mhz * 1e6
                    # Reshape into (N, 2) array of [freq, power] pairs
                    reshaped_data = power_data.reshape(-1, 2)
                    frequencies = reshaped_data[:, 0]
                    powers = reshaped_data[:, 1]
                    
                    freq_diff = np.abs(frequencies - center_frequency_hz)
                    target_index = freq_diff.argmin()

                    input_power_w = powers[target_index]
                    frequency_at_value_mhz = frequencies[target_index] / 1e6
                else: # Should not happen if size > 0
                    input_power_w = -1.0
                    frequency_at_value_mhz = -1.0

                self._log(f"  - Input Power: {input_power_w:.4f} W at {frequency_at_value_mhz:.2f} MHz")
                results_data['input_power_W'] = float(input_power_w)
                results_data['input_power_frequency_MHz'] = float(frequency_at_value_mhz)
            else:
                self._log("  - WARNING: Could not extract input power values. Data series is empty.")
        except Exception as e:
            self._log(f"  - ERROR: An exception occurred during input power extraction: {e}")
            import traceback
            traceback.print_exc()


        # --- Extract SAR Statistics for All Tissues ---
        self._log("  - Extracting SAR statistics for all tissues...")
        try:
            # This follows the user's snippet: create an evaluator for all tissues
            em_sensor_extractor = simulation_extractor["Overall Field"]
            em_sensor_extractor.FrequencySettings.ExtractedFrequency = u"All"
            self.document.AllAlgorithms.Add(em_sensor_extractor)
            em_sensor_extractor.Update() # IMPORTANT: Update the extractor to load the data

            # Create SarStatisticsEvaluator and enable Peak Spatial Average SAR calculation
            inputs = [em_sensor_extractor.Outputs["EM E(x,y,z,f0)"]]
            sar_stats_evaluator = self.analysis.em_evaluators.SarStatisticsEvaluator(inputs=inputs)
            sar_stats_evaluator.PeakSpatialAverageSAR = True
            # NOTE: The AveragingMass property expects a float (in grams). The API does not use
            # the s4l_v1.units module for this property. Setting this to 10.0 calculates
            # the 10g average SAR, even though the output column name from the API
            # will still misleadingly say '1g'.
            sar_stats_evaluator.AveragingMass = 10.0
            self.document.AllAlgorithms.Add(sar_stats_evaluator)

            # Update the evaluator to generate the statistics
            sar_stats_evaluator.Update()

            # Define report path for HTML and pickle stats
            results_dir = os.path.join(self.config.base_dir, 'results', self.phantom_name, f"{self.frequency_mhz}MHz", self.placement_name)
            stats_filepath_html = os.path.join(results_dir, 'sar_stats_all_tissues.html')
            stats_filepath_pickle = os.path.join(results_dir, 'sar_stats_all_tissues.pkl')

            # Extract the data directly from the evaluator's output
            stats_output = sar_stats_evaluator.Outputs[0]
            results = stats_output.Data

            if not (results and results.NumberOfRows() > 0 and results.NumberOfColumns() > 0):
                self._log("  - WARNING: No SAR statistics data found.")
                return

            # --- Data Processing and Grouping ---
            columns = ["Tissue"] + [cap for cap in results.ColumnMainCaptions]
            
            # Prepare data for DataFrame
            data = []
            for i in range(results.NumberOfRows()):
                row_caption = results.RowCaptions[i]
                # Clean the tissue name by removing phantom specifics and trailing characters
                clean_caption = re.sub(r'\s*\(.*\)\s*$', '', row_caption).strip()
                clean_caption = clean_caption.replace(')', '') # Remove any stray closing parentheses
                row_data = [clean_caption] + [results.Value(i, j) for j in range(results.NumberOfColumns())]
                data.append(row_data)

            df = pd.DataFrame(data, columns=columns)

            # Define tissue groups based on the tissues found in the results
            tissue_groups = self._define_tissue_groups(df['Tissue'].tolist())

            # Convert all columns except 'Tissue' to numeric, coercing errors
            numeric_cols = [col for col in df.columns if col != 'Tissue']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df[numeric_cols] = df[numeric_cols].fillna(0) # Replace any NaNs with 0

            # Calculate grouped SAR statistics
            group_sar_stats = self._calculate_group_sar(df, tissue_groups)
            
            # Flatten the dictionary for JSON output
            for group, data in group_sar_stats.items():
                results_data[f"{group}_weighted_avg_sar"] = data['weighted_avg_sar']
                results_data[f"{group}_peak_sar"] = data['peak_sar']

            # Extract the peak 10g SAR from the 'All Regions' data
            all_regions_row = df[df['Tissue'] == 'All Regions']
            peak_sar_col_name = 'Peak Spatial-Average SAR[IEEE/IEC62704-1] (1g)'
            if not all_regions_row.empty and peak_sar_col_name in all_regions_row.columns:
                peak_sar_10g = all_regions_row[peak_sar_col_name].iloc[0]
                results_data['peak_sar_10g_W_kg'] = peak_sar_10g
                self._log(f"  - Peak SAR (10g) from stats: {peak_sar_10g:.4f} W/kg")
            else:
                self._log(f"  - WARNING: Could not find '{peak_sar_col_name}' in the results table.")

            # Extract total average SAR (from the last row) and make the key dynamic
            total_avg_sar_row = df.iloc[-1]
            total_sar_value = total_avg_sar_row['Mass-Averaged SAR']
            
            # Determine if it's a head or trunk simulation
            if self.placement_name.lower() in ['front_of_eyes', 'by_cheek']:
                sar_key = 'head_SAR'
            else:
                sar_key = 'trunk_SAR'
            
            results_data[sar_key] = total_sar_value
            
            # --- Save Reports ---
            # Create a dictionary to hold all data for pickling
            pickle_data = {
                'detailed_sar_stats': df,
                'tissue_group_composition': tissue_groups,
                'grouped_sar_stats': group_sar_stats,
                'summary_results': results_data
            }

            # Save as Pickle
            with open(stats_filepath_pickle, 'wb') as f:
                pickle.dump(pickle_data, f)
            self._log(f"  - Saved comprehensive results dictionary to: {stats_filepath_pickle}")

            # Save as HTML
            html_content = df.to_html(index=False, border=1)
            
            # Add group composition to HTML report
            html_content += "<h2>Tissue Group Composition</h2>"
            html_content += "<table border='1'><tr><th>Group</th><th>Tissues</th></tr>"
            for group_name, tissues in tissue_groups.items():
                tissues_str = ", ".join(tissues) if tissues else "None"
                html_content += f"<tr><td>{group_name}</td><td>{tissues_str}</td></tr>"
            html_content += "</table>"

            # Add grouped SAR to HTML report
            html_content += "<h2>Grouped SAR Statistics</h2>"
            html_content += "<table border='1'><tr><th>Group</th><th>Weighted Average SAR (W/kg)</th><th>Peak SAR (W/kg)</th></tr>"
            for group, data in group_sar_stats.items():
                html_content += f"<tr><td>{group}</td><td>{data['weighted_avg_sar']}</td><td>{data['peak_sar']}</td></tr>"
            html_content += "</table>"

            with open(stats_filepath_html, 'w', encoding='utf-8') as f:
                f.write(html_content)
            self._log(f"  - Saved detailed SAR stats for all tissues to: {stats_filepath_html}")

        except Exception as e:
            self._log(f"  - ERROR: An unexpected error occurred during all-tissue SAR statistics extraction: {e}")
            import traceback
            traceback.print_exc()


        # Save results to a file
        results_dir = os.path.join(self.config.base_dir, 'results', self.phantom_name, f"{self.frequency_mhz}MHz", self.placement_name)
        os.makedirs(results_dir, exist_ok=True)
        
        results_filepath = os.path.join(results_dir, 'sar_results.json')
        with open(results_filepath, 'w') as f:
            json.dump(results_data, f, indent=4)
        self._log(f"  - SAR results saved to: {results_filepath}")

    def save(self):
        """
        Saves the project to its file path.
        """
        self._log(f"Saving project to {self.project_path}...")
        self.document.SaveAs(self.project_path)
        self._log("Project saved.")

    def _define_tissue_groups(self, available_tissues):
        """Defines tissue groups based on keywords found in the available tissue list."""
        groups = {
            "eyes_group": ["eye", "cornea", "sclera", "lens", "vitreous"],
            "skin_group": ["skin"],
            "brain_group": ["brain", "commissura", "midbrain", "pineal", "hypophysis", "medulla", "pons", "thalamus", "hippocampus", "cerebellum"]
        }
        
        tissue_groups = {group: set() for group in groups}
        
        # Match keywords against the actual tissue names from the simulation results
        for tissue_name in available_tissues:
            for group_name, keywords in groups.items():
                if any(keyword in tissue_name.lower() for keyword in keywords):
                    tissue_groups[group_name].add(tissue_name)
        
        # Log the defined groups for clarity
        self._log("Defined Tissue Groups:")
        for group_name, tissues in tissue_groups.items():
            if tissues:
                self._log(f"  - {group_name}: {list(tissues)}")
            else:
                self._log(f"  - {group_name}: No tissues matched.")

        # Convert sets to lists for consistency
        return {group: list(tissues) for group, tissues in tissue_groups.items()}

    def _calculate_group_sar(self, df, tissue_groups):
        """
        Calculates the weighted average SAR and finds the peak SAR
        for defined tissue groups.
        """
        group_sar_data = {}
        peak_sar_col = 'Peak Spatial-Average SAR[IEEE/IEC62704-1] (1g)'

        for group_name, tissues in tissue_groups.items():
            group_df = df[df['Tissue'].isin(tissues)]
            
            weighted_avg_sar = -1.0
            peak_sar = -1.0

            if not group_df.empty:
                try:
                    # Weighted average calculation
                    required_cols = ['Total Mass', 'Mass-Averaged SAR']
                    if not all(col in group_df.columns for col in required_cols):
                        raise KeyError(f"Missing required columns for weighted average SAR")
                    
                    weighted_sar_sum = (group_df['Total Mass'] * group_df['Mass-Averaged SAR']).sum()
                    total_mass = group_df['Total Mass'].sum()
                    weighted_avg_sar = weighted_sar_sum / total_mass if total_mass > 0 else 0

                    # Peak SAR calculation
                    if peak_sar_col in group_df.columns:
                        peak_sar = group_df[peak_sar_col].max()
                    else:
                        self._log(f"  - WARNING: Peak SAR column '{peak_sar_col}' not found for group '{group_name}'.")

                except (KeyError, TypeError) as e:
                    self._log(f"  - WARNING: Could not calculate SAR for '{group_name}'. Error: {e}")
                    self._log(f"  - Available columns: {list(group_df.columns)}")
            else:
                self._log(f"  - INFO: No tissues found for group '{group_name}'.")

            group_sar_data[group_name] = {
                'weighted_avg_sar': weighted_avg_sar,
                'peak_sar': peak_sar
            }
        
        return group_sar_data

    def cleanup(self):
        """
        Closes the Sim4Life document.
        """
        self._log("Cleaning up and closing project...")
        self.document.Close()

    def _ensure_phantom_is_loaded(self):
        """
        Ensures the phantom model is loaded into the current document.
        """
        all_entities = self.model.AllEntities()
        if any(self.phantom_name.lower() in entity.Name.lower() for entity in all_entities if hasattr(entity, 'Name')):
            self._log("Phantom model is already present in the document.")
            return True

        sab_path = os.path.join(self.config.base_dir, 'data', 'phantoms', f"{self.phantom_name.capitalize()}.sab")
        if os.path.exists(sab_path):
            self._log(f"Phantom not found in document. Importing from '{sab_path}'...")
            self.XCoreModeling.Import(sab_path)
            self._log("Phantom imported successfully.")
            return True

        self._log(f"Local .sab file not found. Attempting to download '{self.phantom_name}'...")
        available_downloads = self.data.GetAvailableDownloads()
        phantom_to_download = next((item for item in available_downloads if self.phantom_name in item.Name), None)
        
        if not phantom_to_download:
            raise FileNotFoundError(f"Phantom '{self.phantom_name}' not found for download or in local files.")
        
        self._log(f"Found '{phantom_to_download.Name}'. Downloading...")
        self.data.DownloadModel(phantom_to_download, email="example@example.com", directory=os.path.join(self.config.base_dir, 'data', 'phantoms'))
        self._log("Phantom downloaded successfully. Please re-run the script to import the new .sab file.")
        return False

    def _setup_bounding_boxes(self):
        """
        Creates the head and trunk bounding boxes.
        """
        self._log("Setting up bounding boxes...")
        all_entities = self.model.AllEntities()
        
        phantom_config = self.config.get_phantom_config(self.phantom_name.lower())
        if not phantom_config:
            raise ValueError(f"Configuration for '{self.phantom_name.lower()}' not found.")

        # Clean up pre-existing bounding boxes and antenna placements
        head_bbox_name = f"{self.phantom_name.lower()}_Head_BBox"
        trunk_bbox_name = f"{self.phantom_name.lower()}_Trunk_BBox"
        sim_bbox_name = f"{self.placement_name.lower()}_simulation_bbox"
        antenna_group_name = f"Antenna {self.frequency_mhz} MHz ({self.placement_name})"
        antenna_bbox_name = f"Antenna bounding box ({self.placement_name})"

        entities_to_delete = [
            e for e in all_entities if hasattr(e, 'Name') and e.Name in [
                head_bbox_name,
                trunk_bbox_name,
                sim_bbox_name,
                antenna_group_name,
                antenna_bbox_name
            ]
        ]
        for entity in entities_to_delete:
            self._log(f"  - Deleting existing entity: {entity.Name}")
            entity.Delete()
        
        # Re-fetch entities after deletion
        all_entities = self.model.AllEntities()

        tissue_entities = [e for e in all_entities if isinstance(e, self.XCoreModeling.TriangleMesh)]
        bbox_min, bbox_max = self.model.GetBoundingBox(tissue_entities)

        # Head BBox
        ear_skin_entity = next((e for e in all_entities if hasattr(e, 'Name') and e.Name == "Ear_skin"), None)
        if not ear_skin_entity:
            head_x_min, head_x_max = bbox_min[0], bbox_max[0]
        else:
            ear_bbox_min, ear_bbox_max = self.model.GetBoundingBox([ear_skin_entity])
            head_x_min, head_x_max = ear_bbox_min[0], ear_bbox_max[0]
        
        head_y_sep = phantom_config['head_y_separation']
        back_of_head_y = phantom_config.get('back_of_head', bbox_min[1])
        head_bbox_min_vec = self.model.Vec3(head_x_min, back_of_head_y, head_y_sep)
        head_bbox_max_vec = self.model.Vec3(head_x_max, bbox_max[1], bbox_max[2])
        head_bbox = self.XCoreModeling.CreateWireBlock(head_bbox_min_vec, head_bbox_max_vec)
        head_bbox.Name = head_bbox_name
        self._log("  - Head BBox created.")

        # Trunk BBox
        trunk_z_sep = phantom_config['trunk_z_separation']
        chest_y_ext = phantom_config['chest_extension']
        trunk_bbox_min_vec = self.model.Vec3(bbox_min[0], bbox_min[1], trunk_z_sep)
        trunk_bbox_max_vec = self.model.Vec3(bbox_max[0], chest_y_ext, head_y_sep)
        trunk_bbox = self.XCoreModeling.CreateWireBlock(trunk_bbox_min_vec, trunk_bbox_max_vec)
        trunk_bbox.Name = trunk_bbox_name
        self._log("  - Trunk BBox created.")

    def _place_antenna(self):
        """
        Places and orients the antenna in the simulation environment.
        """
        self._log("Placing and orienting antenna...")
        
        placements_config = self.config.get_phantom_placements(self.phantom_name.lower())
        if not placements_config.get(f"do_{self.placement_name.lower()}"):
            self._log(f"Placement '{self.placement_name}' is disabled in the configuration.")
            return

        # Get target point based on placement
        target_point, rotations_deg = self._get_placement_details()

        # Import and transform antenna
        antenna_path = self.antenna.get_centered_antenna_path(os.path.join(self.config.base_dir, 'data', 'antennas', 'centered'))
        if not os.path.exists(antenna_path):
            raise FileNotFoundError(f"Antenna file not found at: {antenna_path}")

        imported_entities = list(self.model.Import(antenna_path))
        
        antenna_group_orig_name = f"Antenna {self.frequency_mhz} MHz"
        new_antenna_group = next((e for e in imported_entities if hasattr(e, 'Name') and e.Name == antenna_group_orig_name), None)
        new_bbox_entity = next((e for e in imported_entities if hasattr(e, 'Name') and e.Name == "Antenna bounding box"), None)

        if not new_antenna_group:
            raise ValueError(f"Could not find antenna group '{antenna_group_orig_name}' in newly imported entities.")

        new_antenna_group.Name = f"{antenna_group_orig_name} ({self.placement_name})"
        if new_bbox_entity:
            new_bbox_entity.Name = f"Antenna bounding box ({self.placement_name})"

        new_antenna_group.IsVisible = True
        if new_bbox_entity:
            new_bbox_entity.IsVisible = True

        entities_to_transform = [new_antenna_group]
        if new_bbox_entity:
            entities_to_transform.append(new_bbox_entity)

        scale = self.model.Vec3(1, 1, 1)
        null_translation = self.model.Vec3(0, 0, 0)

        for axis, angle_deg in rotations_deg:
            rotation_vec = self.model.Vec3(0, 0, 0)
            if axis.upper() == 'X':
                rotation_vec.X = np.deg2rad(angle_deg)
            elif axis.upper() == 'Y':
                rotation_vec.Y = np.deg2rad(angle_deg)
            elif axis.upper() == 'Z':
                rotation_vec.Z = np.deg2rad(angle_deg)
            
            transform = self.model.Transform(scale, rotation_vec, null_translation)
            for entity in entities_to_transform:
                entity.ApplyTransform(transform)

        # Add a final +90 degree rotation on X-axis for all placements
        rotation_vec_x = self.model.Vec3(np.deg2rad(90), 0, 0)
        transform_x = self.model.Transform(scale, rotation_vec_x, null_translation)
        for entity in entities_to_transform:
            entity.ApplyTransform(transform_x)

        # For the cheek placement, add an additional -90 degree Z rotation
        if self.placement_name == "by_cheek":
            rotation_vec_z = self.model.Vec3(0, 0, np.deg2rad(-90))
            transform_z = self.model.Transform(scale, rotation_vec_z, null_translation)
            for entity in entities_to_transform:
                entity.ApplyTransform(transform_z)

        translation_transform = self.XCoreModeling.Transform()
        translation_transform.Translation = target_point
        for entity in entities_to_transform:
            entity.ApplyTransform(translation_transform)
            
        # Create combined simulation bounding box
        if self.placement_name.lower() == 'front_of_eyes' or self.placement_name.lower() == 'by_cheek':
            bbox_to_combine_name = f"{self.phantom_name.lower()}_Head_BBox"
        else:
            bbox_to_combine_name = f"{self.phantom_name.lower()}_Trunk_BBox"
        
        bbox_to_combine = self.model.AllEntities()[bbox_to_combine_name]
            
        combined_bbox_min, combined_bbox_max = self.model.GetBoundingBox([bbox_to_combine, new_bbox_entity])
        sim_bbox = self.XCoreModeling.CreateWireBlock(combined_bbox_min, combined_bbox_max)
        sim_bbox.Name = f"{self.placement_name.lower()}_simulation_bbox"
        self._log(f"  - Combined BBox created for {self.placement_name}.")

    def _get_placement_details(self):
        """
        Returns the target point and rotations for a given placement.
        """
        all_entities = self.model.AllEntities()
        placements_config = self.config.get_phantom_placements(self.phantom_name.lower())
        
        upright_rotations = [('X', 90), ('Y', 180)]
        cheek_rotations = [('X', 90), ('Y', 180), ('Z', 90)]

        if self.placement_name.lower() == 'front_of_eyes':
            eye_entities = [e for e in all_entities if 'Eye' in e.Name or 'Cornea' in e.Name]
            if not eye_entities:
                raise ValueError("No eye or cornea entities found for 'Eyes' placement.")
            eye_bbox_min, eye_bbox_max = self.model.GetBoundingBox(eye_entities)
            distance = placements_config.get('distance_from_eye', 100)
            center_x = (eye_bbox_min[0] + eye_bbox_max[0]) / 2.0
            center_z = (eye_bbox_min[2] + eye_bbox_max[2]) / 2.0
            target_y = eye_bbox_max[1] + distance
            return self.model.Vec3(center_x, target_y, center_z), upright_rotations
        
        elif self.placement_name.lower() == 'front_of_belly':
            trunk_bbox = self.model.AllEntities()[f"{self.phantom_name.lower()}_Trunk_BBox"]
            trunk_bbox_min, trunk_bbox_max = self.model.GetBoundingBox([trunk_bbox])
            distance = placements_config.get('distance_from_belly', 100)
            center_x = (trunk_bbox_min[0] + trunk_bbox_max[0]) / 2.0
            center_z = (trunk_bbox_min[2] + trunk_bbox_max[2]) / 2.0
            target_y = trunk_bbox_max[1] + distance
            return self.model.Vec3(center_x, target_y, center_z), upright_rotations

        elif self.placement_name.lower() == 'by_cheek':
            ear_skin_entity = next((e for e in all_entities if hasattr(e, 'Name') and e.Name == "Ear_skin"), None)
            if not ear_skin_entity:
                raise ValueError("Could not find 'Ear_skin' entity for 'Cheek' placement.")
            ear_bbox_min, ear_bbox_max = self.model.GetBoundingBox([ear_skin_entity])
            distance = placements_config.get('distance_from_cheek', 15)
            center_y = (ear_bbox_min[1] + ear_bbox_max[1]) / 2.0
            center_z = (ear_bbox_min[2] + ear_bbox_max[2]) / 2.0
            target_x = ear_bbox_max[0] + distance
            return self.model.Vec3(target_x, center_y, center_z), cheek_rotations
        
        else:
            raise ValueError(f"Invalid placement name: {self.placement_name}")

    def _setup_simulation(self):
        """
        Creates and configures the EM-FDTD simulation.
        """
        self._log("Setting up simulation...")
        
        all_entities = self.model.AllEntities()
        sim_params = self.config.get_simulation_parameters()
        grid_params = self.config.get_gridding_parameters()

        # --- Simulation Cleanup ---
        # Delete all existing simulations to ensure a clean state
        if self.document.AllSimulations:
            self._log(f"  - Deleting {len(self.document.AllSimulations)} existing simulation(s)...")
            # Iterate over a copy of the list as we are modifying it
            for sim in list(self.document.AllSimulations):
                self._log(f"    - Deleting: {sim.Name}")
                self.document.AllSimulations.Remove(sim)
        
        sim_name = f"EM_FDTD_{self.phantom_name}_{self.antenna.get_model_name()}_{self.placement_name}"

        # --- Create and Configure Simulation ---
        simulation = self.emfdtd.Simulation()
        simulation.Name = sim_name
        self.document.AllSimulations.Add(simulation)

        # Set Frequency and General Parameters
        # IMPORTANT: Frequency must be set *before* assigning materials for dispersive properties to be calculated correctly.
        simulation.Frequency = self.frequency_mhz, self.units.MHz
        
        # --- Set Solver Settings ---
        solver_settings = self.config.get_solver_settings()
        if solver_settings:
            kernel_type = solver_settings.get("kernel", "CUDA")
            # location = solver_settings.get("location", "localhost") # TODO: Implement location setting
            
            solver = simulation.SolverSettings
            kernel_enum = solver.Kernel.enum
            available_kernels = [k.name for k in kernel_enum]
            
            # Find the correct kernel name, case-insensitively
            kernel_to_set = None
            for available in available_kernels:
                if available.lower() == kernel_type.lower():
                    kernel_to_set = available
                    break

            if kernel_to_set:
                solver.Kernel = getattr(kernel_enum, kernel_to_set)
                self._log(f"  - Solver kernel set to: {kernel_to_set}")
            else:
                self._log(f"  - Warning: Invalid solver kernel '{kernel_type}' specified. Available: {available_kernels}. Using default.")

        term_level = sim_params.get("global_auto_termination", "GlobalAutoTerminationWeak")
        
        # Dynamically calculate simulation time
        sim_bbox_entity = self.model.AllEntities()[f"{self.placement_name.lower()}_simulation_bbox"]
        bbox_min, bbox_max = self.model.GetBoundingBox([sim_bbox_entity])
        diagonal_vec = np.array(bbox_max) - np.array(bbox_min)
        diagonal_length_mm = np.linalg.norm(diagonal_vec)
        diagonal_length_m = diagonal_length_mm / 1000.0  # Convert mm to m
        
        c0 = 299792458  # Speed of light in m/s
        time_to_travel_s = (2 * diagonal_length_m) / c0
        
        frequency_hz = self.frequency_mhz * 1e6
        period_s = 1 / frequency_hz
        sim_time_periods = time_to_travel_s / period_s
        
        self._log(f"  - BBox Diagonal: {diagonal_length_m:.4f} m")
        self._log(f"  - Calculated sim time: {time_to_travel_s:.2e} s ({sim_time_periods:.2f} periods)")
        
        simulation.SetupSettings.SimulationTime = sim_time_periods, self.units.Periods
        
        term_options = simulation.SetupSettings.GlobalAutoTermination.enum
        
        # Set the termination level from the config
        if hasattr(term_options, term_level):
            simulation.SetupSettings.GlobalAutoTermination = getattr(term_options, term_level)
        else:
            self._log(f"  - Warning: Invalid termination level '{term_level}' specified. Using default.")

        # If user-defined, set the convergence level
        if term_level == "GlobalAutoTerminationUserDefined":
            convergence_db = sim_params.get("convergence_level_dB", -30)
            simulation.SetupSettings.ConvergenceLevel = convergence_db
            self._log(f"  - Set user-defined convergence level to: {convergence_db} dB")

        # Set Background Material
        background_settings = simulation.raw.BackgroundMaterialSettings()
        try:
            air_material = self.database["Generic 1.1"]["Air"]
        except KeyError:
            raise RuntimeError("Could not find 'Air' in the 'Generic 1.1' material database.")
        simulation.raw.AssignMaterial(background_settings, air_material)

        # Set Phantom Materials
        # This logic assumes that the only TriangleMesh entities present are the phantom parts.
        # This is safe because the antenna model does not use TriangleMesh objects.
        phantom_parts = [e for e in all_entities if isinstance(e, self.XCoreModeling.TriangleMesh)]
        if not phantom_parts:
            raise RuntimeError("ERROR: No TriangleMesh parts could be found in the project.")
        
        material_groups = {}
        name_mapping = self.config.get_material_mapping()
        for part in phantom_parts:
            base_name = part.Name.split('(')[0].strip()
            material_name = name_mapping.get(base_name, base_name.replace('_', ' '))
            if material_name not in material_groups:
                material_groups[material_name] = []
            material_groups[material_name].append(part)

        successful_assignments = 0
        for material_name, entities in material_groups.items():
            material_settings = self.emfdtd.MaterialSettings()
            try:
                mat = self.database["IT'IS 4.2"][material_name]
                simulation.LinkMaterialWithDatabase(material_settings, mat)
                simulation.Add(material_settings, entities)
                successful_assignments += len(entities)
            except KeyError:
                self._log(f"    - Warning: Could not find material '{material_name}' in IT'IS 4.2 database.")
        self._log(f"  - Assigned materials for {successful_assignments}/{len(phantom_parts)} parts.")

        # Set Antenna Source & Materials
        self._log("  - Setting antenna source and materials...")
        antenna_group_name = f"Antenna {self.frequency_mhz} MHz ({self.placement_name})"
        antenna_group = next((e for e in all_entities if hasattr(e, 'Name') and e.Name == antenna_group_name), None)
        if not antenna_group:
            raise RuntimeError(f"Could not find antenna group: {antenna_group_name}")
        
        self._log(f"    - Found antenna group: '{antenna_group.Name}'")
        
        source_entity_name = self.antenna.get_source_entity_name()
        
        # Define and validate all required components
        antenna_model_name = self.antenna.get_model_name()
        component_names = self.config.get_antenna_component_names(antenna_model_name)
        if not component_names:
            raise ValueError(f"No component names defined for antenna model '{antenna_model_name}' in simulation_config.json")

        components = {}
        for key, name in component_names.items():
            entity = next((e for e in antenna_group.Entities if e.Name == name), None)
            if not entity:
                # Also search top-level entities for PIFA parts
                entity = next((e for e in all_entities if e.Name == name), None)

            if not entity:
                raise RuntimeError(f"Could not find required antenna component '{name}' for model '{antenna_model_name}'")
            
            components[key] = entity
            self._log(f"      - Found component: {key} ('{name}')")

        source_entity = components["source"]
        antenna_entity = components["antenna"]
        battery_entity = components["battery"]
        ground_entity = components["ground"]

        antenna_bodies = [e for e in [antenna_entity, battery_entity, ground_entity] if isinstance(e, self.model.Body)]
        if antenna_bodies:
            material_settings = self.emfdtd.MaterialSettings()
            try:
                mat = self.database["Generic 1.1"]["Copper"]
                simulation.LinkMaterialWithDatabase(material_settings, mat)
                simulation.Add(material_settings, antenna_bodies)
            except KeyError:
                self._log("    - Warning: Could not find 'Copper' in 'Generic 1.1' database.")

        edge_source_settings = self.emfdtd.EdgeSourceSettings()
        edge_source_settings.CenterFrequency = self.frequency_mhz, self.units.MHz
        edge_source_settings.Bandwidth = self.frequency_mhz, self.units.MHz
        simulation.Add(edge_source_settings, [source_entity])

        # Define Gridding
        antenna_gridding = grid_params.get("antenna_gridding", 0.3)
        fine_grid = grid_params.get("fine_grid", 0.3)
        coarse_grid = grid_params.get("coarse_grid", 3.0)
        
        sim_bbox_entity = self.model.AllEntities()[f"{self.placement_name.lower()}_simulation_bbox"]
        simulation.GlobalGridSettings.BoundingBox = self.model.GetBoundingBox([sim_bbox_entity])
        manual_grid_sim_bbox = simulation.AddManualGridSettings([sim_bbox_entity])
        manual_grid_sim_bbox.MaxStep = np.array([coarse_grid] * 3), self.units.MilliMeters

        auto_grid_settings = simulation.AddAutomaticGridSettings([source_entity])
        manual_grid_antenna = simulation.AddManualGridSettings([antenna_entity])
        manual_grid_antenna.MaxStep = np.array([antenna_gridding] * 3), self.units.MilliMeters

        if self.placement_name.lower() == 'cheek':
            battery_grid_res = np.array([fine_grid, coarse_grid, coarse_grid])
        else:
            battery_grid_res = np.array([coarse_grid, fine_grid, coarse_grid])
        
        manual_grid_battery = simulation.AddManualGridSettings([battery_entity, ground_entity])
        manual_grid_battery.MaxStep = battery_grid_res, self.units.MilliMeters

        # Define Sensors
        edge_sensor_settings = self.emfdtd.EdgeSensorSettings()
        simulation.Add(edge_sensor_settings, [source_entity])

        # Voxelization Settings
        voxeler_settings = self.emfdtd.AutomaticVoxelerSettings()
        core_antenna_parts = [antenna_entity, battery_entity, source_entity, ground_entity]
        all_simulation_parts = phantom_parts + core_antenna_parts
        simulation.Add(voxeler_settings, all_simulation_parts)

        # Update all material properties to reflect the new simulation frequency
        self._log("  - Updating all material properties for the new frequency...")
        
        # Temporarily suppress verbose log output during material update
        import XCore
        
        self._log("    - Suppressing engine log for material update...")
        old_log_level = XCore.SetLogLevel(XCore.eLogCategory.Nothing)
        
        simulation.UpdateAllMaterials()
        
        # Restore the original log level
        XCore.SetLogLevel(old_log_level)
        self._log("    - Restored engine log level.")

        self.simulation = simulation
        self._log("Simulation setup complete.")