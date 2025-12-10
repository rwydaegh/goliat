"""
Parse verbose.log files to extract simulation metrics into JSON format.

This script extracts all key metrics from GOLIAT/Sim4Life verbose logs
for reporting and analysis purposes.
"""

import re
import json
import argparse
from pathlib import Path
from typing import Any
from datetime import datetime


def parse_verbose_log(log_path: str | Path) -> dict[str, Any]:
    """
    Parse a verbose.log file and extract all simulation metrics.

    Args:
        log_path: Path to the verbose.log file

    Returns:
        Dictionary containing all extracted metrics
    """
    log_path = Path(log_path)

    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    content = log_path.read_text(encoding="utf-8", errors="replace")

    metrics = {
        "metadata": _extract_metadata(content, log_path),
        "phantom": _extract_phantom_info(content),
        "grid": _extract_grid_info(content),
        "boundaries": _extract_boundary_info(content),
        "materials": _extract_materials_info(content),
        "solver": _extract_solver_info(content),
        "timing": _extract_timing_info(content),
        "hardware": _extract_hardware_info(content),
        "simulation": _extract_simulation_info(content),
        "edges": _extract_edge_statistics(content),
        "sensors": _extract_sensor_info(content),
        "sources": _extract_source_info(content),
        "results": _extract_results_info(content),
        "_content": content,  # Store for speed extraction in _compute_summary
    }

    # Add computed summary statistics
    metrics["summary"] = _compute_summary(metrics)

    # Remove _content to save memory (it's huge)
    del metrics["_content"]

    return metrics


def _extract_metadata(content: str, log_path: Path) -> dict[str, Any]:
    """Extract metadata about the simulation run."""
    metadata = {
        "log_file": str(log_path),
        "parse_timestamp": datetime.now().isoformat(),
    }

    # Extract simulation name
    match = re.search(r"Simulation '([^']+)' started on (.+)", content)
    if match:
        metadata["simulation_name"] = match.group(1)
        metadata["start_time"] = match.group(2).strip()

    # Extract end time
    match = re.search(r"Simulation '([^']+)' has ended successfully on (.+?) and took", content)
    if match:
        metadata["end_time"] = match.group(2).strip()

    # Extract phantom and frequency from path
    parts = log_path.parts
    for i, part in enumerate(parts):
        if part == "near_field" and i + 3 < len(parts):
            metadata["phantom_name"] = parts[i + 1]
            metadata["frequency_folder"] = parts[i + 2]
            metadata["placement"] = parts[i + 3]
            break

    # Extract project path
    match = re.search(r"Saving project to ([^\s]+\.smash)", content)
    if match:
        metadata["project_path"] = match.group(1)

    return metadata


def _extract_phantom_info(content: str) -> dict[str, Any]:
    """Extract phantom-related information."""
    phantom = {}

    # Extract phantom file path
    match = re.search(r"Importing from '([^']+)'", content)
    if match:
        phantom["file_path"] = match.group(1)
        phantom["file_name"] = Path(match.group(1)).name

    # Extract import time
    match = re.search(r"Phantom imported successfully.*?done in ([\d.]+)s", content, re.DOTALL)
    if match:
        phantom["import_time_s"] = float(match.group(1))

    return phantom


def _extract_grid_info(content: str) -> dict[str, Any]:
    """Extract grid information."""
    grid = {}

    # Number of cells
    match = re.search(r"Number of cells: (\d+)x(\d+)x(\d+) = (\d+) cells = ([\d.]+) MCells", content)
    if match:
        grid["dimensions"] = {
            "x": int(match.group(1)),
            "y": int(match.group(2)),
            "z": int(match.group(3)),
        }
        grid["total_cells"] = int(match.group(4))
        grid["total_mcells"] = float(match.group(5))

    # Number of cells with PML
    match = re.search(r"Number of cells including PML: (\d+)x(\d+)x(\d+) = (\d+) cells = ([\d.]+) MCells", content)
    if match:
        grid["dimensions_with_pml"] = {
            "x": int(match.group(1)),
            "y": int(match.group(2)),
            "z": int(match.group(3)),
        }
        grid["total_cells_with_pml"] = int(match.group(4))
        grid["total_mcells_with_pml"] = float(match.group(5))

    # X range
    match = re.search(r"X: Range \[([-\d.]+) \.\.\. ([-\d.]+)\] with minimal ([-\d.e+]+) and maximal step ([-\d.e+]+)", content)
    if match:
        grid["x_range"] = {
            "min_m": float(match.group(1)),
            "max_m": float(match.group(2)),
            "min_step_m": float(match.group(3)),
            "max_step_m": float(match.group(4)),
        }
        grid["x_range"]["extent_mm"] = (grid["x_range"]["max_m"] - grid["x_range"]["min_m"]) * 1000

    # Y range
    match = re.search(r"Y: Range \[([-\d.]+) \.\.\. ([-\d.]+)\] with minimal ([-\d.e+]+) and maximal step ([-\d.e+]+)", content)
    if match:
        grid["y_range"] = {
            "min_m": float(match.group(1)),
            "max_m": float(match.group(2)),
            "min_step_m": float(match.group(3)),
            "max_step_m": float(match.group(4)),
        }
        grid["y_range"]["extent_mm"] = (grid["y_range"]["max_m"] - grid["y_range"]["min_m"]) * 1000

    # Z range
    match = re.search(r"Z: Range \[([-\d.]+) \.\.\. ([-\d.]+)\] with minimal ([-\d.e+]+) and maximal step ([-\d.e+]+)", content)
    if match:
        grid["z_range"] = {
            "min_m": float(match.group(1)),
            "max_m": float(match.group(2)),
            "min_step_m": float(match.group(3)),
            "max_step_m": float(match.group(4)),
        }
        grid["z_range"]["extent_mm"] = (grid["z_range"]["max_m"] - grid["z_range"]["min_m"]) * 1000

    # Grid resolution setting
    match = re.search(r"Global and added manual grid set with frequency-specific \((\d+)MHz\) resolution: ([\d.]+) mm", content)
    if match:
        grid["frequency_mhz"] = int(match.group(1))
        grid["resolution_mm"] = float(match.group(2))

    return grid


def _extract_boundary_info(content: str) -> dict[str, Any]:
    """Extract boundary condition information."""
    boundaries = {}

    # Extract PML layers for each side
    sides = ["X-", "X+", "Y-", "Y+", "Z-", "Z+"]
    boundaries["pml_layers"] = {}

    for side in sides:
        match = re.search(rf"Side {re.escape(side)}: ABC \(UPML, (\d+) layers\)", content)
        if match:
            boundaries["pml_layers"][side] = int(match.group(1))

    # Global boundary type
    match = re.search(r"Setting global boundary conditions to: (\w+)", content)
    if match:
        boundaries["type"] = match.group(1)

    # PML strength
    match = re.search(r"Setting PML strength to: (\w+)", content)
    if match:
        boundaries["pml_strength"] = match.group(1)

    return boundaries


def _extract_materials_info(content: str) -> dict[str, Any]:
    """Extract materials information."""
    materials = {}

    # Total number of materials
    match = re.search(r"Materials \((\d+)\):", content)
    if match:
        materials["total_count"] = int(match.group(1))

    # Count material types
    dielectric_count = len(re.findall(r": dielectric \(eps_r=", content))
    lossy_metal_count = len(re.findall(r": lossy metal \(eps_r=", content))

    materials["dielectric_count"] = dielectric_count
    materials["lossy_metal_count"] = lossy_metal_count

    # Extract tissue names (from Eartha phantom)
    tissue_pattern = re.findall(r"(\w+(?:_\w+)*)\s+\(Eartha\): (\w+)", content)
    materials["tissues"] = [{"name": t[0], "type": t[1]} for t in tissue_pattern]
    materials["tissue_count"] = len(materials["tissues"])

    # Extract antenna materials
    antenna_pattern = re.findall(r"([\w:]+)\s+\(Antenna[^)]+\): (\w+)", content)
    materials["antenna_components"] = [{"name": a[0], "type": a[1]} for a in antenna_pattern]

    return materials


def _extract_solver_info(content: str) -> dict[str, Any]:
    """Extract solver configuration information."""
    solver = {}

    # Solver type
    match = re.search(r"Solver type: (\w+), (\w+), (\w+)", content)
    if match:
        solver["type"] = match.group(1)
        solver["precision"] = match.group(2)
        solver["accelerator"] = match.group(3)

    # Solver kernel
    match = re.search(r"Solver kernel set to: ([^\[]+)", content)
    if match:
        solver["kernel"] = match.group(1).strip()

    # Acceleware version
    match = re.search(r"Used Acceleware library is '([^']+)'", content)
    if match:
        solver["acceleware_version"] = match.group(1)

    # iSolve version
    match = re.search(r"iSolve X, Version ([\d.]+) \((\d+)\)", content)
    if match:
        solver["isolve_version"] = match.group(1)
        solver["isolve_build"] = int(match.group(2))

    # Floating point precision
    match = re.search(r"Floating Point Arithmetic: (\w+) \((\d+) Bytes\)", content)
    if match:
        solver["float_type"] = match.group(1)
        solver["float_bytes"] = int(match.group(2))

    # Time step
    match = re.search(r"Simulation Time Step:\s+([\d.e+-]+) sec", content)
    if match:
        solver["time_step_s"] = float(match.group(1))

    # Number of iterations
    match = re.search(r"Simulation Iterations:\s+(\d+)", content)
    if match:
        solver["iterations"] = int(match.group(1))

    # Max simulated time
    match = re.search(r"Max Simulated Time:\s+([\d.e+-]+) sec", content)
    if match:
        solver["max_simulated_time_s"] = float(match.group(1))

    # Simulation time in periods
    match = re.search(r"Simulation time set to ([\d.]+) periods", content)
    if match:
        solver["simulation_periods"] = float(match.group(1))

    return solver


def _extract_timing_info(content: str) -> dict[str, Any]:
    """Extract timing information."""
    timing = {}

    # Total simulation wall clock time
    match = re.search(r"took (\d+):(\d+):(\d+) wall clock time", content)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        timing["total_wall_clock_s"] = hours * 3600 + minutes * 60 + seconds
        timing["total_wall_clock_formatted"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # Subtask timings
    subtask_pattern = re.findall(r"Subtask '(\w+)' done in ([\d.]+)s", content)
    timing["subtasks"] = {task: float(time) for task, time in subtask_pattern}

    # Phase timings
    phase_pattern = re.findall(r"--- Finished: (\w+) \(took ([\d.]+)s\)", content)
    timing["phases"] = {phase: float(time) for phase, time in phase_pattern}

    # Elapsed times for specific operations
    elapsed_pattern = re.findall(r"Elapsed time for '([^']+)' was (\d+):(\d+):(\d+)", content)
    timing["operations"] = {}
    for op, h, m, s in elapsed_pattern:
        total_s = int(h) * 3600 + int(m) * 60 + int(s)
        timing["operations"][op] = total_s

    return timing


def _extract_hardware_info(content: str) -> dict[str, Any]:
    """Extract hardware information."""
    hardware = {}

    # OS
    match = re.search(r"Host OS: (.+)", content)
    if match:
        hardware["os"] = match.group(1).strip()

    # CPU
    match = re.search(r"Host CPU: (.+)", content)
    if match:
        hardware["cpu"] = match.group(1).strip()

    # System RAM
    match = re.search(r"Installed system RAM visible to this process:\s+([\d.]+) GB", content)
    if match:
        hardware["system_ram_gb"] = float(match.group(1))

    match = re.search(r"Host memory: (\d+) MB", content)
    if match:
        hardware["host_memory_mb"] = int(match.group(1))

    # GPU
    match = re.search(r"(NVIDIA [^,]+) \(device ID = (\d+)\), compute capability ([\d.]+), total memory (\d+) MB", content)
    if match:
        hardware["gpu"] = {
            "name": match.group(1),
            "device_id": int(match.group(2)),
            "compute_capability": match.group(3),
            "memory_mb": int(match.group(4)),
        }

    # Peak memory usage
    match = re.search(r"Peak CPU memory usage:\s+([\d.]+) GB \((\d+) Bytes\)", content)
    if match:
        hardware["peak_memory_gb"] = float(match.group(1))
        hardware["peak_memory_bytes"] = int(match.group(2))

    # MPI processes
    match = re.search(r"Running MPI version ([\d.]+) on (\d+) process", content)
    if match:
        hardware["mpi_version"] = match.group(1)
        hardware["mpi_processes"] = int(match.group(2))

    # Number of threads
    match = re.search(r"using (\d+) threads", content)
    if match:
        hardware["threads"] = int(match.group(1))

    return hardware


def _extract_simulation_info(content: str) -> dict[str, Any]:
    """Extract simulation configuration information."""
    simulation = {}

    # Frequency
    match = re.search(r"Trusted frequency is (\d+) MHz", content)
    if match:
        simulation["frequency_mhz"] = int(match.group(1))

    # Excitation signal
    match = re.search(r"Excitation signal: (.+)", content)
    if match:
        simulation["excitation_signal"] = match.group(1).strip()

    # Harmonic frequency and ramp time
    match = re.search(r"Harmonic signal with frequency (\d+) MHz and ramp time ([\d.]+) ns", content)
    if match:
        simulation["harmonic_frequency_mhz"] = int(match.group(1))
        simulation["ramp_time_ns"] = float(match.group(2))

    # Simulation time multiplier
    match = re.search(r"Using simulation time multiplier: ([\d.]+)", content)
    if match:
        simulation["time_multiplier"] = float(match.group(1))

    # Placement info
    match = re.search(r"--- Starting Placement: (\w+) - (\w+) - (\w+) ---", content)
    if match:
        simulation["placement"] = {
            "position": match.group(1),
            "side": match.group(2),
            "orientation": match.group(3),
        }

    # Bounding box setting
    match = re.search(r"Bounding box setting: '(\w+)'", content)
    if match:
        simulation["bounding_box_setting"] = match.group(1)

    return simulation


def _extract_edge_statistics(content: str) -> dict[str, Any]:
    """Extract edge statistics."""
    edges = {}

    # Total edges calculated
    match = re.search(r"Update coefficient calculation for (\d+) edges", content)
    if match:
        edges["total_edges"] = int(match.group(1))

    # Edge-Material Statistics
    match = re.search(r"Edge-Material Statistics \(Electric/Magnetic\):", content)
    if match:
        # Total
        total_match = re.search(r"(\d+) / (\d+)\s+\([^)]+\) : Total", content)
        if total_match:
            edges["electric_total"] = int(total_match.group(1))
            edges["magnetic_total"] = int(total_match.group(2))

        # Dielectric
        diel_match = re.search(r"(\d+) / (\d+)\s+\(\s*([\d.]+)% /\s*([\d.]+)%\) : Dielectric", content)
        if diel_match:
            edges["dielectric"] = {
                "electric": int(diel_match.group(1)),
                "magnetic": int(diel_match.group(2)),
                "electric_pct": float(diel_match.group(3)),
                "magnetic_pct": float(diel_match.group(4)),
            }

        # Lossy Metal
        metal_match = re.search(r"(\d+) /\s+(\d+)\s+\(\s*([\d.]+)% /\s*([\d.]+)%\) : Lossy Metal", content)
        if metal_match:
            edges["lossy_metal"] = {
                "electric": int(metal_match.group(1)),
                "magnetic": int(metal_match.group(2)),
                "electric_pct": float(metal_match.group(3)),
                "magnetic_pct": float(metal_match.group(4)),
            }

    # Update coefficient database
    match = re.search(r"Update coefficient database contains (\d+) E-coefficient\(s\) and (\d+) H-coefficient\(s\)", content)
    if match:
        edges["e_coefficients"] = int(match.group(1))
        edges["h_coefficients"] = int(match.group(2))

    return edges


def _extract_sensor_info(content: str) -> dict[str, Any]:
    """Extract sensor information."""
    sensors = {}

    # Number of sensors
    match = re.search(r"Sensors \((\d+)\):", content)
    if match:
        sensors["count"] = int(match.group(1))

    # Sensor types
    sensors["types"] = []

    if "path sensor" in content:
        sensors["types"].append("path")
    if "field sensor" in content:
        sensors["types"].append("field")
    if "point sensor" in content:
        sensors["types"].append("point")

    # DFT conversion
    if "Using DFT to convert to frequency domain" in content:
        sensors["dft_enabled"] = True

    return sensors


def _extract_source_info(content: str) -> dict[str, Any]:
    """Extract source information."""
    sources = {}

    # Number of sources
    match = re.search(r"Sources \((\d+)\):", content)
    if match:
        sources["count"] = int(match.group(1))

    # Source type
    if "Using Harmonic source" in content:
        sources["type"] = "Harmonic"
    elif "Using Gaussian source" in content:
        sources["type"] = "Gaussian"

    # Edge source details
    match = re.search(r"edge source ([^(]+) \(amplitude (\d+), time shift([\d.]+), type (\w+)", content)
    if match:
        sources["edge_source"] = {
            "name": match.group(1).strip(),
            "amplitude": int(match.group(2)),
            "time_shift": float(match.group(3)),
            "voltage_type": match.group(4),
        }

    # Lumped elements
    match = re.search(r"Lumped Elements \((\d+)\):", content)
    if match:
        sources["lumped_elements_count"] = int(match.group(1))

    match = re.search(r"Resistor, (\d+) ohm", content)
    if match:
        sources["resistor_ohm"] = int(match.group(1))

    return sources


def _extract_results_info(content: str) -> dict[str, Any]:
    """Extract results information."""
    results = {}

    # Power balance
    match = re.search(r"Final Balance: ([\d.]+)%", content)
    if match:
        results["power_balance_pct"] = float(match.group(1))

    # SAR results path
    match = re.search(r"SAR results saved to: (.+\.json)", content)
    if match:
        results["sar_results_path"] = match.group(1).strip()

    # Success status
    results["success"] = "FDTD simulation finished successfully" in content
    results["isolve_success"] = "iSolve ended successfully" in content

    return results


def _compute_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    """Compute summary statistics from extracted metrics."""
    summary = {}

    # Grid summary
    if "grid" in metrics and "total_cells" in metrics["grid"]:
        summary["total_cells"] = metrics["grid"]["total_cells"]
        summary["total_mcells"] = metrics["grid"]["total_mcells"]

    if "grid" in metrics and "total_cells_with_pml" in metrics["grid"]:
        summary["total_cells_with_pml"] = metrics["grid"]["total_cells_with_pml"]

    # Edge summary
    if "edges" in metrics and "total_edges" in metrics["edges"]:
        summary["total_edges"] = metrics["edges"]["total_edges"]

    # Material summary
    if "materials" in metrics:
        summary["total_materials"] = metrics["materials"].get("total_count", 0)
        summary["total_tissues"] = metrics["materials"].get("tissue_count", 0)

    # Solver summary
    if "solver" in metrics:
        summary["iterations"] = metrics["solver"].get("iterations", 0)
        summary["time_step_fs"] = metrics["solver"].get("time_step_s", 0) * 1e15  # femtoseconds

    # Compute total cell-iterations (the big "wow" number)
    cells_with_pml = metrics.get("grid", {}).get("total_cells_with_pml", 0)
    iterations = metrics.get("solver", {}).get("iterations", 0)
    if cells_with_pml and iterations:
        total_cell_iterations = cells_with_pml * iterations
        summary["total_cell_iterations"] = total_cell_iterations
        summary["total_cell_iterations_billions"] = total_cell_iterations / 1e9
        summary["total_cell_iterations_trillions"] = total_cell_iterations / 1e12

    # Timing summary
    if "timing" in metrics:
        summary["total_time_s"] = metrics["timing"].get("total_wall_clock_s", 0)

    # Performance - calculate average MCells/s from progress updates
    progress_pattern = re.findall(r"@ ([\d.]+) MCells/s", metrics.get("_content", ""))
    if progress_pattern:
        speeds = [float(s) for s in progress_pattern]
        summary["avg_mcells_per_s"] = sum(speeds) / len(speeds)
        summary["peak_mcells_per_s"] = max(speeds)
        summary["min_mcells_per_s"] = min(speeds)

    return summary


def parse_and_save(log_path: str | Path, output_path: str | Path | None = None) -> Path:
    """
    Parse a verbose.log file and save metrics to JSON.

    Args:
        log_path: Path to the verbose.log file
        output_path: Optional output path for JSON. Defaults to same directory as log.

    Returns:
        Path to the saved JSON file
    """
    log_path = Path(log_path)

    if output_path is None:
        output_path = log_path.parent / "simulation_metrics.json"
    else:
        output_path = Path(output_path)

    metrics = parse_verbose_log(log_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    print(f"Metrics saved to: {output_path}")
    return output_path


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(description="Parse verbose.log files to extract simulation metrics")
    parser.add_argument("log_path", type=str, help="Path to the verbose.log file")
    parser.add_argument(
        "-o", "--output", type=str, default=None, help="Output path for JSON file (default: simulation_metrics.json in same directory)"
    )
    parser.add_argument("--pretty", action="store_true", help="Print metrics to console in pretty format")

    args = parser.parse_args()

    output_path = parse_and_save(args.log_path, args.output)

    if args.pretty:
        with open(output_path, "r") as f:
            metrics = json.load(f)
        print("\n" + "=" * 60)
        print("SIMULATION METRICS SUMMARY")
        print("=" * 60)

        if "summary" in metrics:
            for key, value in metrics["summary"].items():
                print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
