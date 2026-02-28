"""
Compute skin depth (penetration depth) for biological tissues at all frequencies.

The skin depth (δ) is the depth at which the electric field amplitude decays to 1/e (≈37%)
of its surface value. This is critical for understanding:
1. Why S_ab is used above 6 GHz instead of SAR (energy confined to surface)
2. How many FDTD cells resolve the penetration depth (accuracy)
3. The transition from volumetric to surface absorption

Formula for lossy dielectric:
    α = ω√(με'/2) × √(√(1 + tan²δ) - 1)
    δ = 1/α

where tan δ = ε''/ε' = σ/(ωε₀εᵣ)
"""

import json
import numpy as np
from pathlib import Path

# Constants
C = 299792458  # Speed of light (m/s)
MU_0 = 4 * np.pi * 1e-7  # Permeability of free space (H/m)
EPS_0 = 8.854187817e-12  # Permittivity of free space (F/m)


def calculate_penetration_depth(freq_mhz: float, eps_r: float, sigma: float) -> float:
    """
    Calculate penetration depth (skin depth) for a lossy dielectric.
    
    Args:
        freq_mhz: Frequency in MHz
        eps_r: Relative permittivity
        sigma: Conductivity in S/m
    
    Returns:
        delta: skin depth in mm (field decays to 1/e = 37%)
    """
    omega = 2 * np.pi * freq_mhz * 1e6  # Angular frequency (rad/s)
    
    # Complex permittivity approach
    eps_prime = EPS_0 * eps_r
    eps_double_prime = sigma / omega
    
    # Loss tangent
    tan_delta = eps_double_prime / eps_prime
    
    # Attenuation constant (Np/m) - general formula for lossy dielectric
    alpha = omega * np.sqrt(MU_0 * eps_prime / 2) * np.sqrt(np.sqrt(1 + tan_delta**2) - 1)
    
    # Skin depth (m) - field decays to 1/e
    delta = 1 / alpha if alpha > 0 else np.inf
    
    return delta * 1000  # Convert to mm


def main():
    # Load material properties cache
    cache_path = Path(__file__).parent.parent.parent.parent / "data" / "material_properties_cache.json"
    with open(cache_path, 'r') as f:
        cache = json.load(f)
    
    # All frequencies
    frequencies = [450, 700, 835, 1450, 2140, 2450, 3500, 5200, 5800, 7000, 9000, 11000, 13000, 15000, 26000]
    
    # Grid sizes per frequency (mm)
    grid_sizes_mm = {
        450: 2.5, 700: 2.5, 835: 2.5, 1450: 2.5,
        2140: 1.694, 2450: 1.482, 3500: 1.0, 5200: 1.0, 5800: 1.0,
        7000: 0.6, 9000: 0.5, 11000: 0.5, 13000: 0.45, 15000: 0.4, 26000: 0.3
    }
    
    # Key tissue - Skin is most relevant for penetration depth discussion
    tissue = 'Skin'
    
    print("=" * 140)
    print("SKIN PENETRATION DEPTH (delta) - Field decays to 1/e ~ 37%")
    print("IT'IS Foundation Database V5.0 (4-Cole-Cole Gabriel model)")
    print("=" * 140)
    print()
    
    # Collect data
    skin_depths = []
    eps_values = []
    sigma_values = []
    
    for freq in frequencies:
        freq_str = str(freq)
        if freq_str in cache['tissues'][tissue]:
            eps_r = cache['tissues'][tissue][freq_str]['eps_r']
            sigma = cache['tissues'][tissue][freq_str]['sigma']
            delta = calculate_penetration_depth(freq, eps_r, sigma)
            skin_depths.append(delta)
            eps_values.append(eps_r)
            sigma_values.append(sigma)
        else:
            skin_depths.append(None)
            eps_values.append(None)
            sigma_values.append(None)
    
    # Print detailed table
    print(f"{'Freq [MHz]':>12}", end='')
    for freq in frequencies:
        print(f"{freq:>8}", end='')
    print()
    
    print(f"{'ε_r':>12}", end='')
    for eps in eps_values:
        if eps is not None:
            print(f"{eps:>8.1f}", end='')
        else:
            print(f"{'N/A':>8}", end='')
    print()
    
    print(f"{'σ [S/m]':>12}", end='')
    for sigma in sigma_values:
        if sigma is not None:
            print(f"{sigma:>8.2f}", end='')
        else:
            print(f"{'N/A':>8}", end='')
    print()
    
    print(f"{'δ [mm]':>12}", end='')
    for delta in skin_depths:
        if delta is not None:
            print(f"{delta:>8.1f}", end='')
        else:
            print(f"{'N/A':>8}", end='')
    print()
    
    print(f"{'Cell [mm]':>12}", end='')
    for freq in frequencies:
        print(f"{grid_sizes_mm[freq]:>8.2f}", end='')
    print()
    
    print(f"{'δ/cell':>12}", end='')
    for i, freq in enumerate(frequencies):
        if skin_depths[i] is not None:
            ratio = skin_depths[i] / grid_sizes_mm[freq]
            print(f"{ratio:>8.1f}", end='')
        else:
            print(f"{'N/A':>8}", end='')
    print()
    
    print()
    print("=" * 140)
    print("LaTeX TABLE ROW (for paper):")
    print("=" * 140)
    
    # Format for LaTeX - rounded to 1 decimal
    latex_values = []
    for d in skin_depths:
        if d is not None:
            if d >= 10:
                latex_values.append(f"{d:.0f}")
            else:
                latex_values.append(f"{d:.1f}")
        else:
            latex_values.append("---")
    
    print(r"\quad Skin & $\delta$ [mm]; penetration depth & " + " & ".join(latex_values) + r" \\")
    
    print()
    print("=" * 140)
    print("INTERPRETATION:")
    print("=" * 140)
    print()
    print("Key observations:")
    print(f"  - At 450 MHz: δ = {skin_depths[0]:.1f} mm (deep penetration, whole-body SAR relevant)")
    print(f"  - At 6 GHz:   δ ≈ {skin_depths[8]:.1f} mm (transition frequency for SAR → S_ab)")
    print(f"  - At 26 GHz:  δ = {skin_depths[14]:.1f} mm (very superficial, S_ab appropriate)")
    print()
    print("The δ/cell ratio shows how many FDTD cells resolve the penetration depth:")
    print("  - Values > 3-5 ensure accurate modeling of the exponential decay")
    print("  - At high frequencies, smaller cells are needed to maintain accuracy")
    print()
    print("This explains why:")
    print("  1. S_ab (surface absorbed power density) is used above 6 GHz")
    print("  2. Finer grids are required at higher frequencies")
    print("  3. Energy deposition at 26 GHz is confined to superficial tissues")


if __name__ == "__main__":
    main()
