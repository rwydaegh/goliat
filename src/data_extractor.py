import json
import os
from typing import Any, Dict


def get_parameter_from_json(file_path: str, json_path: str) -> Any:
    """
    Extracts a nested parameter from a JSON file using a dot-separated path.

    This function navigates through a nested dictionary loaded from a JSON file
    to retrieve a value specified by a path string (e.g., "key1.key2.key3").

    Args:
        file_path (str): The absolute or relative path to the JSON file.
        json_path (str): The dot-separated path representing the nested keys.

    Returns:
        Any: The value found at the specified path, or None if the path is
             invalid or the file does not exist.
    """
    if not os.path.exists(file_path):
        return None

    with open(file_path, "r") as f:
        data = json.load(f)

    keys = json_path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


def get_parameter(source_config: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Retrieves a parameter from a specified data source based on a configuration.

    This function acts as a generic data retrieval interface. It uses a
    `source_config` dictionary to determine the type of data source (e.g., 'json')
    and the necessary parameters to access it. The `context` dictionary provides
    dynamic values to format file paths or other parameters.

    Args:
        source_config (Dict[str, Any]): A dictionary defining the data source,
            including 'source_type', 'file_path_template', and 'json_path'.
        context (Dict[str, Any]): A dictionary with contextual information
            (e.g., frequency, phantom_name) to format the file path.

    Returns:
        Any: The retrieved parameter value, or None if an error occurs during
             retrieval.
    """
    source_type = source_config.get("source_type")

    if source_type == "json":
        file_path_template = source_config.get("file_path_template")
        if not file_path_template:
            return None

        try:
            file_path = file_path_template.format(**context)
        except KeyError as e:
            import logging

            logging.getLogger("verbose").error(
                f"Error: Missing context for placeholder in file_path_template: {e}"
            )
            return None

        json_path = source_config.get("json_path")
        if not json_path:
            return None

        project_root = context.get("project_root", "")
        full_path = os.path.join(project_root, file_path)

        return get_parameter_from_json(full_path, json_path)

    # Future extension for other data source types
    # elif source_type == 'simulation':
    #     # ... implementation for extracting from simulation results ...
    #     pass

    else:
        import logging

        logging.getLogger("verbose").error(
            f"Error: Unsupported source type '{source_type}'"
        )
        return None
