import s4l_v1.document
import ModelsDownload
import s4l_v1

def get_licensed_models():
    """
    This script retrieves a list of all available models and phantoms
    from the Sim4Life Python API and prints out the ones that are licensed.
    """
    print("Updating the list of available downloads...")
    # It's good practice to update the list before fetching it.
    # The function returns False if the operation fails.
    if not ModelsDownload.UpdateAvailableDownloads():
        print("Could not update the list of available downloads. Please check your connection or credentials.")
        return

    print("Fetching available downloads...")
    # Get the list of all available ModelDownloadItem objects.
    available_downloads = ModelsDownload.GetAvailableDownloads()

    if not available_downloads:
        print("No available downloads found.")
        return

    print("\n--- Licensed Models and Phantoms ---")
    licensed_items = []
    for item in available_downloads:
        # The 'Licensed' property is True if a license is available or not needed.
        if item.Licensed:
            licensed_items.append(item)
            print(f"  - {item.Name} (Version: {item.Version})")

    if not licensed_items:
        print("No licensed models or phantoms found in the available downloads list.")
    
    print("\n--- Unlicensed Models and Phantoms ---")
    unlicensed_items = []
    for item in available_downloads:
        if not item.Licensed:
            unlicensed_items.append(item)
            print(f"  - {item.Name} (Version: {item.Version})")

    if not unlicensed_items:
        print("All available models and phantoms are licensed.")


if __name__ == "__main__":
    # This script needs to be run within a Sim4Life environment
    # where the s4l_v1 module is available.
    # You can run this from the Sim4Life Python console.
    get_licensed_models()
