import argparse
import json
import logging
import os
import sys

from src.config import Config
from src.setups.phantom_setup import PhantomSetup
from src.utils import ensure_s4l_running

# Add the src directory to the Python path to allow for module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def extract_tissues(phantom_name):
    """
    Loads a phantom, extracts its tissue names, and saves them to a JSON file.
    """
    print(f"Starting tissue extraction for phantom: {phantom_name}")

    # Initialize a basic logger for the setup script
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Initialize the configuration
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config = Config(base_dir)

    # Ensure Sim4Life is running
    ensure_s4l_running()

    # Create a new project in memory
    import s4l_v1.document

    s4l_v1.document.New()
    print("New Sim4Life project created.")

    # Set up and load the phantom
    phantom_setup = PhantomSetup(config, phantom_name, logger, logger)
    if not phantom_setup.ensure_phantom_is_loaded():
        print(
            f"Could not load phantom {phantom_name}. It may need to be downloaded first."
        )
        return

    # Get all entities and extract tissue names
    import s4l_v1.model

    all_entities = s4l_v1.model.AllEntities()

    phantom_entity = next(
        (e for e in all_entities if phantom_name.lower() in e.Name.lower()), None
    )

    if not phantom_entity:
        print(f"Could not find the phantom entity for '{phantom_name}' after loading.")
        return

    # Tissue entities are identified as TriangleMesh objects within the model
    import XCoreModeling

    tissue_entities = [
        e for e in all_entities if isinstance(e, XCoreModeling.TriangleMesh)
    ]
    tissue_names = sorted([tissue.Name for tissue in tissue_entities])

    print(f"Found {len(tissue_names)} tissues in '{phantom_name}'.")

    # Define the output path and save the results
    output_dir = os.path.join(base_dir, "data", "phantom_tissues")
    os.makedirs(output_dir, exist_ok=True)
    output_filepath = os.path.join(output_dir, f"{phantom_name}_tissues.json")

    with open(output_filepath, "w") as f:
        json.dump(tissue_names, f, indent=4)

    print(f"Tissue list saved to: {output_filepath}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract tissue names from a Sim4Life phantom."
    )
    parser.add_argument(
        "phantom_name",
        type=str,
        help="The name of the phantom to process (e.g., 'duke', 'ella').",
    )

    args = parser.parse_args()

    extract_tissues(args.phantom_name)
