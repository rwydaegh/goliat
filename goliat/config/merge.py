"""Dictionary merging utilities."""


def deep_merge(source: dict, destination: dict) -> dict:
    """Recursively merges two dictionaries, overwriting destination with source values.

    Args:
        source: The dictionary with values to merge.
        destination: The dictionary to be merged into.

    Returns:
        The merged dictionary.
    """
    for key, value in source.items():
        if isinstance(value, dict) and key in destination and isinstance(destination[key], dict):
            deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination
