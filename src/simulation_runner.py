import os
import glob
import subprocess
from .utils import open_project

class SimulationRunner:
    """
    Manages the execution of the simulation, either through the Sim4Life API
    or by calling the iSolve.exe solver manually.
    """
    def __init__(self, config, project_path, simulation, verbose=True):
        self.config = config
        self.project_path = project_path
        self.simulation = simulation
        self.verbose = verbose
        import s4l_v1.document
        self.document = s4l_v1.document

    def _log(self, message):
        if self.verbose:
            print(message)

    def run(self):
        """
        Runs the simulation, either via S4L API or iSolve executable.
        """
        self._log(f"Running simulation...")
        if not self.simulation:
            self._log(f"ERROR: Simulation object not found.")
            return

        if hasattr(self.simulation, "WriteInputFile"):
            self._log("Writing solver input file...")
            self.simulation.WriteInputFile()
            self.document.SaveAs(self.project_path) # Force a save to flush files
        
        if self.config.get_manual_isolve():
            self._run_isolve_manual()
        else:
            self.simulation.RunSimulation(wait=True)
            self._log("Simulation finished.")
        
        return self.simulation

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
            subprocess.run(command, check=True)
            self._log("iSolve.exe completed successfully.")
            
            self._log("Re-opening project to load results...")
            self.document.Close()
            open_project(self.project_path)
            
            sim_name = self.simulation.Name
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