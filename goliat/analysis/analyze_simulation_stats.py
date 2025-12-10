"""
Analyze Near-Field simulation logs and create professional, client-ready visualizations.

IMPROVEMENTS:
- Strict filtering for Near Field simulations only.
- Emojis removed to prevent font rendering errors.
- "High-End Engineering" aesthetic (professional dark theme).
- Dynamic layout scaling for lists with many items.
- Robust text placement to avoid overlap.
"""

import json
import logging
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

from goliat.analysis.parse_verbose_log import parse_verbose_log


def find_all_verbose_logs(results_dir: str | Path) -> list[Path]:
    """Find all verbose.log files in the results directory."""
    results_dir = Path(results_dir)
    return list(results_dir.rglob("verbose.log"))


def parse_all_logs(log_files: list[Path], verbose: bool = True) -> list[dict]:
    """Parse all verbose.log files and return list of metrics."""
    all_metrics = []

    for i, log_file in enumerate(log_files):
        # STRICT FILTER: Only Near Field
        if "near_field" not in log_file.parts:
            continue

        if verbose and i % 50 == 0:
            logging.getLogger("progress").info(f"  Parsing: {i + 1}/{len(log_files)}...", extra={"log_type": "verbose"})

        try:
            metrics = parse_verbose_log(log_file)

            # Robust category extraction
            parts = log_file.parts
            category = {"study_type": "near_field", "phantom": "unknown", "frequency": "unknown", "placement": "unknown"}

            try:
                # Assuming structure: .../near_field/phantom/freq/placement/verbose.log
                nf_index = parts.index("near_field")
                if nf_index + 3 < len(parts):
                    category["phantom"] = parts[nf_index + 1]
                    category["frequency"] = parts[nf_index + 2]
                    category["placement"] = parts[nf_index + 3]
            except ValueError:
                pass

            metrics["category"] = category
            all_metrics.append(metrics)

        except Exception:
            if verbose:
                # print(f"  Error parsing {log_file}: {e}")
                pass

    if verbose:
        logging.getLogger("progress").info(f"  Parsed {len(all_metrics)} Near-Field log files.", extra={"log_type": "progress"})

    return all_metrics


def compute_aggregate_stats(all_metrics: list[dict]) -> dict:
    """Compute aggregate statistics across all simulations."""
    stats = {
        "total_simulations": len(all_metrics),
        "total_cells": 0,
        "total_cells_with_pml": 0,
        "total_edges": 0,
        "total_iterations": 0,
        "total_cell_iterations": 0,
        "total_runtime_s": 0,
        "total_materials": [],  # Changed to list for JSON serialization
        "total_tissues": [],  # Changed to list for JSON serialization
        "by_phantom": defaultdict(lambda: {"count": 0, "cells": 0, "iterations": 0, "cell_iterations": 0, "runtime_s": 0}),
        "by_frequency": defaultdict(lambda: {"count": 0, "cells": 0, "iterations": 0, "cell_iterations": 0, "runtime_s": 0}),
        "by_placement": defaultdict(lambda: {"count": 0, "cells": 0, "iterations": 0, "cell_iterations": 0, "runtime_s": 0}),
        "iterations_list": [],
        "cells_list": [],
        "runtime_list": [],
        "cell_iterations_list": [],
        "peak_speed_list": [],  # Peak MCells/s per simulation
        "avg_speed_list": [],  # Avg MCells/s per simulation
    }

    unique_tissues = set()

    for m in all_metrics:
        # Extract values
        cells = m.get("grid", {}).get("total_cells_with_pml", 0)
        iterations = m.get("solver", {}).get("iterations", 0)
        runtime = m.get("timing", {}).get("total_wall_clock_s", 0)
        edges = m.get("edges", {}).get("total_edges", 0)
        cell_iterations = cells * iterations if cells and iterations else 0

        # Aggregate totals
        stats["total_cells_with_pml"] += cells
        stats["total_cells"] += m.get("grid", {}).get("total_cells", 0)
        stats["total_edges"] += edges
        stats["total_iterations"] += iterations
        stats["total_cell_iterations"] += cell_iterations
        stats["total_runtime_s"] += runtime

        # Track materials/tissues
        for tissue in m.get("materials", {}).get("tissues", []):
            unique_tissues.add(tissue.get("name", ""))

        # Lists for distributions
        stats["iterations_list"].append(iterations)
        stats["cells_list"].append(cells)
        stats["runtime_list"].append(runtime)
        stats["cell_iterations_list"].append(cell_iterations)

        # Speed metrics from summary
        summary = m.get("summary", {})
        if summary.get("peak_mcells_per_s"):
            stats["peak_speed_list"].append(summary["peak_mcells_per_s"])
        if summary.get("avg_mcells_per_s"):
            stats["avg_speed_list"].append(summary["avg_mcells_per_s"])

        # By category
        cat = m.get("category", {})

        if cat.get("phantom"):
            p = stats["by_phantom"][cat["phantom"]]
            p["count"] += 1
            p["cells"] += cells
            p["iterations"] += iterations
            p["cell_iterations"] += cell_iterations
            p["runtime_s"] += runtime

        if cat.get("frequency"):
            freq = cat["frequency"]
            f = stats["by_frequency"][freq]
            f["count"] += 1
            f["cells"] += cells
            f["iterations"] += iterations
            f["cell_iterations"] += cell_iterations
            f["runtime_s"] += runtime

        if cat.get("placement"):
            # Group by placement type more cleanly
            placement = cat["placement"]
            pl = stats["by_placement"][placement]
            pl["count"] += 1
            pl["cells"] += cells
            pl["iterations"] += iterations
            pl["cell_iterations"] += cell_iterations
            pl["runtime_s"] += runtime

    stats["unique_tissue_count"] = len(unique_tissues)
    stats["total_tissues"] = list(unique_tissues)

    # Convert defaultdicts to simple dicts
    stats["by_phantom"] = {k: dict(v) for k, v in stats["by_phantom"].items()}
    stats["by_frequency"] = {k: dict(v) for k, v in stats["by_frequency"].items()}
    stats["by_placement"] = {k: dict(v) for k, v in stats["by_placement"].items()}

    return stats


def format_large_number(n: float, precision: int = 1) -> str:
    """Format large numbers with appropriate suffixes."""
    if n >= 1e15:
        return f"{n / 1e15:.{precision}f} Quadrillion"
    elif n >= 1e12:
        return f"{n / 1e12:.{precision}f} Trillion"
    elif n >= 1e9:
        return f"{n / 1e9:.{precision}f} Billion"
    elif n >= 1e6:
        return f"{n / 1e6:.{precision}f} Million"
    elif n >= 1e3:
        return f"{n / 1e3:.{precision}f} K"
    else:
        return f"{n:.{precision}f}"


def set_custom_style():
    """Set a professional, high-contrast engineering dark style."""
    plt.style.use("seaborn-v0_8-darkgrid")

    # Colors suitable for "Engineering/Simulation" look (Deep Blues, Bright Cyans, Warm Accents)
    bg_color = "#0e1117"
    paper_color = "#0e1117"
    text_color = "#e0e0e0"  # Softer white
    grid_color = "#262730"

    # Updated Palette - Less aggressive, more "Scientific"
    primary_blue = "#2E86C1"  # Strong, professional blue
    cyan_bright = "#00BFA5"  # Teal/Cyan for distinction
    alert_orange = "#FF7043"  # Softer than red, for highlights
    soft_purple = "#9b59b6"
    slate_grey = "#607D8B"
    gold_accent = "#F1C40F"

    plt.rcParams.update(
        {
            "figure.facecolor": paper_color,
            "axes.facecolor": bg_color,
            "axes.edgecolor": grid_color,
            "axes.labelcolor": text_color,
            "text.color": text_color,
            "xtick.color": text_color,
            "ytick.color": text_color,
            "grid.color": grid_color,
            "grid.alpha": 0.6,
            "figure.figsize": (12, 7),
            "font.size": 12,
            "axes.labelsize": 13,
            "axes.titlesize": 16,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "font.family": "sans-serif",  # Ensure standard font
        }
    )

    return [primary_blue, cyan_bright, alert_orange, soft_purple, slate_grey, gold_accent]


def create_visualizations(stats: dict, output_dir: str | Path):
    """Create all visualizations with rigorous layout checks."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    colors = set_custom_style()

    # 01. COMPUTATIONAL SCALE
    fig, ax = plt.subplots(figsize=(14, 8))

    labels = ["Cells Computed", "Edges Computed", "Grid Cells (PML)", "Time Steps"]
    values = [stats["total_cell_iterations"], stats["total_edges"], stats["total_cells_with_pml"], stats["total_iterations"]]

    y_pos = np.arange(len(labels))
    # Use the blue/teal/purple palette
    bar_colors = [colors[2], colors[0], colors[1], colors[5]]

    ax.barh(y_pos, values, color=bar_colors, height=0.6, alpha=0.9)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontweight="bold")
    ax.set_xscale("log")
    ax.set_title(f"Simulation Campaign Scale ({stats['total_simulations']} Runs)", pad=20, fontweight="bold")
    ax.set_xlabel("Count (Log Scale)")
    ax.grid(True, which="both", ls="-", alpha=0.3)

    # Text labels placed strictly outside for readability
    for i, v in enumerate(values):
        ax.text(v * 1.5, i, f" {format_large_number(v, 2)}", va="center", fontweight="bold", color="white")

    ax.set_xlim(right=max(values) * 50)

    plt.tight_layout()
    fig.savefig(output_dir / "01_computational_scale.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # 02. DETAILED PLACEMENT ANALYSIS
    placements = sorted(stats["by_placement"].keys())
    # Clean names
    display_names = [p.replace("by_", "").replace("front_of_", "").replace("_", " ").title() for p in placements]
    values = [stats["by_placement"][p]["cell_iterations"] for p in placements]

    # Sort
    if values:
        sorted_pack = sorted(zip(values, display_names), reverse=False)
        values = [x[0] for x in sorted_pack]
        display_names = [x[1] for x in sorted_pack]

    dynamic_height = max(8, len(values) * 0.4)
    fig, ax = plt.subplots(figsize=(14, dynamic_height))

    # Main bars in primary blue
    ax.barh(range(len(values)), values, color=colors[0], alpha=0.85)

    ax.set_yticks(range(len(values)))
    ax.set_yticklabels(display_names)
    ax.set_xlabel("Computational Cost (Cells Computed)")
    ax.set_title("Computational Load by Antenna Placement", pad=20, fontweight="bold")
    ax.grid(True, axis="x", alpha=0.3)

    max_val = max(values) if values else 1
    for i, v in enumerate(values):
        label_text = f"{format_large_number(v)}"
        if v > max_val * 0.2:
            ax.text(v - (max_val * 0.02), i, label_text, va="center", ha="right", color="white", fontweight="bold")
        else:
            ax.text(v + (max_val * 0.01), i, label_text, va="center", ha="left", color="#dddddd", fontweight="bold")

    plt.tight_layout()
    fig.savefig(output_dir / "02_placement_cost.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # 03. PHANTOM & FREQUENCY
    phantom_list = sorted(stats["by_phantom"].keys())

    # Filter out Duke if it somehow snuck in with 0 stats, but keep if real
    # Only keep phantoms with > 0 cell iterations to be safe
    phantom_list = [p for p in phantom_list if stats["by_phantom"][p]["cell_iterations"] > 0]

    freq_list = sorted(stats["by_frequency"].keys(), key=lambda x: int(m.group()) if (m := re.search(r"\d+", x)) else 0)

    fig = plt.figure(figsize=(16, 8))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1, 1], wspace=0.3)

    # Phantoms
    ax0 = plt.subplot(gs[0])
    p_values = [stats["by_phantom"][p]["cell_iterations"] for p in phantom_list]

    # Nice bar colors
    ax0.bar(phantom_list, p_values, color=colors[3], alpha=0.9)
    ax0.set_title("Load by Phantom", fontweight="bold")
    ax0.set_ylabel("Cells Computed")
    ax0.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x / 1e12:.0f}T"))
    ax0.grid(True, axis="y", alpha=0.3)

    # Value labels
    for i, v in enumerate(p_values):
        ax0.text(i, v, f"{v / 1e12:.1f}T", ha="center", va="bottom", fontweight="bold", color="white")

    # Frequencies
    ax1 = plt.subplot(gs[1])
    f_values = [stats["by_frequency"][f]["cell_iterations"] for f in freq_list]
    ax1.bar(freq_list, f_values, color=colors[1], alpha=0.9)
    ax1.set_title("Load by Frequency", fontweight="bold")
    ax1.tick_params(axis="x", rotation=45)
    ax1.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    fig.savefig(output_dir / "03_phantom_freq_breakdown.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # 04. CLIENT INFOGRAPHIC (Enhanced)
    fig = plt.figure(figsize=(18, 10))
    fig.patch.set_facecolor("#0e1117")

    # Compute additional metrics
    peak_speed_gcells_s = max(stats["peak_speed_list"]) / 1000 if stats["peak_speed_list"] else 0
    avg_runtime_min = (stats["total_runtime_s"] / stats["total_simulations"]) / 60 if stats["total_simulations"] > 0 else 0
    num_placements = len(stats["by_placement"])

    # Get frequency range
    freq_list_sorted = sorted(stats["by_frequency"].keys(), key=lambda x: int(m.group()) if (m := re.search(r"\d+", x)) else 0)
    if freq_list_sorted:
        freq_range = f"{freq_list_sorted[0]} - {freq_list_sorted[-1]}"
    else:
        freq_range = "N/A"

    # Title Area
    gs = gridspec.GridSpec(5, 4, height_ratios=[0.15, 0.28, 0.28, 0.28, 0.08], hspace=0.15)
    ax_title = plt.subplot(gs[0, :])
    ax_title.axis("off")
    ax_title.text(0.5, 0.5, "NEAR FIELD COMPUTATIONAL CAMPAIGN", ha="center", va="center", fontsize=30, color=colors[1], fontweight="bold")

    # Row 1: Hero Stats (Large)
    hero_stats = [
        ("TOTAL RUNS", f"{stats['total_simulations']}", colors[0]),
        ("CELLS COMPUTED", f"{stats['total_cell_iterations'] / 1e15:.2f} Quadrillion", colors[2]),
        ("COMPUTE TIME", f"{stats['total_runtime_s'] / 3600:.0f} Hours", colors[1]),
        ("PEAK SPEED", f"{peak_speed_gcells_s:.1f} GCells/s", colors[5]),
    ]

    for i, (k, v, c) in enumerate(hero_stats):
        ax = plt.subplot(gs[1, i])
        ax.axis("off")
        ax.text(0.5, 0.6, v, ha="center", va="center", fontsize=24, fontweight="bold", color=c)
        ax.text(0.5, 0.3, k, ha="center", va="center", fontsize=11, fontweight="bold", color="#aaaaaa")

    # Row 2: Grid & Data Stats
    row2_stats = [
        ("Grid Cells", f"{stats['total_cells_with_pml'] / 1e9:.1f} Billion", "#ffffff"),
        ("Data Edges", f"{stats['total_edges'] / 1e9:.1f} Billion", "#ffffff"),
        ("Time Steps", f"{stats['total_iterations'] / 1e6:.1f} Million", "#ffffff"),
        ("Avg Sim Time", f"{avg_runtime_min:.1f} min", "#ffffff"),
    ]

    for i, (k, v, c) in enumerate(row2_stats):
        ax = plt.subplot(gs[2, i])
        ax.axis("off")
        rect = plt.Rectangle((0.1, 0.15), 0.8, 0.7, transform=ax.transAxes, fill=True, color="#1e222b", zorder=0, alpha=0.8, lw=0)
        ax.add_patch(rect)
        ax.text(0.5, 0.6, v, ha="center", va="center", fontsize=18, fontweight="bold", color=c)
        ax.text(0.5, 0.35, k, ha="center", va="center", fontsize=11, color="#888888")

    # Row 3: Study Configuration
    row3_stats = [
        ("Anatomical Models", f"{len(phantom_list)}", "#ffffff"),
        ("Frequency Range", freq_range, "#ffffff"),
        ("Antenna Placements", f"{num_placements}", "#ffffff"),
        ("Tissues Modeled", f"{stats['unique_tissue_count']}", "#ffffff"),
    ]

    for i, (k, v, c) in enumerate(row3_stats):
        ax = plt.subplot(gs[3, i])
        ax.axis("off")
        rect = plt.Rectangle((0.1, 0.15), 0.8, 0.7, transform=ax.transAxes, fill=True, color="#1e222b", zorder=0, alpha=0.8, lw=0)
        ax.add_patch(rect)
        ax.text(0.5, 0.6, v, ha="center", va="center", fontsize=18, fontweight="bold", color=c)
        ax.text(0.5, 0.35, k, ha="center", va="center", fontsize=11, color="#888888")

    # Footer
    ax_foot = plt.subplot(gs[4, :])
    ax_foot.axis("off")
    ax_foot.text(
        0.5,
        0.5,
        f"Generated: {datetime.now().strftime('%Y-%m-%d')} | GOLIAT Solver Analysis",
        ha="center",
        va="center",
        fontsize=10,
        color="#666666",
    )

    plt.tight_layout()
    fig.savefig(output_dir / "00_summary_infographic.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # 04. RUNTIME DISTRIBUTION (Restored)
    if stats["runtime_list"]:
        fig, ax = plt.subplots(figsize=(14, 7))
        # Convert to minutes
        runtimes_min = [r / 60 for r in stats["runtime_list"]]

        ax.hist(runtimes_min, bins=30, color=colors[3], alpha=0.7, edgecolor=colors[3])
        ax.set_title("Simulation Runtime Distribution", pad=20, fontweight="bold")
        ax.set_xlabel("Runtime (Minutes)")
        ax.set_ylabel("Number of Simulations")

        # Add a text box with stats
        avg_runtime = np.mean(runtimes_min)
        total_hours = sum(runtimes_min) / 60
        stats_text = f"Total Time: {total_hours:.1f} Hours\nAvg Runtime: {avg_runtime:.1f} min\nMax Runtime: {max(runtimes_min):.1f} min"

        ax.text(
            0.95,
            0.95,
            stats_text,
            transform=ax.transAxes,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="round", facecolor="#1e222b", alpha=0.8, edgecolor=colors[4]),
            color="white",
            fontsize=12,
        )

        ax.grid(True, axis="y", alpha=0.3)
        plt.tight_layout()
        fig.savefig(output_dir / "04_runtime_distribution.png", dpi=200, bbox_inches="tight")
        plt.close(fig)

    # 05. SCATTER PLOT: GRID SIZE vs RUNTIME
    if stats["cells_list"] and stats["runtime_list"]:
        fig, ax = plt.subplots(figsize=(14, 8))

        cells_m = [c / 1e6 for c in stats["cells_list"]]
        # Convert seconds to minutes
        runtimes_min = [r / 60 for r in stats["runtime_list"]]

        # Scatter with alpha to show density
        ax.scatter(cells_m, runtimes_min, c=colors[1], alpha=0.6, s=80, edgecolors="none")

        ax.set_title("Solver Performance: Grid Size vs Compute Time", pad=20, fontweight="bold")
        ax.set_xlabel("Grid Size (Million Cells)")
        ax.set_ylabel("Compute Time (Minutes)")
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)
        ax.grid(True, alpha=0.3)

        # Add correlation text
        if len(cells_m) > 1:
            try:
                corr = np.corrcoef(cells_m, runtimes_min)[0, 1]
                ax.text(
                    0.05,
                    0.95,
                    f"Correlation: {corr:.3f}",
                    transform=ax.transAxes,
                    bbox=dict(boxstyle="round", facecolor="#1e222b", alpha=0.8),
                    color="white",
                )
            except Exception:
                pass

        plt.tight_layout()
        fig.savefig(output_dir / "05_solver_scaling.png", dpi=200, bbox_inches="tight")
        plt.close(fig)

    # 06. SPEED DISTRIBUTION PLOT
    if stats["peak_speed_list"]:
        fig, ax = plt.subplots(figsize=(14, 7))

        # Convert to GCells/s for readability
        peak_speeds_gcells = [s / 1000 for s in stats["peak_speed_list"]]

        # Histogram of Peak Speeds
        ax.hist(peak_speeds_gcells, bins=25, color=colors[2], alpha=0.8, edgecolor=colors[2])
        ax.set_title("Solver Speed Distribution", pad=15, fontweight="bold")
        ax.set_xlabel("Peak Speed (GCells/s)")
        ax.set_ylabel("Number of Simulations")
        ax.grid(True, axis="y", alpha=0.3)

        # Add stats annotation
        max_speed = max(peak_speeds_gcells)
        avg_peak = np.mean(peak_speeds_gcells)
        stats_text = (
            f"Fastest: {max_speed:.2f} GCells/s\nAvg Peak: {avg_peak:.2f} GCells/s\nMin Peak: {min(peak_speeds_gcells):.2f} GCells/s"
        )
        ax.axvline(max_speed, color=colors[5], linestyle="--", linewidth=2, label=f"Fastest: {max_speed:.2f}")
        ax.text(
            0.95,
            0.95,
            stats_text,
            transform=ax.transAxes,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="round", facecolor="#1e222b", alpha=0.9, edgecolor=colors[5]),
            color="white",
            fontsize=11,
        )

        plt.tight_layout()
        fig.savefig(output_dir / "06_speed_distribution.png", dpi=200, bbox_inches="tight")
        plt.close(fig)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir", nargs="?", default="results")
    parser.add_argument("-o", "--output", default="paper/simulation_stats")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    log_files = find_all_verbose_logs(args.results_dir)
    all_metrics = parse_all_logs(log_files)

    if not all_metrics:
        logging.getLogger("progress").warning("  No Near-Field logs found.", extra={"log_type": "warning"})
        return

    stats = compute_aggregate_stats(all_metrics)

    logging.getLogger("progress").info(f"  Total Simulations: {stats['total_simulations']}", extra={"log_type": "info"})
    logging.getLogger("progress").info(
        f"  Total Cell-Iterations: {format_large_number(stats['total_cell_iterations'])}", extra={"log_type": "info"}
    )

    create_visualizations(stats, args.output)

    if args.json:
        json_path = Path(args.output) / "nf_stats.json"
        # We need to filter out the large lists before dumping
        json_stats = stats.copy()
        json_stats["iterations_list"] = []
        json_stats["cells_list"] = []
        json_stats["runtime_list"] = []
        json_stats["cell_iterations_list"] = []
        json_stats["peak_speed_list"] = []
        json_stats["avg_speed_list"] = []

        with open(json_path, "w") as f:
            json.dump(json_stats, f, indent=2)

    logging.getLogger("progress").info(f"  Saved visualizations to: {args.output}/", extra={"log_type": "success"})


if __name__ == "__main__":
    main()
