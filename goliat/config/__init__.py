"""Configuration management module.

This package provides configuration loading, access, and management utilities.
The main Config class is re-exported for backward compatibility.
"""

# Re-export Config and deep_merge from core module
from .core import Config, deep_merge

__all__ = ["Config", "deep_merge"]
