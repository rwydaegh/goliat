import os
import sys
import logging

# 1. Add project root to Python path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# 2. Set up logging and initialize Sim4Life
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
from src.utils import ensure_s4l_running
from s4l_v1._api import simwrappers
print("--- Initializing Sim4Life ---")
ensure_s4l_running()
print("--- Sim4Life Initialized ---")

# 3. Import the necessary simulation module
import s4l_v1.simulation.emfdtd

print("\n--- Available Sim4Life Servers (using DEPRECATED global function) ---")
try:
    # 4. Call the global, deprecated GetAvailableServers function
    print("Calling simwrappers.XSimulator.GetAvailableServers()...")
    available_servers = dict(simwrappers.XSimulator.GetAvailableServers())

    if not available_servers:
        print("No servers found.")
    else:
        print(f"Found {len(available_servers)} servers:")
        for i, (name, server_id) in enumerate(available_servers.items()):
            print(f"  {i+1}. Name: {name}, ID: {server_id}")

except Exception as e:
    print(f"An error occurred: {e}")
    import traceback
    traceback.print_exc()

print("------------------------------------")

print("\n--- Available Sim4Life Servers (using MODERN instance method) ---")
try:
    # 5. Create a simulation instance to call the modern GetComputeResources method
    print("Creating a dummy simulation object with solver settings...")
    sim = s4l_v1.simulation.emfdtd.Simulation()
    solver_settings = sim.SolverSettings
    solver_settings.Kernel = solver_settings.Kernel.enum.Cuda
    
    print("Calling sim.raw.GetComputeResources()...")
    # The .raw property gives access to the underlying XSimulator object
    compute_resources = sim.raw.GetComputeResources()

    if not compute_resources:
        print("No compute resources found.")
    else:
        print(f"Found {len(compute_resources)} resources:")
        # The modern API returns a list of 'XSimulator.ComputeResource' objects.
        # These objects have .Name and .Id attributes.
        for i, resource in enumerate(compute_resources):
            # Check for attributes to be safe
            name = getattr(resource, 'Name', 'N/A')
            resource_id = getattr(resource, 'Id', 'N/A')
            print(f"  {i+1}. Name: {name}, ID: {resource_id}")

except Exception as e:
    print(f"An error occurred: {e}")
    import traceback
    traceback.print_exc()

print("------------------------------------")
print("\nDebug script finished. If only 'localhost' is listed, the script is running in an unauthenticated context.")