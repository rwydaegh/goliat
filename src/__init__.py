from importlib import metadata

try:
    __version__ = metadata.version("goliat")
except metadata.PackageNotFoundError:
    # The package is not installed, so we fall back to the version defined in pyproject.toml
    # This is a common scenario when running from source without installation.
    __version__ = "0.2.0"
