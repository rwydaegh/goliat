"""
Dispersion model fitting and material property lookup for multisine simulations.

This package provides:
- `fitter`: Fit dispersion models to match permittivity/conductivity
- `material_cache`: Query material properties from IT'IS V5.0 database
"""

from .fitter import DispersionParams, PoleFit, fit_dispersion, validate_fit
from .material_cache import (
    get_material_properties,
    get_cole_cole_params,
    get_available_tissues,
    load_material_cache,
    clear_cache,
)

__all__ = [
    "DispersionParams",
    "PoleFit",
    "fit_dispersion",
    "validate_fit",
    "get_material_properties",
    "get_cole_cole_params",
    "get_available_tissues",
    "load_material_cache",
    "clear_cache",
]
