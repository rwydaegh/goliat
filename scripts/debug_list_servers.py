import s4l_v1
import s4l_v1.simulation
import sys

# This script attempts to connect to an already running Sim4Life GUI instance.
# It will NOT launch a new application.
# Please ensure Sim4Life is running before executing this script.

print("--- Attaching to existing Sim4Life session to query servers ---")

try:
    # The import of s4l_v1 automatically tries to connect to a running instance.
    # We can check if a document is open to see if we are connected.
    # A more direct check is not readily available.

    # Fetch the available servers
    available_servers = s4l_v1.simulation.GetAvailableServers()

    print(f"\nRaw output of GetAvailableServers(): {available_servers}")
    print(f"Type of returned object: {type(available_servers)}")

    if not available_servers:
        print("\nResult: No servers found or the returned object is empty.")
        print("This could mean no cloud servers are configured or you are not logged in within the Sim4Life GUI.")
    elif isinstance(available_servers, dict):
        print("\n--- Parsed Server List (Dictionary) ---")
        for name, uuid in available_servers.items():
            print(f"  - Name: {name}, ID: {uuid}")
    elif isinstance(available_servers, list):
        print("\n--- Parsed Server List (List) ---")
        for item in available_servers:
            print(f"  - Item: {item} (Type: {type(item)})")
    else:
        print(f"\n--- Unrecognized Format ---")
        print("The returned object is not a dictionary or a list.")

except Exception as e:
    import traceback
    print(f"\nAn error occurred: {e}")
    print("Please ensure the Sim4Life GUI application is running before executing this script.")
    traceback.print_exc()

print("\n--- Script Finished ---")