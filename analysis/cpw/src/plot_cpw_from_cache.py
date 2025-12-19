"""
Plot Required Cell Size for CPW=10 as a function of frequency for all tissues.

For FDTD simulations, we typically want CPW = 10 (10 cells per wavelength).
This script computes the required cell size (grid resolution) in mm to achieve
CPW = 10 for each tissue at each frequency.

Cell Size = wavelength_in_material / CPW
          = c / (f * sqrt(eps_r)) / 10

This script reads material properties from data/material_properties_cache.json
and creates a visualization of required cell size vs frequency for all tissues.

For higher frequencies (7-26 GHz), simple linear extrapolation is used based on
the trend from 3500-5800 MHz data.
"""

import json
import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Constants
C = 299792458  # Speed of light in m/s
CPW_TARGET = 10  # Target cells per wavelength
MAX_CELL_SIZE_MM = 3.0  # Focus on cell sizes up to 3 mm (above is always fine)

# Additional frequencies to extrapolate to (in MHz)
EXTRAPOLATE_FREQS_MHZ = [7000, 8000, 9000, 10000, 11000, 12000, 15000, 18000, 26000]


def load_material_cache(cache_path: str) -> dict:
    """Load the material properties cache from JSON file."""
    with open(cache_path, "r") as f:
        return json.load(f)


def calculate_wavelength_in_material(frequency_hz: float, eps_r: float) -> float:
    """
    Calculate wavelength in material.
    
    λ_material = c / (f * sqrt(eps_r))
    """
    return C / (frequency_hz * np.sqrt(eps_r))


def calculate_cell_size_for_cpw(wavelength_m: float, cpw: int = CPW_TARGET) -> float:
    """
    Calculate required cell size to achieve target CPW.
    
    cell_size = wavelength / CPW
    """
    return wavelength_m / cpw


def linear_extrapolate(freqs_mhz: list, values: list, target_freq_mhz: float) -> float:
    """
    Simple linear extrapolation based on last two data points.
    Uses data from 3500 MHz onwards for more stable extrapolation.
    """
    # Filter to use only high-frequency data (3500+ MHz) for extrapolation
    high_freq_data = [(f, v) for f, v in zip(freqs_mhz, values) if f >= 3500]
    
    if len(high_freq_data) < 2:
        # Fallback to last two points if not enough high-freq data
        high_freq_data = list(zip(freqs_mhz[-2:], values[-2:]))
    
    # Use linear regression on high-freq data
    x = np.array([d[0] for d in high_freq_data])
    y = np.array([d[1] for d in high_freq_data])
    
    # Linear fit: y = mx + b
    slope = (y[-1] - y[0]) / (x[-1] - x[0]) if x[-1] != x[0] else 0
    intercept = y[-1] - slope * x[-1]
    
    extrapolated = slope * target_freq_mhz + intercept
    
    # Ensure physical constraints
    # eps_r should be >= 1 (vacuum), sigma should be >= 0
    return max(extrapolated, 1.0 if extrapolated > 0 else 0.0)


def extrapolate_properties(freq_properties: dict) -> dict:
    """
    Extrapolate material properties to higher frequencies using linear extrapolation.
    """
    # Get existing frequencies and values
    freqs_mhz = sorted([float(f) for f in freq_properties.keys()])
    eps_r_values = [freq_properties[str(int(f))]["eps_r"] for f in freqs_mhz]
    sigma_values = [freq_properties[str(int(f))]["sigma"] for f in freqs_mhz]
    
    # Create extended properties dict
    extended_props = dict(freq_properties)
    
    for target_freq in EXTRAPOLATE_FREQS_MHZ:
        if target_freq not in freqs_mhz:
            # Extrapolate eps_r (ensure >= 1)
            eps_r_extrap = linear_extrapolate(freqs_mhz, eps_r_values, target_freq)
            eps_r_extrap = max(eps_r_extrap, 1.0)
            
            # Extrapolate sigma (ensure >= 0)
            sigma_extrap = linear_extrapolate(freqs_mhz, sigma_values, target_freq)
            sigma_extrap = max(sigma_extrap, 0.0)
            
            extended_props[str(target_freq)] = {
                "eps_r": eps_r_extrap,
                "sigma": sigma_extrap,
                "extrapolated": True
            }
    
    return extended_props


def process_material_data(cache_data: dict) -> dict:
    """
    Process material cache data to compute required cell size for CPW=10 
    for each tissue at each frequency, including extrapolated frequencies.
    
    Returns a dictionary with tissue names as keys and lists of 
    (frequency_mhz, cell_size_mm, eps_r, is_extrapolated) tuples.
    """
    tissues_data = {}
    
    for tissue_name, freq_properties in cache_data.get("tissues", {}).items():
        # Extrapolate to higher frequencies
        extended_props = extrapolate_properties(freq_properties)
        
        tissue_cell_data = []
        
        for freq_str, properties in extended_props.items():
            freq_mhz = float(freq_str)
            freq_hz = freq_mhz * 1e6
            eps_r = properties.get("eps_r", 1.0)
            is_extrapolated = properties.get("extrapolated", False)
            
            wavelength_m = calculate_wavelength_in_material(freq_hz, eps_r)
            cell_size_m = calculate_cell_size_for_cpw(wavelength_m, CPW_TARGET)
            cell_size_mm = cell_size_m * 1000  # Convert to mm
            
            tissue_cell_data.append((freq_mhz, cell_size_mm, eps_r, is_extrapolated))
        
        # Sort by frequency
        tissue_cell_data.sort(key=lambda x: x[0])
        tissues_data[tissue_name] = tissue_cell_data
    
    return tissues_data


def plot_cell_size_vs_frequency(tissues_data: dict, output_dir: str):
    """
    Create plots of required cell size (for CPW=10) vs frequency.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all frequencies for x-axis limits
    all_freqs = set()
    for data in tissues_data.values():
        for d in data:
            all_freqs.add(d[0])
    max_freq = max(all_freqs)
    
    # Determine y-axis limit based on smallest cell sizes
    min_cell = min(d[1] for data in tissues_data.values() for d in data)
    # Round down to nearest 0.05
    y_min = max(0, np.floor(min_cell * 20) / 20 - 0.05)
    
    # --- Plot 1: All tissues overview ---
    fig, ax = plt.subplots(figsize=(16, 10))
    
    for tissue_name, data in tissues_data.items():
        frequencies = [d[0] for d in data]
        cell_sizes = [d[1] for d in data]
        is_extrap = [d[3] for d in data]
        
        # Split into measured and extrapolated
        meas_f = [f for f, e in zip(frequencies, is_extrap) if not e]
        meas_c = [c for c, e in zip(cell_sizes, is_extrap) if not e]
        ext_f = [f for f, e in zip(frequencies, is_extrap) if e]
        ext_c = [c for c, e in zip(cell_sizes, is_extrap) if e]
        
        line, = ax.plot(meas_f, meas_c, marker='o', markersize=3, alpha=0.6, linewidth=1)
        if ext_f:
            ax.plot(ext_f, ext_c, marker='s', markersize=3, alpha=0.4, linewidth=1, 
                   linestyle='--', color=line.get_color())
    
    ax.set_xlabel("Frequency (MHz)", fontsize=12)
    ax.set_ylabel("Required Cell Size (mm) for CPW=10", fontsize=12)
    ax.set_title(f"Required Cell Size for CPW={CPW_TARGET} vs Frequency (All Tissues)\nDashed = Extrapolated", fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, max_freq * 1.05)
    ax.set_ylim(y_min, MAX_CELL_SIZE_MM)
    
    # Add vertical lines for key frequencies
    for freq in [6000, 10000, 18000, 26000]:
        ax.axvline(x=freq, color='gray', linestyle=':', alpha=0.5)
    
    plt.tight_layout()
    output_path = os.path.join(output_dir, "cell_size_vs_freq_all_tissues.png")
    plt.savefig(output_path, dpi=150)
    print(f"Saved: {output_path}")
    plt.close()
    
    # --- Plot 2: Cell size at highest frequency (most demanding) sorted ---
    fig, ax = plt.subplots(figsize=(16, 16))
    
    # Get cell size at highest frequency for each tissue
    tissue_cell_at_max_freq = []
    for tissue_name, data in tissues_data.items():
        max_freq_data = max(data, key=lambda x: x[0])
        tissue_cell_at_max_freq.append((tissue_name, max_freq_data[1], max_freq_data[0], max_freq_data[2]))
    
    # Sort by cell size (ascending - smallest cell = finest grid needed)
    tissue_cell_at_max_freq.sort(key=lambda x: x[1])
    
    # Filter to only show tissues with cell size < MAX_CELL_SIZE_MM
    tissue_cell_at_max_freq = [t for t in tissue_cell_at_max_freq if t[1] <= MAX_CELL_SIZE_MM]
    
    tissue_names = [t[0] for t in tissue_cell_at_max_freq]
    cell_sizes = [t[1] for t in tissue_cell_at_max_freq]
    eps_values = [t[3] for t in tissue_cell_at_max_freq]
    freq_value = tissue_cell_at_max_freq[0][2] if tissue_cell_at_max_freq else 26000
    
    # Color by permittivity
    norm_eps = np.array(eps_values) / max(eps_values) if eps_values else [0]
    colors = plt.cm.viridis(norm_eps)
    
    ax.barh(range(len(tissue_names)), cell_sizes, color=colors)
    
    ax.set_yticks(range(len(tissue_names)))
    ax.set_yticklabels(tissue_names, fontsize=6)
    ax.set_xlabel(f"Required Cell Size (mm) for CPW={CPW_TARGET}", fontsize=12)
    ax.set_title(f"Required Cell Size at {int(freq_value/1000)} GHz (sorted, smallest = finest grid needed)\n[Extrapolated]", fontsize=14)
    ax.axvline(x=1.0, color='red', linestyle='--', linewidth=2, label='1 mm grid')
    ax.axvline(x=0.5, color='orange', linestyle='--', linewidth=2, label='0.5 mm grid')
    ax.axvline(x=0.25, color='yellow', linestyle='--', linewidth=2, label='0.25 mm grid')
    ax.axvline(x=0.1, color='green', linestyle='--', linewidth=2, label='0.1 mm grid')
    ax.set_xlim(0, MAX_CELL_SIZE_MM)
    ax.legend(loc='lower right')
    ax.grid(True, axis='x', alpha=0.3)
    
    # Add colorbar for permittivity
    if eps_values:
        sm = plt.cm.ScalarMappable(cmap='viridis', norm=plt.Normalize(vmin=min(eps_values), vmax=max(eps_values)))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, label='Relative Permittivity (εr) [extrapolated]')
    
    plt.tight_layout()
    output_path = os.path.join(output_dir, f"cell_size_at_{int(freq_value/1000)}GHz_sorted.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {output_path}")
    plt.close()
    
    # --- Plot 3: Selected critical tissues (smallest cell size needed) ---
    fig, ax = plt.subplots(figsize=(16, 10))
    
    # Find minimum cell size per tissue (at highest frequency, highest permittivity)
    min_cell_per_tissue = [(name, min(d[1] for d in data)) for name, data in tissues_data.items()]
    min_cell_per_tissue.sort(key=lambda x: x[1])
    
    # Take top 20 most critical tissues (need finest grid)
    critical_tissues = [t[0] for t in min_cell_per_tissue[:20]]
    
    colors = plt.cm.tab20(np.linspace(0, 1, len(critical_tissues)))
    
    for i, tissue_name in enumerate(critical_tissues):
        data = tissues_data[tissue_name]
        frequencies = [d[0] for d in data]
        cell_sizes = [d[1] for d in data]
        is_extrap = [d[3] for d in data]
        
        # Split into measured and extrapolated
        meas_f = [f for f, e in zip(frequencies, is_extrap) if not e]
        meas_c = [c for c, e in zip(cell_sizes, is_extrap) if not e]
        ext_f = [f for f, e in zip(frequencies, is_extrap) if e]
        ext_c = [c for c, e in zip(cell_sizes, is_extrap) if e]
        
        ax.plot(meas_f, meas_c, marker='o', markersize=5, 
                label=tissue_name, color=colors[i], linewidth=2)
        if ext_f:
            ax.plot(ext_f, ext_c, marker='s', markersize=4, 
                   color=colors[i], linewidth=1.5, linestyle='--', alpha=0.7)
    
    ax.axhline(y=1.0, color='red', linestyle='--', linewidth=2, label='1 mm grid')
    ax.axhline(y=0.5, color='orange', linestyle='--', linewidth=2, label='0.5 mm grid')
    ax.axhline(y=0.25, color='yellow', linestyle='--', linewidth=2, label='0.25 mm grid')
    ax.axhline(y=0.1, color='green', linestyle='--', linewidth=2, label='0.1 mm grid')
    ax.set_xlabel("Frequency (MHz)", fontsize=12)
    ax.set_ylabel(f"Required Cell Size (mm) for CPW={CPW_TARGET}", fontsize=12)
    ax.set_title(f"Required Cell Size for CPW={CPW_TARGET} - Most Critical Tissues\nSolid = Measured, Dashed = Extrapolated", fontsize=14)
    ax.legend(loc='upper right', fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, max_freq * 1.05)
    ax.set_ylim(y_min, MAX_CELL_SIZE_MM)
    
    plt.tight_layout()
    output_path = os.path.join(output_dir, "cell_size_vs_freq_critical_tissues.png")
    plt.savefig(output_path, dpi=150)
    print(f"Saved: {output_path}")
    plt.close()
    
    # --- Plot 4: Heatmap of cell size (tissue vs frequency) ---
    fig, ax = plt.subplots(figsize=(18, 24))
    
    # Sort tissues by minimum cell size
    sorted_tissues = [t[0] for t in min_cell_per_tissue]
    frequencies_sorted = sorted(set(d[0] for data in tissues_data.values() for d in data))
    
    # Create matrix
    cell_matrix = np.zeros((len(sorted_tissues), len(frequencies_sorted)))
    
    for i, tissue_name in enumerate(sorted_tissues):
        data = tissues_data.get(tissue_name, [])
        freq_to_cell = {d[0]: d[1] for d in data}
        for j, freq in enumerate(frequencies_sorted):
            cell_matrix[i, j] = freq_to_cell.get(freq, np.nan)
    
    # Create heatmap (red = small cell size = critical)
    im = ax.imshow(cell_matrix, aspect='auto', cmap='RdYlGn', vmin=0.1, vmax=MAX_CELL_SIZE_MM)
    
    ax.set_xticks(range(len(frequencies_sorted)))
    freq_labels = [f"{int(f/1000)}G" if f >= 1000 else f"{int(f)}" for f in frequencies_sorted]
    ax.set_xticklabels(freq_labels, fontsize=9, rotation=45)
    ax.set_yticks(range(len(sorted_tissues)))
    ax.set_yticklabels(sorted_tissues, fontsize=6)
    
    ax.set_xlabel("Frequency", fontsize=12)
    ax.set_ylabel("Tissue", fontsize=12)
    ax.set_title(f"Required Cell Size (mm) for CPW={CPW_TARGET} - Red = Fine grid needed", fontsize=14)
    
    cbar = plt.colorbar(im, ax=ax, label='Required Cell Size (mm)')
    
    plt.tight_layout()
    output_path = os.path.join(output_dir, "cell_size_heatmap.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {output_path}")
    plt.close()
    
    # --- Plot 5: Minimum cell size across all frequencies per tissue (at 26 GHz) ---
    fig, ax = plt.subplots(figsize=(16, 16))
    
    # Filter to only show tissues with cell size < MAX_CELL_SIZE_MM
    min_cell_per_tissue_filtered = [t for t in min_cell_per_tissue if t[1] <= MAX_CELL_SIZE_MM]
    
    tissue_names = [t[0] for t in min_cell_per_tissue_filtered]
    min_cells = [t[1] for t in min_cell_per_tissue_filtered]
    
    # Find at which frequency the minimum occurs
    min_freq_per_tissue = []
    for tissue_name, _ in min_cell_per_tissue_filtered:
        data = tissues_data[tissue_name]
        min_data = min(data, key=lambda x: x[1])
        min_freq_per_tissue.append(min_data[0])  # frequency
    
    # Color by frequency
    freq_colors = plt.cm.plasma(np.array(min_freq_per_tissue) / max(min_freq_per_tissue))
    
    ax.barh(range(len(tissue_names)), min_cells, color=freq_colors)
    
    ax.set_yticks(range(len(tissue_names)))
    ax.set_yticklabels(tissue_names, fontsize=6)
    ax.set_xlabel(f"Minimum Required Cell Size (mm) for CPW={CPW_TARGET}", fontsize=12)
    ax.set_title("Minimum Required Cell Size (at highest frequency = 26 GHz, extrapolated)", fontsize=14)
    ax.axvline(x=1.0, color='red', linestyle='--', linewidth=2, label='1 mm grid')
    ax.axvline(x=0.5, color='orange', linestyle='--', linewidth=2, label='0.5 mm grid')
    ax.axvline(x=0.25, color='yellow', linestyle='--', linewidth=2, label='0.25 mm grid')
    ax.axvline(x=0.1, color='green', linestyle='--', linewidth=2, label='0.1 mm grid')
    ax.set_xlim(0, MAX_CELL_SIZE_MM)
    ax.legend(loc='lower right')
    ax.grid(True, axis='x', alpha=0.3)
    
    # Add colorbar for frequency
    sm = plt.cm.ScalarMappable(cmap='plasma', norm=plt.Normalize(vmin=min(min_freq_per_tissue), vmax=max(min_freq_per_tissue)))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, label='Frequency at minimum (MHz)')
    
    plt.tight_layout()
    output_path = os.path.join(output_dir, "min_cell_size_all_freq.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {output_path}")
    plt.close()
    
    # --- Plot 6: Zoomed in view for very small cell sizes (<0.5mm) ---
    fig, ax = plt.subplots(figsize=(16, 10))
    
    # Filter tissues that need < 0.5mm cells
    very_critical = [(name, min(d[1] for d in data)) for name, data in tissues_data.items() 
                     if min(d[1] for d in data) < 0.5]
    very_critical.sort(key=lambda x: x[1])
    
    if very_critical:
        very_critical_tissues = [t[0] for t in very_critical[:15]]
        colors = plt.cm.tab20(np.linspace(0, 1, len(very_critical_tissues)))
        
        for i, tissue_name in enumerate(very_critical_tissues):
            data = tissues_data[tissue_name]
            frequencies = [d[0] for d in data]
            cell_sizes = [d[1] for d in data]
            is_extrap = [d[3] for d in data]
            
            meas_f = [f for f, e in zip(frequencies, is_extrap) if not e]
            meas_c = [c for c, e in zip(cell_sizes, is_extrap) if not e]
            ext_f = [f for f, e in zip(frequencies, is_extrap) if e]
            ext_c = [c for c, e in zip(cell_sizes, is_extrap) if e]
            
            ax.plot(meas_f, meas_c, marker='o', markersize=6, 
                    label=tissue_name, color=colors[i], linewidth=2)
            if ext_f:
                ax.plot(ext_f, ext_c, marker='s', markersize=5, 
                       color=colors[i], linewidth=1.5, linestyle='--', alpha=0.7)
        
        ax.axhline(y=0.5, color='orange', linestyle='--', linewidth=2, label='0.5 mm')
        ax.axhline(y=0.25, color='yellow', linestyle='--', linewidth=2, label='0.25 mm')
        ax.axhline(y=0.1, color='green', linestyle='--', linewidth=2, label='0.1 mm')
        ax.axhline(y=0.05, color='cyan', linestyle='--', linewidth=2, label='0.05 mm')
        ax.set_xlabel("Frequency (MHz)", fontsize=12)
        ax.set_ylabel(f"Required Cell Size (mm) for CPW={CPW_TARGET}", fontsize=12)
        ax.set_title(f"Tissues Requiring Very Fine Grid (<0.5mm) for CPW={CPW_TARGET}\nSolid = Measured, Dashed = Extrapolated", fontsize=14)
        ax.legend(loc='upper right', fontsize=8, ncol=2)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, max_freq * 1.05)
        ax.set_ylim(0, 0.6)
        
        plt.tight_layout()
        output_path = os.path.join(output_dir, "cell_size_very_critical_zoomed.png")
        plt.savefig(output_path, dpi=150)
        print(f"Saved: {output_path}")
        plt.close()
    else:
        print("No tissues require < 0.5mm cells, skipping zoomed plot")


def print_summary(tissues_data: dict):
    """Print a summary of critical tissues and their required cell sizes."""
    print("\n" + "="*80)
    print(f"Required Cell Size for CPW = {CPW_TARGET}")
    print(f"Frequencies: measured (450-5800 MHz) + extrapolated ({', '.join(str(f//1000)+'G' for f in EXTRAPOLATE_FREQS_MHZ)})")
    print("="*80)
    
    # Find minimum cell size per tissue (most demanding)
    min_cell_per_tissue = []
    for tissue_name, data in tissues_data.items():
        min_data = min(data, key=lambda x: x[1])
        min_cell_per_tissue.append((tissue_name, min_data[1], min_data[0], min_data[2], min_data[3]))
    
    # Sort by cell size (smallest first = most critical)
    min_cell_per_tissue.sort(key=lambda x: x[1])
    
    print(f"\nTissues requiring cell size < 0.5 mm at 26 GHz (for CPW=10):")
    print("-"*80)
    
    critical_count = 0
    for tissue, cell_mm, freq, eps_r, is_extrap in min_cell_per_tissue:
        if cell_mm < 0.5:
            critical_count += 1
            extrap_marker = " [E]" if is_extrap else ""
            print(f"  {tissue:40s} | {cell_mm:5.3f} mm @ {int(freq/1000):2d} GHz | εr = {eps_r:.1f}{extrap_marker}")
    
    if critical_count == 0:
        print("  None - all tissues can use 0.5 mm grid or coarser")
    
    print(f"\n{critical_count} tissues require cell size < 0.5 mm.")
    
    print(f"\nTissues requiring cell size < 0.25 mm (extreme resolution):")
    print("-"*80)
    
    extreme_count = 0
    for tissue, cell_mm, freq, eps_r, is_extrap in min_cell_per_tissue:
        if cell_mm < 0.25:
            extreme_count += 1
            extrap_marker = " [E]" if is_extrap else ""
            print(f"  {tissue:40s} | {cell_mm:5.3f} mm @ {int(freq/1000):2d} GHz | εr = {eps_r:.1f}{extrap_marker}")
    
    if extreme_count == 0:
        print("  None")
    
    print("="*80 + "\n")


def main():
    # Get paths relative to script location
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent  # goliat/
    
    cache_path = project_root / "data" / "material_properties_cache.json"
    output_dir = script_dir.parent / "plots"
    
    print(f"Loading material cache from: {cache_path}")
    
    if not cache_path.exists():
        print(f"ERROR: Material cache not found at {cache_path}")
        return
    
    # Load data
    cache_data = load_material_cache(str(cache_path))
    
    print(f"Source: {cache_data.get('source', 'Unknown')}")
    print(f"Original frequencies: {cache_data.get('frequencies_mhz', [])} MHz")
    print(f"Extrapolating to: {[f'{f//1000}G' for f in EXTRAPOLATE_FREQS_MHZ]}")
    print(f"Number of tissues: {len(cache_data.get('tissues', {}))}")
    print(f"Target CPW: {CPW_TARGET}")
    
    # Process data (includes extrapolation)
    tissues_data = process_material_data(cache_data)
    
    # Print summary
    print_summary(tissues_data)
    
    # Create plots
    print("\nGenerating plots...")
    plot_cell_size_vs_frequency(tissues_data, str(output_dir))
    
    print("\nDone!")


if __name__ == "__main__":
    main()
