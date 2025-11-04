from importlib import metadata

try:
    __version__ = metadata.version("goliat")
except metadata.PackageNotFoundError:
    # Fallback: read from pyproject.toml directly
    import tomllib
    from pathlib import Path

    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    if pyproject_path.exists():
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
            __version__ = pyproject.get("project", {}).get("version", "unknown")
    else:
        __version__ = "unknown"
