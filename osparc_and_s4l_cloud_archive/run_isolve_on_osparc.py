import os
import sys
import glob
import shutil
import s4l_v1.document as document
import s4l_v1.simulation.emlf as emlf
import XCore

def run_isolve():
    """
    This script is intended to be run on the oSPARC platform by a python-runner.
    It takes a .smash file as input, runs the iSolve solver, and saves the results.
    """
    # Initialize the Sim4Life application
    app = XCore.GetOrCreateConsoleApp()
    
    # oSPARC provides INPUT_FOLDER and OUTPUT_FOLDER environment variables
    input_dir = os.environ.get("INPUT_FOLDER", "/input")
    output_dir = os.environ.get("OUTPUT_FOLDER", "/output")

    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")

    # Find the .smash file in the input directory
    smash_files = glob.glob(os.path.join(input_dir, '*.smash'))
    if not smash_files:
        # The example uses .smash_Results, but the runner script in the example uses .smash
        # Let's check for .smash_Results as well
        smash_files = glob.glob(os.path.join(input_dir, '*.smash_Results'))

    if not smash_files:
        raise FileNotFoundError(f"No .smash or .smash_Results file found in {input_dir}")

    project_path = smash_files[0]
    print(f"Opening project: {project_path}")
    document.Open(project_path)

    # Get the iSolve simulation
    simulations = document.AllSimulations
    print(f"Found {len(simulations)} simulations in the project.")
    for i, sim in enumerate(simulations):
        print(f"  Simulation {i+1}: '{sim.Name}'")

    isolve_sim = None
    for sim in simulations:
        if "em" in sim.Name.lower(): # Look for "EM" instead of "isolve"
            isolve_sim = sim
            break
    
    if not isolve_sim:
        raise RuntimeError("No iSolve simulation found in the project.")

    print(f"Found iSolve simulation: {isolve_sim.Name}")

    # Run the simulation
    print("Starting simulation...")
    isolve_sim.RunSimulation(wait=True)
    print("Simulation finished.")

    # Copy results to output directory
    # This part is tricky as we don't know the exact output structure.
    # For now, let's assume the results are in the project's results folder.
    project_name = os.path.basename(project_path)
    results_folder = project_path + "_Results"
    
    if os.path.exists(results_folder):
        output_results_path = os.path.join(output_dir, os.path.basename(results_folder))
        print(f"Copying results from {results_folder} to {output_results_path}")
        shutil.copytree(results_folder, output_results_path)
    else:
        print(f"Warning: Could not find results folder: {results_folder}")

    print("Script finished successfully.")

if __name__ == "__main__":
    run_isolve()