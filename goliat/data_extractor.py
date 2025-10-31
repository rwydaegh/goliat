import json
import os
from typing import Any, Dict


def get_parameter_from_json(file_path: str, json_path: str) -> Any:
    """Extracts a nested value from a JSON file using dot notation.

    Args:
        file_path: Path to the JSON file.
        json_path: Dot-separated path like 'section.subsection.key'.

    Returns:
        The value at the path, or None if not found.
    """
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return None

    keys = json_path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


def get_parameter(source_config: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """Retrieves a parameter from a data source using a config-driven approach.

    Supports JSON sources currently. The source_config defines where to look,
    and context provides values for formatting paths (e.g., project_root).

    Args:
        source_config: Dict with 'source_type', 'file_path_template', 'json_path'.
        context: Values for formatting file paths.

    Returns:
        The retrieved value, or None on error.
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

            logging.getLogger("verbose").error(f"Error: Missing context for placeholder in file_path_template: {e}")
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

        logging.getLogger("verbose").error(f"Error: Unsupported source type '{source_type}'")
        return None
