"""
Comprehensive Analysis of Thelonious FR3 Simulation Results
============================================================
This script analyzes SAR results across multiple frequencies (7-26 GHz)
for the Thelonious phantom with environmental x_neg_theta exposure.

Includes:
- SAR metrics vs frequency plots
- Tissue-specific SAR analysis
- Spatial analysis of psSAR10g peak locations
- Performance and timing analysis
- Grid and solver statistics
"""

import json
import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import pandas as pd
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import FancyBboxPatch
import matplotlib.patches as mpatches

# Set up paths
BASE_PATH = Path("results/thelonious_FR3")
OUTPUT_PATH = Path("analysis/thelonious_FR3_plots")
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

# Frequencies to analyze
FREQUENCIES = [7000, 9000, 11000, 13000, 15000, 26000]

def load_all_data():
    """Load all SAR results and metadata for all frequencies."""
    data = {}
    
    for freq in FREQUENCIES:
        freq_path = BASE_PATH / f"{freq}MHz" / "environmental_x_neg_theta"
        
        # Load SAR results
        sar_file = freq_path / "sar_results.json"
        metadata_file = freq_path / "simulation_metadata.json"
        
        if sar_file.exists() and metadata_file.exists():
            with open(sar_file, 'r') as f:
                sar_data = json.load(f)
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            data[freq] = {
                'sar': sar_data,
                'metadata': metadata
            }
    
    return data

def create_dataframe(data):
    """Convert data to pandas DataFrame for easier analysis."""
    rows = []
    
    for freq, d in data.items():
        sar = d['sar']
        meta = d['metadata']
        
        row = {
            'frequency_mhz': freq,
            'frequency_ghz': freq / 1000,
            # SAR metrics
            'peak_sar_10g': sar['peak_sar_10g_W_kg'],
            'whole_body_sar': sar['whole_body_sar'],
            'input_power_w': sar['input_power_W'],
            # Tissue-specific SAR
            'eyes_avg_sar': sar['eyes_group_weighted_avg_sar'],
            'eyes_peak_sar': sar['eyes_group_peak_sar'],
            'skin_avg_sar': sar['skin_group_weighted_avg_sar'],
            'skin_peak_sar': sar['skin_group_peak_sar'],
            'brain_avg_sar': sar['brain_group_weighted_avg_sar'],
            'brain_peak_sar': sar['brain_group_peak_sar'],
            'genitals_avg_sar': sar['genitals_group_weighted_avg_sar'],
            # Peak location
            'peak_x': sar['peak_sar_details']['PeakLocation'][0],
            'peak_y': sar['peak_sar_details']['PeakLocation'][1],
            'peak_z': sar['peak_sar_details']['PeakLocation'][2],
            'peak_cube_side': sar['peak_sar_details']['PeakCubeSideLength'],
            # Performance
            'total_time_s': meta['total_study_time_s'],
            'solver_iterations': meta['solver']['iterations'],
            'total_cells': meta['grid']['total_cells'],
            'avg_mcells_per_s': meta['performance']['avg_mcells_per_s'],
            'peak_memory_gb': meta['hardware']['peak_memory_gb'],
            'grid_resolution_mm': meta['solver']['grid_resolution_mm'],
        }
        rows.append(row)
    
    return pd.DataFrame(rows).sort_values('frequency_mhz')

def plot_sar_vs_frequency(df):
    """Plot SAR metrics vs frequency."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Plot 1: Peak SAR 10g vs Frequency
    ax1 = axes[0, 0]
    ax1.plot(df['frequency_ghz'], df['peak_sar_10g'] * 1e6, 'bo-', linewidth=2, markersize=10)
    ax1.set_xlabel('Frequency (GHz)', fontsize=12)
    ax1.set_ylabel('Peak SAR 10g (µW/kg)', fontsize=12)
    ax1.set_title('Peak Spatial Average SAR (10g) vs Frequency', fontsize=14)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim([6, 27])
    
    # Plot 2: Whole Body SAR vs Frequency
    ax2 = axes[0, 1]
    ax2.plot(df['frequency_ghz'], df['whole_body_sar'] * 1e6, 'ro-', linewidth=2, markersize=10)
    ax2.set_xlabel('Frequency (GHz)', fontsize=12)
    ax2.set_ylabel('Whole Body SAR (µW/kg)', fontsize=12)
    ax2.set_title('Whole Body SAR vs Frequency', fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim([6, 27])
    
    # Plot 3: Tissue-specific Average SAR
    ax3 = axes[1, 0]
    ax3.semilogy(df['frequency_ghz'], df['eyes_avg_sar'] * 1e6, 's-', label='Eyes', linewidth=2, markersize=8)
    ax3.semilogy(df['frequency_ghz'], df['skin_avg_sar'] * 1e6, 'o-', label='Skin', linewidth=2, markersize=8)
    ax3.semilogy(df['frequency_ghz'], df['brain_avg_sar'] * 1e6, '^-', label='Brain', linewidth=2, markersize=8)
    ax3.semilogy(df['frequency_ghz'], df['genitals_avg_sar'] * 1e6, 'd-', label='Genitals', linewidth=2, markersize=8)
    ax3.set_xlabel('Frequency (GHz)', fontsize=12)
    ax3.set_ylabel('Average SAR (µW/kg)', fontsize=12)
    ax3.set_title('Tissue-Specific Average SAR vs Frequency', fontsize=14)
    ax3.legend(loc='best')
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim([6, 27])
    
    # Plot 4: Tissue-specific Peak SAR
    ax4 = axes[1, 1]
    ax4.plot(df['frequency_ghz'], df['eyes_peak_sar'] * 1e6, 's-', label='Eyes', linewidth=2, markersize=8)
    ax4.plot(df['frequency_ghz'], df['skin_peak_sar'] * 1e6, 'o-', label='Skin', linewidth=2, markersize=8)
    ax4.plot(df['frequency_ghz'], df['brain_peak_sar'] * 1e6, '^-', label='Brain', linewidth=2, markersize=8)
    ax4.set_xlabel('Frequency (GHz)', fontsize=12)
    ax4.set_ylabel('Peak SAR (µW/kg)', fontsize=12)
    ax4.set_title('Tissue-Specific Peak SAR vs Frequency', fontsize=14)
    ax4.legend(loc='best')
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim([6, 27])
    
    plt.tight_layout()
    plt.savefig(OUTPUT_PATH / 'sar_vs_frequency.png', dpi=150, bbox_inches='tight')
    plt.savefig(OUTPUT_PATH / 'sar_vs_frequency.pdf', bbox_inches='tight')
    print(f"Saved: {OUTPUT_PATH / 'sar_vs_frequency.png'}")
    return fig

def plot_spatial_analysis_psSAR10g(df):
    """Spatial analysis of psSAR10g peak locations."""
    fig = plt.figure(figsize=(16, 12))
    
    # 3D scatter plot of peak locations
    ax1 = fig.add_subplot(2, 2, 1, projection='3d')
    scatter = ax1.scatter(df['peak_x'] * 100, df['peak_y'] * 100, df['peak_z'] * 100, 
                         c=df['frequency_ghz'], cmap='viridis', s=200, alpha=0.8)
    ax1.set_xlabel('X (cm)', fontsize=11)
    ax1.set_ylabel('Y (cm)', fontsize=11)
    ax1.set_zlabel('Z (cm)', fontsize=11)
    ax1.set_title('3D Peak SAR 10g Locations\n(colored by frequency)', fontsize=13)
    cbar = plt.colorbar(scatter, ax=ax1, shrink=0.6, pad=0.1)
    cbar.set_label('Frequency (GHz)', fontsize=10)
    
    # Add frequency labels to points
    for i, row in df.iterrows():
        ax1.text(row['peak_x']*100, row['peak_y']*100, row['peak_z']*100, 
                f"  {row['frequency_ghz']:.0f}G", fontsize=8)
    
    # X-Z projection (sagittal view)
    ax2 = fig.add_subplot(2, 2, 2)
    scatter2 = ax2.scatter(df['peak_x'] * 100, df['peak_z'] * 100, 
                          c=df['frequency_ghz'], cmap='viridis', s=200, alpha=0.8)
    ax2.set_xlabel('X (cm) - Anterior-Posterior', fontsize=11)
    ax2.set_ylabel('Z (cm) - Superior-Inferior', fontsize=11)
    ax2.set_title('Peak SAR Locations (Sagittal View)', fontsize=13)
    for i, row in df.iterrows():
        ax2.annotate(f"{row['frequency_ghz']:.0f}G", 
                    (row['peak_x']*100, row['peak_z']*100),
                    xytext=(5, 5), textcoords='offset points', fontsize=9)
    ax2.grid(True, alpha=0.3)
    plt.colorbar(scatter2, ax=ax2, label='Frequency (GHz)')
    
    # X-Y projection (axial view)
    ax3 = fig.add_subplot(2, 2, 3)
    scatter3 = ax3.scatter(df['peak_x'] * 100, df['peak_y'] * 100, 
                          c=df['frequency_ghz'], cmap='viridis', s=200, alpha=0.8)
    ax3.set_xlabel('X (cm) - Anterior-Posterior', fontsize=11)
    ax3.set_ylabel('Y (cm) - Left-Right', fontsize=11)
    ax3.set_title('Peak SAR Locations (Axial View)', fontsize=13)
    for i, row in df.iterrows():
        ax3.annotate(f"{row['frequency_ghz']:.0f}G", 
                    (row['peak_x']*100, row['peak_y']*100),
                    xytext=(5, 5), textcoords='offset points', fontsize=9)
    ax3.grid(True, alpha=0.3)
    plt.colorbar(scatter3, ax=ax3, label='Frequency (GHz)')
    
    # Peak location Z coordinate vs frequency
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.plot(df['frequency_ghz'], df['peak_z'] * 100, 'go-', linewidth=2, markersize=10, label='Z (height)')
    ax4.plot(df['frequency_ghz'], df['peak_x'] * 100, 'bo-', linewidth=2, markersize=10, label='X (front-back)')
    ax4.plot(df['frequency_ghz'], df['peak_y'] * 100, 'ro-', linewidth=2, markersize=10, label='Y (left-right)')
    ax4.set_xlabel('Frequency (GHz)', fontsize=11)
    ax4.set_ylabel('Peak Location Coordinate (cm)', fontsize=11)
    ax4.set_title('Peak SAR Location Coordinates vs Frequency', fontsize=13)
    ax4.legend(loc='best')
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim([6, 27])
    
    plt.tight_layout()
    plt.savefig(OUTPUT_PATH / 'spatial_analysis_psSAR10g.png', dpi=150, bbox_inches='tight')
    plt.savefig(OUTPUT_PATH / 'spatial_analysis_psSAR10g.pdf', bbox_inches='tight')
    print(f"Saved: {OUTPUT_PATH / 'spatial_analysis_psSAR10g.png'}")
    return fig

def plot_performance_analysis(df):
    """Plot performance and computational metrics."""
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    
    # Plot 1: Total simulation time
    ax1 = axes[0, 0]
    bars = ax1.bar(df['frequency_ghz'].astype(str), df['total_time_s'] / 3600, color='steelblue', edgecolor='black')
    ax1.set_xlabel('Frequency (GHz)', fontsize=11)
    ax1.set_ylabel('Total Time (hours)', fontsize=11)
    ax1.set_title('Total Simulation Time', fontsize=13)
    ax1.grid(True, alpha=0.3, axis='y')
    for bar, val in zip(bars, df['total_time_s'] / 3600):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05, 
                f'{val:.1f}h', ha='center', va='bottom', fontsize=9)
    
    # Plot 2: Solver iterations
    ax2 = axes[0, 1]
    ax2.plot(df['frequency_ghz'], df['solver_iterations'], 'mo-', linewidth=2, markersize=10)
    ax2.set_xlabel('Frequency (GHz)', fontsize=11)
    ax2.set_ylabel('Solver Iterations', fontsize=11)
    ax2.set_title('FDTD Solver Iterations', fontsize=13)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim([6, 27])
    
    # Plot 3: Total grid cells
    ax3 = axes[0, 2]
    ax3.plot(df['frequency_ghz'], df['total_cells'] / 1e6, 'co-', linewidth=2, markersize=10)
    ax3.set_xlabel('Frequency (GHz)', fontsize=11)
    ax3.set_ylabel('Total Cells (millions)', fontsize=11)
    ax3.set_title('Grid Size (Total Cells)', fontsize=13)
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim([6, 27])
    
    # Plot 4: Performance (MCells/s)
    ax4 = axes[1, 0]
    ax4.plot(df['frequency_ghz'], df['avg_mcells_per_s'], 'go-', linewidth=2, markersize=10)
    ax4.set_xlabel('Frequency (GHz)', fontsize=11)
    ax4.set_ylabel('Average MCells/s', fontsize=11)
    ax4.set_title('Solver Performance', fontsize=13)
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim([6, 27])
    ax4.set_ylim([0, max(df['avg_mcells_per_s']) * 1.1])
    
    # Plot 5: Peak memory usage
    ax5 = axes[1, 1]
    ax5.plot(df['frequency_ghz'], df['peak_memory_gb'], 'ro-', linewidth=2, markersize=10)
    ax5.set_xlabel('Frequency (GHz)', fontsize=11)
    ax5.set_ylabel('Peak Memory (GB)', fontsize=11)
    ax5.set_title('GPU Memory Usage', fontsize=13)
    ax5.grid(True, alpha=0.3)
    ax5.set_xlim([6, 27])
    
    # Plot 6: Grid resolution (should be constant for same frequency band)
    ax6 = axes[1, 2]
    ax6.bar(df['frequency_ghz'].astype(str), df['grid_resolution_mm'], color='orange', edgecolor='black')
    ax6.set_xlabel('Frequency (GHz)', fontsize=11)
    ax6.set_ylabel('Grid Resolution (mm)', fontsize=11)
    ax6.set_title('Grid Resolution', fontsize=13)
    ax6.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(OUTPUT_PATH / 'performance_analysis.png', dpi=150, bbox_inches='tight')
    plt.savefig(OUTPUT_PATH / 'performance_analysis.pdf', bbox_inches='tight')
    print(f"Saved: {OUTPUT_PATH / 'performance_analysis.png'}")
    return fig

def plot_sar_ratios(df):
    """Plot SAR ratios and normalized values."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Plot 1: Peak SAR 10g / Whole Body SAR ratio
    ax1 = axes[0, 0]
    ratio = df['peak_sar_10g'] / df['whole_body_sar']
    ax1.plot(df['frequency_ghz'], ratio, 'ko-', linewidth=2, markersize=10)
    ax1.set_xlabel('Frequency (GHz)', fontsize=11)
    ax1.set_ylabel('Ratio', fontsize=11)
    ax1.set_title('Peak SAR 10g / Whole Body SAR Ratio', fontsize=13)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim([6, 27])
    
    # Plot 2: Skin/Brain SAR ratio
    ax2 = axes[0, 1]
    skin_brain_ratio = df['skin_avg_sar'] / df['brain_avg_sar']
    ax2.plot(df['frequency_ghz'], skin_brain_ratio, 'bo-', linewidth=2, markersize=10)
    ax2.set_xlabel('Frequency (GHz)', fontsize=11)
    ax2.set_ylabel('Ratio', fontsize=11)
    ax2.set_title('Skin/Brain Average SAR Ratio', fontsize=13)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim([6, 27])
    
    # Plot 3: Normalized SAR (relative to 7 GHz)
    ax3 = axes[1, 0]
    ref_sar = df[df['frequency_mhz'] == 7000]['peak_sar_10g'].values[0]
    normalized_sar = df['peak_sar_10g'] / ref_sar
    ax3.plot(df['frequency_ghz'], normalized_sar, 'go-', linewidth=2, markersize=10)
    ax3.axhline(y=1, color='gray', linestyle='--', alpha=0.5)
    ax3.set_xlabel('Frequency (GHz)', fontsize=11)
    ax3.set_ylabel('Normalized SAR (ref: 7 GHz)', fontsize=11)
    ax3.set_title('Peak SAR 10g Normalized to 7 GHz', fontsize=13)
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim([6, 27])
    
    # Plot 4: Stacked bar chart of tissue contributions
    ax4 = axes[1, 1]
    tissues = ['Eyes', 'Skin', 'Brain', 'Genitals']
    x = np.arange(len(df))
    width = 0.2
    
    ax4.bar(x - 1.5*width, df['eyes_avg_sar'] * 1e6, width, label='Eyes', color='#1f77b4')
    ax4.bar(x - 0.5*width, df['skin_avg_sar'] * 1e6, width, label='Skin', color='#ff7f0e')
    ax4.bar(x + 0.5*width, df['brain_avg_sar'] * 1e6, width, label='Brain', color='#2ca02c')
    ax4.bar(x + 1.5*width, df['genitals_avg_sar'] * 1e6, width, label='Genitals', color='#d62728')
    
    ax4.set_xlabel('Frequency (GHz)', fontsize=11)
    ax4.set_ylabel('Average SAR (µW/kg)', fontsize=11)
    ax4.set_title('Tissue-Specific Average SAR Comparison', fontsize=13)
    ax4.set_xticks(x)
    ax4.set_xticklabels(df['frequency_ghz'].astype(int).astype(str))
    ax4.legend(loc='upper left')
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(OUTPUT_PATH / 'sar_ratios.png', dpi=150, bbox_inches='tight')
    plt.savefig(OUTPUT_PATH / 'sar_ratios.pdf', bbox_inches='tight')
    print(f"Saved: {OUTPUT_PATH / 'sar_ratios.png'}")
    return fig

def plot_peak_cube_analysis(df):
    """Analyze the averaging cube size for peak SAR."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Plot 1: Peak cube side length vs frequency
    ax1 = axes[0]
    ax1.plot(df['frequency_ghz'], df['peak_cube_side'] * 1000, 'mo-', linewidth=2, markersize=10)
    ax1.set_xlabel('Frequency (GHz)', fontsize=11)
    ax1.set_ylabel('Cube Side Length (mm)', fontsize=11)
    ax1.set_title('10g Averaging Cube Side Length', fontsize=13)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim([6, 27])
    
    # Plot 2: Cube volume vs frequency
    ax2 = axes[1]
    cube_volume = (df['peak_cube_side'] * 100) ** 3  # in cm³
    ax2.plot(df['frequency_ghz'], cube_volume, 'co-', linewidth=2, markersize=10)
    ax2.set_xlabel('Frequency (GHz)', fontsize=11)
    ax2.set_ylabel('Cube Volume (cm³)', fontsize=11)
    ax2.set_title('10g Averaging Cube Volume', fontsize=13)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim([6, 27])
    
    plt.tight_layout()
    plt.savefig(OUTPUT_PATH / 'peak_cube_analysis.png', dpi=150, bbox_inches='tight')
    plt.savefig(OUTPUT_PATH / 'peak_cube_analysis.pdf', bbox_inches='tight')
    print(f"Saved: {OUTPUT_PATH / 'peak_cube_analysis.png'}")
    return fig

def plot_comprehensive_summary(df):
    """Create a comprehensive summary figure."""
    fig = plt.figure(figsize=(18, 14))
    
    # Title
    fig.suptitle('Thelonious FR3 Simulation Results Summary\nEnvironmental Exposure (x_neg, theta polarization)', 
                 fontsize=16, fontweight='bold', y=0.98)
    
    # Grid specification
    gs = fig.add_gridspec(3, 4, hspace=0.35, wspace=0.3)
    
    # Plot 1: Peak SAR 10g vs Frequency (main plot)
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.plot(df['frequency_ghz'], df['peak_sar_10g'] * 1e6, 'b-o', linewidth=2.5, markersize=12)
    ax1.fill_between(df['frequency_ghz'], 0, df['peak_sar_10g'] * 1e6, alpha=0.2)
    ax1.set_xlabel('Frequency (GHz)', fontsize=11)
    ax1.set_ylabel('Peak SAR 10g (µW/kg)', fontsize=11)
    ax1.set_title('Peak Spatial Average SAR (10g)', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim([6, 27])
    
    # Plot 2: Tissue comparison
    ax2 = fig.add_subplot(gs[0, 2:])
    tissues = ['Skin', 'Brain', 'Eyes', 'Genitals']
    colors = ['#ff7f0e', '#2ca02c', '#1f77b4', '#d62728']
    for tissue, color in zip(tissues, colors):
        col = f'{tissue.lower()}_avg_sar'
        ax2.semilogy(df['frequency_ghz'], df[col] * 1e6, 'o-', 
                    label=tissue, linewidth=2, markersize=8, color=color)
    ax2.set_xlabel('Frequency (GHz)', fontsize=11)
    ax2.set_ylabel('Average SAR (µW/kg)', fontsize=11)
    ax2.set_title('Tissue-Specific Average SAR', fontsize=13, fontweight='bold')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim([6, 27])
    
    # Plot 3: 3D peak locations
    ax3 = fig.add_subplot(gs[1, :2], projection='3d')
    scatter = ax3.scatter(df['peak_x'] * 100, df['peak_y'] * 100, df['peak_z'] * 100, 
                         c=df['frequency_ghz'], cmap='plasma', s=200, alpha=0.9)
    ax3.set_xlabel('X (cm)', fontsize=10)
    ax3.set_ylabel('Y (cm)', fontsize=10)
    ax3.set_zlabel('Z (cm)', fontsize=10)
    ax3.set_title('Peak SAR 10g Locations (3D)', fontsize=13, fontweight='bold')
    cbar = plt.colorbar(scatter, ax=ax3, shrink=0.6, pad=0.1)
    cbar.set_label('Freq (GHz)', fontsize=9)
    
    # Plot 4: Peak Z coordinate vs frequency
    ax4 = fig.add_subplot(gs[1, 2:])
    ax4.plot(df['frequency_ghz'], df['peak_z'] * 100, 'go-', linewidth=2, markersize=10)
    ax4.set_xlabel('Frequency (GHz)', fontsize=11)
    ax4.set_ylabel('Peak Z Coordinate (cm)', fontsize=11)
    ax4.set_title('Peak SAR Height vs Frequency', fontsize=13, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim([6, 27])
    
    # Annotate: 7 GHz peak is at head, others at lower body
    ax4.annotate('Head region\n(7 GHz)', xy=(7, df[df['frequency_ghz']==7]['peak_z'].values[0]*100),
                xytext=(9, 20), fontsize=9,
                arrowprops=dict(arrowstyle='->', color='gray'))
    ax4.annotate('Lower body\n(9-26 GHz)', xy=(15, df[df['frequency_ghz']==15]['peak_z'].values[0]*100),
                xytext=(17, -30), fontsize=9,
                arrowprops=dict(arrowstyle='->', color='gray'))
    
    # Plot 5: Simulation time
    ax5 = fig.add_subplot(gs[2, 0])
    bars = ax5.bar(df['frequency_ghz'].astype(int).astype(str), df['total_time_s'] / 3600, 
                   color='steelblue', edgecolor='black')
    ax5.set_xlabel('Frequency (GHz)', fontsize=10)
    ax5.set_ylabel('Time (hours)', fontsize=10)
    ax5.set_title('Simulation Time', fontsize=12, fontweight='bold')
    ax5.grid(True, alpha=0.3, axis='y')
    
    # Plot 6: Grid cells
    ax6 = fig.add_subplot(gs[2, 1])
    ax6.plot(df['frequency_ghz'], df['total_cells'] / 1e6, 'co-', linewidth=2, markersize=8)
    ax6.set_xlabel('Frequency (GHz)', fontsize=10)
    ax6.set_ylabel('Cells (millions)', fontsize=10)
    ax6.set_title('Grid Size', fontsize=12, fontweight='bold')
    ax6.grid(True, alpha=0.3)
    ax6.set_xlim([6, 27])
    
    # Plot 7: Memory usage
    ax7 = fig.add_subplot(gs[2, 2])
    ax7.plot(df['frequency_ghz'], df['peak_memory_gb'], 'ro-', linewidth=2, markersize=8)
    ax7.set_xlabel('Frequency (GHz)', fontsize=10)
    ax7.set_ylabel('Memory (GB)', fontsize=10)
    ax7.set_title('GPU Memory', fontsize=12, fontweight='bold')
    ax7.grid(True, alpha=0.3)
    ax7.set_xlim([6, 27])
    
    # Plot 8: Performance
    ax8 = fig.add_subplot(gs[2, 3])
    ax8.plot(df['frequency_ghz'], df['avg_mcells_per_s'], 'go-', linewidth=2, markersize=8)
    ax8.set_xlabel('Frequency (GHz)', fontsize=10)
    ax8.set_ylabel('MCells/s', fontsize=10)
    ax8.set_title('Solver Performance', fontsize=12, fontweight='bold')
    ax8.grid(True, alpha=0.3)
    ax8.set_xlim([6, 27])
    
    plt.savefig(OUTPUT_PATH / 'comprehensive_summary.png', dpi=150, bbox_inches='tight')
    plt.savefig(OUTPUT_PATH / 'comprehensive_summary.pdf', bbox_inches='tight')
    print(f"Saved: {OUTPUT_PATH / 'comprehensive_summary.png'}")
    return fig

def print_analysis_summary(df):
    """Print a text summary of the analysis."""
    print("\n" + "="*80)
    print("THELONIOUS FR3 SIMULATION RESULTS ANALYSIS")
    print("="*80)
    
    print("\n📊 DATA OVERVIEW")
    print("-"*40)
    print(f"  Phantom: Thelonious")
    print(f"  Exposure: Environmental (x_neg, theta polarization)")
    print(f"  Frequencies: {', '.join([f'{f/1000:.0f} GHz' for f in FREQUENCIES])}")
    print(f"  Input Power: {df['input_power_w'].iloc[0]*1e6:.2f} µW (constant)")
    
    print("\n📈 SAR STATISTICS")
    print("-"*40)
    print(f"  Peak SAR 10g range: {df['peak_sar_10g'].min()*1e6:.2f} - {df['peak_sar_10g'].max()*1e6:.2f} µW/kg")
    print(f"  Whole Body SAR range: {df['whole_body_sar'].min()*1e6:.2f} - {df['whole_body_sar'].max()*1e6:.2f} µW/kg")
    print(f"  Max Peak SAR 10g at: {df.loc[df['peak_sar_10g'].idxmax(), 'frequency_ghz']:.0f} GHz")
    print(f"  Min Peak SAR 10g at: {df.loc[df['peak_sar_10g'].idxmin(), 'frequency_ghz']:.0f} GHz")
    
    print("\n🎯 SPATIAL ANALYSIS OF psSAR10g")
    print("-"*40)
    for _, row in df.iterrows():
        print(f"  {row['frequency_ghz']:.0f} GHz: Peak at ({row['peak_x']*100:.1f}, {row['peak_y']*100:.1f}, {row['peak_z']*100:.1f}) cm")
    
    # Identify peak location patterns
    head_peaks = df[df['peak_z'] > 0]
    body_peaks = df[df['peak_z'] < 0]
    print(f"\n  Peak in HEAD region (Z > 0): {len(head_peaks)} frequencies ({', '.join([f'{f:.0f}G' for f in head_peaks['frequency_ghz']])})")
    print(f"  Peak in BODY region (Z < 0): {len(body_peaks)} frequencies ({', '.join([f'{f:.0f}G' for f in body_peaks['frequency_ghz']])})")
    
    print("\n🔬 TISSUE-SPECIFIC OBSERVATIONS")
    print("-"*40)
    print("  Skin SAR:")
    print(f"    - Increases with frequency: {df['skin_avg_sar'].iloc[0]*1e6:.2f} → {df['skin_avg_sar'].iloc[-1]*1e6:.2f} µW/kg")
    print(f"    - Ratio (26 GHz / 7 GHz): {df['skin_avg_sar'].iloc[-1]/df['skin_avg_sar'].iloc[0]:.2f}x")
    print("  Eyes SAR:")
    print(f"    - Decreases with frequency: {df['eyes_avg_sar'].iloc[0]*1e6:.2f} → {df['eyes_avg_sar'].iloc[-1]*1e6:.2f} µW/kg")
    print(f"    - Ratio (26 GHz / 7 GHz): {df['eyes_avg_sar'].iloc[-1]/df['eyes_avg_sar'].iloc[0]:.2f}x")
    print("  Brain SAR:")
    print(f"    - Slight decrease: {df['brain_avg_sar'].iloc[0]*1e6:.2f} → {df['brain_avg_sar'].iloc[-1]*1e6:.2f} µW/kg")
    
    print("\n⚡ PERFORMANCE SUMMARY")
    print("-"*40)
    print(f"  Total simulation time: {df['total_time_s'].sum()/3600:.1f} hours")
    print(f"  Average time per frequency: {df['total_time_s'].mean()/3600:.1f} hours")
    print(f"  Grid cells range: {df['total_cells'].min()/1e6:.1f} - {df['total_cells'].max()/1e6:.1f} million")
    print(f"  Peak GPU memory: {df['peak_memory_gb'].max():.1f} GB")
    print(f"  Solver performance: {df['avg_mcells_per_s'].mean():.0f} MCells/s (average)")
    
    print("\n" + "="*80)

def main():
    """Main analysis function."""
    print("Loading data...")
    data = load_all_data()
    
    if not data:
        print("ERROR: No data found in results/thelonious_FR3")
        return
    
    print(f"Loaded data for {len(data)} frequencies")
    
    # Create DataFrame
    df = create_dataframe(data)
    
    # Print summary
    print_analysis_summary(df)
    
    # Generate all plots
    print("\nGenerating plots...")
    
    plot_sar_vs_frequency(df)
    plot_spatial_analysis_psSAR10g(df)
    plot_performance_analysis(df)
    plot_sar_ratios(df)
    plot_peak_cube_analysis(df)
    plot_comprehensive_summary(df)
    
    # Save data to CSV
    csv_path = OUTPUT_PATH / 'thelonious_FR3_data.csv'
    df.to_csv(csv_path, index=False)
    print(f"Saved: {csv_path}")
    
    print(f"\n✅ All plots saved to: {OUTPUT_PATH}")
    print("Analysis complete!")
    
    # Show plots
    plt.show()

if __name__ == "__main__":
    main()
