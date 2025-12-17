"""
Generate material properties cache from IT'IS V5.0 SQLite database.

This script reads the Gabriel 4-Cole-Cole dispersion parameters from the IT'IS
Foundation database and calculates eps_r and sigma at multiple frequencies.

Usage:
    python scripts/generate_material_cache_from_db.py

Output:
    data/material_properties_cache.json
"""

import json
import sqlite3
import numpy as np
from datetime import datetime
from pathlib import Path

# Configuration
FREQUENCIES_MHZ = [450, 700, 835, 1450, 2140, 2450, 3500, 5200, 5800]
DB_PATH = Path(__file__).parent.parent / "data" / "itis_v5.db"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "material_properties_cache.json"

# Physical constants
EPS_0 = 8.854187817e-12  # Vacuum permittivity (F/m)

# Gabriel Parameters property ID in the database
GABRIEL_PROP_ID = "37f803e4-fc61-4b2b-9a41-39bd6569eb28"


def cole_cole_complex_permittivity(f_hz: float, ef: float, poles: list) -> complex:
    """
    Calculate complex permittivity using 4-Cole-Cole model.

    ε*(ω) = ε∞ + Σ(Δεₙ / (1 + (jωτₙ)^(1-αₙ)))

    Args:
        f_hz: Frequency in Hz
        ef: Epsilon infinity (high-frequency limit)
        poles: List of (delta_eps, tau_s, alpha) tuples for each Cole-Cole pole

    Returns:
        Complex permittivity (without ionic conductivity contribution)
    """
    omega = 2 * np.pi * f_hz
    eps_complex = ef + 0j

    for delta_eps, tau, alpha in poles:
        if delta_eps != 0 and tau != 0 and alpha < 1:
            eps_complex += delta_eps / (1 + (1j * omega * tau) ** (1 - alpha))

    return eps_complex


def calculate_eps_sigma(f_hz: float, ef: float, poles: list, sigma_ionic: float) -> tuple:
    """
    Calculate relative permittivity and conductivity at a given frequency.

    Args:
        f_hz: Frequency in Hz
        ef: Epsilon infinity
        poles: List of Cole-Cole poles [(delta_eps, tau_s, alpha), ...]
        sigma_ionic: Ionic (DC) conductivity in S/m

    Returns:
        Tuple of (eps_r, sigma) - relative permittivity and total conductivity
    """
    omega = 2 * np.pi * f_hz
    eps_complex = cole_cole_complex_permittivity(f_hz, ef, poles)

    # Add ionic conductivity contribution to imaginary part
    eps_complex -= 1j * sigma_ionic / (omega * EPS_0)

    # Extract real permittivity and effective conductivity
    eps_r = float(np.real(eps_complex))
    sigma = float(-omega * EPS_0 * np.imag(eps_complex))

    return eps_r, sigma


def parse_gabriel_params(blob: bytes) -> tuple:
    """
    Parse Gabriel 4-Cole-Cole parameters from database BLOB.

    Format (14 float64 values):
    [ef, del1, tau1_ps, alf1, del2, tau2_ns, alf2, del3, tau3_us, alf3, del4, tau4_ms, alf4, sigma]

    Returns:
        Tuple of (ef, poles, sigma_ionic) where poles is a list of (delta, tau_s, alpha)
    """
    arr = np.frombuffer(blob, dtype=np.float64)

    if len(arr) != 14:
        return None, None, None

    ef = arr[0]
    sigma_ionic = arr[13]

    # Convert time constants to seconds
    # tau1 is in picoseconds, tau2 in nanoseconds, tau3 in microseconds, tau4 in milliseconds
    poles = [
        (arr[1], arr[2] * 1e-12, arr[3]),  # del1, tau1_ps -> s, alf1
        (arr[4], arr[5] * 1e-9, arr[6]),  # del2, tau2_ns -> s, alf2
        (arr[7], arr[8] * 1e-6, arr[9]),  # del3, tau3_us -> s, alf3
        (arr[10], arr[11] * 1e-3, arr[12]),  # del4, tau4_ms -> s, alf4
    ]

    return ef, poles, sigma_ionic


def generate_cache() -> dict:
    """Generate the material properties cache from IT'IS database."""
    print("=" * 60)
    print("Generating material properties cache from IT'IS V5.0 Database")
    print(f"Source: {DB_PATH}")
    print(f"Frequencies: {FREQUENCIES_MHZ} MHz")
    print("=" * 60)

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Please ensure data/itis_v5.db is in the project root.")

    # Connect to database
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Get all materials with Gabriel parameters
    cursor.execute(
        """
        SELECT m.name, v.vals
        FROM vectors v
        JOIN materials m ON v.mat_id = m.mat_id
        WHERE v.prop_id = ?
        """,
        (GABRIEL_PROP_ID,),
    )

    results = cursor.fetchall()
    conn.close()

    print(f"Found {len(results)} materials with Gabriel parameters")

    cache = {
        "source": "IT'IS Foundation Database V5.0 (4-Cole-Cole Gabriel model)",
        "database": DB_PATH.name,
        "generated": datetime.now().isoformat(),
        "frequencies_mhz": FREQUENCIES_MHZ,
        "model": "4-pole Cole-Cole",
        "tissues": {},
    }

    tissues_processed = 0
    tissues_failed = 0

    for name, blob in results:
        ef, poles, sigma_ionic = parse_gabriel_params(blob)

        if ef is None:
            tissues_failed += 1
            continue

        # Check if air/vacuum (all deltas zero)
        is_air = all(p[0] == 0 for p in poles)

        if is_air:
            # Air: eps_r = ef (usually 1), sigma = 0
            tissue_data = {str(f): {"eps_r": float(ef), "sigma": 0.0} for f in FREQUENCIES_MHZ}
        else:
            # Calculate properties at each frequency
            tissue_data = {}
            for freq_mhz in FREQUENCIES_MHZ:
                f_hz = freq_mhz * 1e6
                eps_r, sigma = calculate_eps_sigma(f_hz, ef, poles, sigma_ionic)
                tissue_data[str(freq_mhz)] = {"eps_r": eps_r, "sigma": sigma}

        cache["tissues"][name] = tissue_data
        tissues_processed += 1

    print(f"Processed {tissues_processed} tissues, {tissues_failed} failed")

    return cache


def verify_against_mapping(cache: dict) -> bool:
    """Verify cache contains all materials needed by phantoms."""
    mapping_path = OUTPUT_PATH.parent / "material_name_mapping.json"

    if not mapping_path.exists():
        print("Warning: material_name_mapping.json not found, skipping verification")
        return True

    with open(mapping_path, encoding="utf-8") as f:
        mapping = json.load(f)

    cache_tissues = set(cache["tissues"].keys())

    print("\n" + "=" * 60)
    print("Verifying against material_name_mapping.json")
    print("=" * 60)

    all_ok = True
    total_mappings = 0

    for phantom in mapping:
        tissue_map = mapping[phantom]
        missing = []

        for entity_name, itis_name in tissue_map.items():
            if entity_name.startswith("_"):  # Skip _tissue_groups
                continue
            total_mappings += 1
            if itis_name not in cache_tissues:
                missing.append((entity_name, itis_name))

        if missing:
            all_ok = False
            print(f"{phantom}: MISSING {len(missing)} materials")
            for entity, itis in missing[:5]:
                print(f"    {entity} -> {itis}")
            if len(missing) > 5:
                print(f"    ... and {len(missing) - 5} more")
        else:
            count = len([k for k in tissue_map if not k.startswith("_")])
            print(f"{phantom}: All {count} mappings OK ✓")

    print(f"\nTotal mappings verified: {total_mappings}")

    return all_ok


def save_cache(cache: dict) -> None:
    """Save cache to JSON file."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

    print(f"\nCache saved to: {OUTPUT_PATH}")
    print(f"Total tissues: {len(cache['tissues'])}")


def main():
    try:
        cache = generate_cache()
        save_cache(cache)

        # Verify all needed materials are present
        verify_against_mapping(cache)

        # Show sample values
        print("\n" + "=" * 60)
        print("Sample values for validation (compare with Sim4Life GUI)")
        print("=" * 60)

        test_tissues = [
            ("Brain (Grey Matter)", "700"),
            ("Muscle", "2450"),
            ("Skin", "835"),
            ("Fat", "5800"),
            ("Bone (Cortical)", "450"),
        ]

        for tissue, freq in test_tissues:
            if tissue in cache["tissues"]:
                d = cache["tissues"][tissue][freq]
                print(f"{tissue} @ {freq} MHz:")
                print(f"    ε_r = {d['eps_r']:.4f}")
                print(f"    σ   = {d['sigma']:.4f} S/m")

        print("\n✓ Cache generation complete!")

    except Exception as e:
        print(f"\nERROR: {e}")
        raise


if __name__ == "__main__":
    main()
