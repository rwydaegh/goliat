"""
Material property provider for multisine dispersion fitting.

Computes material properties (eps_r, sigma) at any frequency using the
Gabriel 4-Cole-Cole model from IT'IS V5.0 database.

Supports two modes:
1. Direct DB lookup (preferred) - queries IT'IS V5.0 database
2. JSON cache fallback - uses precomputed cache file
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Physical constants
EPS_0 = 8.854187817e-12  # Vacuum permittivity (F/m)

# Database and cache paths
_DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "itis_v5.db"
_DEFAULT_CACHE_PATH = Path(__file__).parent.parent.parent / "data" / "material_properties_cache.json"

# Gabriel Parameters property ID in the database
_GABRIEL_PROP_ID = "37f803e4-fc61-4b2b-9a41-39bd6569eb28"

# In-memory caches
_db_gabriel_params: Optional[dict] = None  # {tissue_name: (ef, poles, sigma)}
_json_cache: Optional[dict] = None


def _cole_cole(f_hz: float, ef: float, poles: list, sigma_ionic: float) -> tuple:
    """
    Calculate eps_r and sigma at frequency using 4-Cole-Cole model.

    Args:
        f_hz: Frequency in Hz
        ef: Epsilon infinity (high-frequency limit)
        poles: List of (delta_eps, tau_seconds, alpha) tuples
        sigma_ionic: Ionic conductivity in S/m

    Returns:
        Tuple of (eps_r, sigma)
    """
    omega = 2 * np.pi * f_hz
    eps_complex = ef + 0j

    for delta_eps, tau, alpha in poles:
        if delta_eps != 0 and tau != 0 and alpha < 1:
            eps_complex += delta_eps / (1 + (1j * omega * tau) ** (1 - alpha))

    # Add ionic conductivity contribution
    eps_complex -= 1j * sigma_ionic / (omega * EPS_0)

    eps_r = float(np.real(eps_complex))
    sigma = float(-omega * EPS_0 * np.imag(eps_complex))

    return eps_r, sigma


def _parse_gabriel_params(blob: bytes) -> tuple:
    """
    Parse Gabriel parameters from database BLOB.

    Format: [ef, del1, tau1_ps, alf1, del2, tau2_ns, alf2, del3, tau3_us, alf3, del4, tau4_ms, alf4, sigma]
    """
    arr = np.frombuffer(blob, dtype=np.float64)

    if len(arr) != 14:
        return None, None, None

    ef = arr[0]
    sigma_ionic = arr[13]

    # Convert time constants to seconds
    poles = [
        (arr[1], arr[2] * 1e-12, arr[3]),  # tau1 in ps
        (arr[4], arr[5] * 1e-9, arr[6]),  # tau2 in ns
        (arr[7], arr[8] * 1e-6, arr[9]),  # tau3 in µs
        (arr[10], arr[11] * 1e-3, arr[12]),  # tau4 in ms
    ]

    return ef, poles, sigma_ionic


def _load_db_params(db_path: Optional[Path] = None) -> dict:
    """
    Load Gabriel parameters for all materials from IT'IS database.

    Returns:
        Dict of {tissue_name: (ef, poles, sigma_ionic)}
    """
    global _db_gabriel_params

    if _db_gabriel_params is not None:
        return _db_gabriel_params

    path = db_path or _DEFAULT_DB_PATH

    if not path.exists():
        raise FileNotFoundError(
            f"IT'IS database not found at {path}\n"
            "This file is stored in Git LFS. To download it, run:\n"
            "  git lfs install\n"
            "  git lfs pull --include='data/itis_v5.db'\n"
            "Or run 'goliat init' which handles this automatically."
        )

    conn = sqlite3.connect(str(path))
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT m.name, v.vals
        FROM vectors v
        JOIN materials m ON v.mat_id = m.mat_id
        WHERE v.prop_id = ?
        """,
        (_GABRIEL_PROP_ID,),
    )

    results = cursor.fetchall()
    conn.close()

    _db_gabriel_params = {}
    for name, blob in results:
        ef, poles, sigma = _parse_gabriel_params(blob)
        if ef is not None:
            _db_gabriel_params[name] = (ef, poles, sigma)

    logger.info(f"Loaded Gabriel parameters for {len(_db_gabriel_params)} tissues from DB")
    return _db_gabriel_params


def _get_from_db(tissue_name: str, frequencies_mhz: list[int]) -> list[dict]:
    """Get material properties by computing Cole-Cole from DB parameters."""
    params = _load_db_params()

    if tissue_name not in params:
        # Try name variations
        alt_names = [
            tissue_name.replace(" ", "_"),
            tissue_name.replace("_", " "),
            tissue_name.title(),
        ]
        for alt in alt_names:
            if alt in params:
                tissue_name = alt
                break
        else:
            raise KeyError(f"Tissue '{tissue_name}' not found in IT'IS database. Available: {list(params.keys())[:10]}...")

    ef, poles, sigma_ionic = params[tissue_name]

    # Check if air (all deltas zero)
    is_air = all(p[0] == 0 for p in poles)

    result = []
    for freq_mhz in frequencies_mhz:
        if is_air:
            result.append({"eps_r": float(ef), "sigma": 0.0})
        else:
            eps_r, sigma = _cole_cole(freq_mhz * 1e6, ef, poles, sigma_ionic)
            result.append({"eps_r": eps_r, "sigma": sigma})

    return result


def _load_json_cache(cache_path: Optional[Path] = None) -> dict:
    """Load material properties from JSON cache file."""
    global _json_cache

    if _json_cache is not None:
        return _json_cache

    path = cache_path or _DEFAULT_CACHE_PATH

    if not path.exists():
        raise FileNotFoundError(f"Material cache not found at {path}")

    with open(path, encoding="utf-8") as f:
        _json_cache = json.load(f)

    logger.info(f"Loaded JSON cache with {len(_json_cache.get('tissues', {}))} tissues")  # type: ignore[union-attr]
    return _json_cache  # type: ignore[return-value]


def _get_from_cache(tissue_name: str, frequencies_mhz: list[int]) -> list[dict]:
    """Get material properties from JSON cache."""
    cache = _load_json_cache()
    tissues = cache.get("tissues", {})

    if tissue_name not in tissues:
        alt_names = [
            tissue_name.replace(" ", "_"),
            tissue_name.replace("_", " "),
            tissue_name.title(),
        ]
        for alt in alt_names:
            if alt in tissues:
                tissue_name = alt
                break
        else:
            raise KeyError(f"Tissue '{tissue_name}' not found in cache")

    tissue_data = tissues[tissue_name]
    result = []

    for freq in frequencies_mhz:
        freq_str = str(freq)
        if freq_str not in tissue_data:
            raise ValueError(f"Frequency {freq} MHz not in cache for '{tissue_name}'. Available: {list(tissue_data.keys())}")
        result.append(tissue_data[freq_str])

    return result


def get_material_properties(
    tissue_name: str,
    frequencies_mhz: list[int],
    use_db: bool = True,
) -> list[dict]:
    """
    Get material properties for a tissue at specified frequencies.

    Uses IT'IS V5.0 database with Cole-Cole calculation (preferred),
    with fallback to JSON cache if DB unavailable.

    Args:
        tissue_name: Name of tissue (IT'IS database name)
        frequencies_mhz: List of frequencies in MHz
        use_db: If True, try DB first; if False, use cache only

    Returns:
        List of dicts with {'eps_r': float, 'sigma': float} for each frequency

    Raises:
        KeyError: If tissue not found
        ValueError: If frequency not available (cache mode only)
    """
    if use_db:
        try:
            return _get_from_db(tissue_name, frequencies_mhz)
        except FileNotFoundError:
            logger.warning(
                "IT'IS database not found, falling back to JSON cache. "
                "For full frequency support, run: git lfs pull --include='data/itis_v5.db' "
                "or 'goliat init'"
            )
            return _get_from_cache(tissue_name, frequencies_mhz)
    else:
        return _get_from_cache(tissue_name, frequencies_mhz)


def load_material_cache(cache_path: Optional[Path] = None) -> dict:
    """
    Load material property cache from JSON file.

    Kept for backward compatibility. Prefer get_material_properties() for new code.
    """
    return _load_json_cache(cache_path)


def clear_cache() -> None:
    """Clear all in-memory caches to force reload on next access."""
    global _db_gabriel_params, _json_cache
    _db_gabriel_params = None
    _json_cache = None


def get_available_tissues(use_db: bool = True) -> list[str]:
    """Get list of all available tissue names."""
    if use_db:
        try:
            params = _load_db_params()
            return list(params.keys())
        except FileNotFoundError:
            pass

    cache = _load_json_cache()
    return list(cache.get("tissues", {}).keys())


def get_cole_cole_params(tissue_name: str) -> tuple:
    """
    Get raw Cole-Cole parameters for a tissue.

    Returns:
        Tuple of (ef, poles, sigma_ionic) where poles is list of (delta, tau_s, alpha)

    Raises:
        KeyError: If tissue not found
    """
    params = _load_db_params()

    if tissue_name not in params:
        raise KeyError(f"Tissue '{tissue_name}' not found in database")

    return params[tissue_name]
