# Cloud Simulation Guide

This document outlines how to configure and run simulations on a remote Sim4Life cloud server using this framework.

## 1. Configuration

The framework identifies which server to use by reading a `server` key from the active JSON configuration file.

### Method

In your study's configuration file (e.g., `configs/test_cloud_config.json`), add a `"server"` key with the name of your target cloud server as its value.

**Example:**
```json
{
    "extends": "base_config.json",
    "study_name": "Cloud Simulation Test",
    "study_type": "near_field",
    "server": "MyCloudServerName", 
    "phantoms": {
        "thelonious": {
            "placements": ["front_of_eyes"]
        }
    },
    "frequencies_mhz": [700]
}
```

### How It Works

The [`Config`](../src/config.py) class is responsible for loading all settings. The following method retrieves the server name:

```python
# In src/config.py
def get_server(self):
    """Returns the server name."""
    return self.config.get("server", None)
```

If the `server` key is not present in the configuration, the method returns `None`, and the simulation will run locally by default.

## 2. Simulation Execution

The [`SimulationRunner`](../src/simulation_runner.py) class uses the server name to find the corresponding server ID and dispatch the simulation.

### Implementation

The core logic resides in the `run` method of the `SimulationRunner` class:

```python
# In src/simulation_runner.py

# 1. Get the server name from the config
server_name = self.config.get_server()
server_id = None

# 2. If a server name is provided, search for it
if server_name:
    self._log(f"Attempting to use server: {server_name}", level='progress')
    available_servers = simulation.GetAvailableServers()
    for server in available_servers:
        # 3. Match the name and get the server ID
        if server_name.lower() in server.Name.lower():
            server_id = server.Id
            self._log(f"Found matching server: {server.Name}", level='progress')
            break
    if not server_id:
        raise RuntimeError(f"Server '{server_name}' not found.")

try:
    # 4. Run the simulation, passing the server_id if found.
    #    If server_id is None, it runs locally.
    simulation.RunSimulation(wait=True, server_id=server_id)
    self._log("Simulation finished.", level='progress')
except Exception as e:
    self._log(f"An error occurred during simulation run: {e}", level='progress')
    if server_id:
        # 5. Provide a helpful message if a cloud simulation fails
        self._log("If you are running on the cloud, please ensure you are logged into Sim4Life via the GUI.", level='progress')
    traceback.print_exc()
```

### Workflow Summary

1.  The `Config` class reads the `server` name from the JSON file.
2.  The `SimulationRunner` gets this server name.
3.  It calls `simulation.GetAvailableServers()` to get a list of all configured local and cloud servers.
4.  It iterates through the list to find a server whose name matches the one from the config.
5.  If a match is found, it passes the `server.Id` to the `simulation.RunSimulation()` method, which directs the simulation to that cloud resource.