import json
import os
from typing import Any, Dict

def get_parameter_from_json(file_path: str, json_path: str) -> Any:
    """
    Extracts a parameter from a JSON file using a dot-separated path.

    Args:
        file_path (str): The path to the JSON file.
        json_path (str): The dot-separated path to the desired value.

    Returns:
        Any: The extracted value, or None if not found.
    """
    if not os.path.exists(file_path):
        return None

    with open(file_path, 'r') as f:
        data = json.load(f)

    keys = json_path.split('.')
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value

def get_parameter(source_config: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Generic function to retrieve a parameter from a specified source.

    Args:
        source_config (Dict[str, Any]): Configuration for the data source.
        context (Dict[str, Any]): Contextual information like frequency, phantom_name, etc.

    Returns:
        Any: The retrieved parameter value, or None if an error occurs.
    """
    source_type = source_config.get('source_type')

    if source_type == 'json':
        file_path_template = source_config.get('file_path_template')
        if not file_path_template:
            return None
        
        # Replace placeholders in the file path template with values from the context
        try:
            file_path = file_path_template.format(**context)
        except KeyError as e:
            print(f"Error: Missing context for placeholder in file_path_template: {e}")
            return None

        json_path = source_config.get('json_path')
        if not json_path:
            return None
            
        project_root = context.get('project_root', '')
        full_path = os.path.join(project_root, file_path)

        return get_parameter_from_json(full_path, json_path)
    
    # Add other source types here in the future (e.g., 'simulation')
    # elif source_type == 'simulation':
    #     # ... implementation for extracting from simulation ...
    #     pass

    else:
        print(f"Error: Unsupported source type '{source_type}'")
        return None
