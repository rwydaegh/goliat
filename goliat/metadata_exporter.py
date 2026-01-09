"""
Simulation Metadata Exporter.

Exports comprehensive simulation metadata to pickle and JSON files at the
end of extraction. Captures timing data, performance metrics, file sizes,
and grid information for post-hoc analysis.
"""

import glob
import json
import logging
import os
import pickle
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .profiler import Profiler


@dataclass
class TimingBreakdown:
    """Breakdown of timing data for a single phase."""

    phase_name: str
    avg_time_s: float
    total_time_s: float
    num_executions: int
    subtasks: dict[str, float] = field(default_factory=dict)


@dataclass
class SolverInfo:
    """Solver configuration and simulation parameters."""

    iterations: Optional[int] = None
    time_step_s: Optional[float] = None
    grid_resolution_mm: Optional[float] = None
    total_cell_iterations: Optional[int] = None
    power_balance_pct: Optional[float] = None
    total_edges: Optional[int] = None


@dataclass
class HardwareInfo:
    """Hardware configuration used for simulation."""

    gpu_model: Optional[str] = None
    gpu_memory_mb: Optional[int] = None
    peak_memory_gb: Optional[float] = None


@dataclass
class PerformanceMetrics:
    """iSolve performance metrics extracted from verbose log."""

    avg_mcells_per_s: Optional[float] = None
    peak_mcells_per_s: Optional[float] = None
    min_mcells_per_s: Optional[float] = None


@dataclass
class GridInfo:
    """Grid information from simulation."""

    total_cells: Optional[int] = None
    total_mcells: Optional[float] = None
    total_cells_with_pml: Optional[int] = None
    total_mcells_with_pml: Optional[float] = None
    dimensions: Optional[dict[str, int]] = None
    dimensions_with_pml: Optional[dict[str, int]] = None


@dataclass
class FileSizeInfo:
    """File size information for key output files."""

    output_h5_bytes: Optional[int] = None
    output_h5_mb: Optional[float] = None
    sapd_h5_bytes: Optional[int] = None
    sapd_h5_mb: Optional[float] = None
    project_smash_bytes: Optional[int] = None
    project_smash_mb: Optional[float] = None


@dataclass
class SimulationMetadata:
    """Complete simulation metadata snapshot."""

    # Identification
    simulation_name: str
    study_type: str  # "near_field" or "far_field"
    phantom_name: str
    frequency_mhz: int | list[int]
    timestamp: str

    # Timing data (from profiler)
    timing: dict[str, TimingBreakdown]
    total_study_time_s: float

    # Solver configuration
    solver: SolverInfo

    # Hardware info
    hardware: HardwareInfo

    # Performance (from verbose log)
    performance: PerformanceMetrics

    # Grid info
    grid: GridInfo

    # File sizes
    file_sizes: FileSizeInfo

    # Extraction flags
    extract_sapd: bool = False

    # Additional context
    config_path: Optional[str] = None
    project_path: Optional[str] = None


class MetadataExporter:
    """Exports simulation metadata at the end of extraction."""

    def __init__(
        self,
        profiler: "Profiler",
        project_path: str,
        simulation_name: str,
        study_type: str,
        phantom_name: str,
        frequency_mhz: int | list[int],
        config_path: Optional[str] = None,
        extract_sapd: bool = False,
    ):
        """Initialize the exporter.

        Args:
            profiler: The profiler instance with timing data.
            project_path: Path to the .smash project file.
            simulation_name: Name of the simulation.
            study_type: Type of study ("near_field" or "far_field").
            phantom_name: Name of the phantom used.
            frequency_mhz: Simulation frequency in MHz.
            config_path: Path to the config file.
            extract_sapd: Whether SAPD extraction was enabled.
        """
        self.profiler = profiler
        self.project_path = project_path
        self.project_dir = os.path.dirname(project_path) if project_path else None
        self.simulation_name = simulation_name
        self.study_type = study_type
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        self.config_path = config_path
        self.extract_sapd = extract_sapd
        self.logger = logging.getLogger("progress")
        self.verbose_logger = logging.getLogger("verbose")

    def export(self) -> tuple[Optional[str], Optional[str]]:
        """Export metadata to pickle and JSON files.

        Returns:
            Tuple of (pickle_path, json_path) or (None, None) if export failed.
        """
        if not self.project_dir:
            return None, None

        try:
            metadata = self._collect_metadata()

            # Save metadata files in the project directory (same level as .smash file)
            os.makedirs(self.project_dir, exist_ok=True)

            # Export to pickle
            pickle_path = os.path.join(self.project_dir, "simulation_metadata.pkl")
            with open(pickle_path, "wb") as f:
                pickle.dump(asdict(metadata), f)

            # Export to JSON
            json_path = os.path.join(self.project_dir, "simulation_metadata.json")
            with open(json_path, "w") as f:
                json.dump(asdict(metadata), f, indent=2, default=str)

            self.logger.info("    - Metadata extraction completed.", extra={"log_type": "success"})
            return pickle_path, json_path

        except Exception as e:
            self.verbose_logger.error(f"Metadata export failed: {e}")
            return None, None

    def _collect_metadata(self) -> SimulationMetadata:
        """Collect all metadata from various sources."""
        timing = self._extract_timing_data()
        solver = self._extract_solver_info()
        hardware = self._extract_hardware_info()
        performance = self._extract_performance_metrics()
        grid = self._extract_grid_info()
        file_sizes = self._extract_file_sizes()

        total_time = sum(tb.total_time_s for tb in timing.values())

        return SimulationMetadata(
            simulation_name=self.simulation_name,
            study_type=self.study_type,
            phantom_name=self.phantom_name,
            frequency_mhz=self.frequency_mhz,
            timestamp=datetime.now().isoformat(),
            timing=timing,
            total_study_time_s=total_time,
            solver=solver,
            hardware=hardware,
            performance=performance,
            grid=grid,
            file_sizes=file_sizes,
            extract_sapd=self.extract_sapd,
            config_path=self.config_path,
            project_path=self.project_path,
        )

    def _extract_timing_data(self) -> dict[str, TimingBreakdown]:
        """Extract timing breakdown from profiler.

        This mirrors the data structure used by PieChartsManager for the GUI.
        """
        timing = {}

        for phase in ["setup", "run", "extract"]:
            avg_time = self.profiler.profiling_config.get(f"avg_{phase}_time", 0.0)
            times = self.profiler.subtask_times.get(phase, [])
            total_time = sum(times)
            num_executions = len(times)

            # Extract subtasks for this phase
            subtasks = {}
            for key, value in self.profiler.profiling_config.items():
                if key.startswith(f"avg_{phase}_") and key != f"avg_{phase}_time":
                    subtask_name = key.replace(f"avg_{phase}_", "")
                    # Skip fake aggregated entries (same logic as PieChartsManager)
                    if subtask_name not in ["simulation", "simulation_total", "results_total"]:
                        subtasks[subtask_name] = value

            timing[phase] = TimingBreakdown(
                phase_name=phase,
                avg_time_s=avg_time,
                total_time_s=total_time,
                num_executions=num_executions,
                subtasks=subtasks,
            )

        return timing

    def _extract_solver_info(self) -> SolverInfo:
        """Extract solver configuration from verbose.log if available."""
        if not self.project_dir:
            return SolverInfo()

        verbose_log_path = os.path.join(self.project_dir, "verbose.log")
        if not os.path.exists(verbose_log_path):
            return SolverInfo()

        try:
            from goliat.analysis.parse_verbose_log import parse_verbose_log

            metrics = parse_verbose_log(verbose_log_path)
            solver_data = metrics.get("solver", {})
            edges_data = metrics.get("edges", {})
            results_data = metrics.get("results", {})
            grid_data = metrics.get("grid", {})

            # Compute total cell-iterations
            cells_with_pml = grid_data.get("total_cells_with_pml")
            iterations = solver_data.get("iterations")
            total_cell_iterations = None
            if cells_with_pml and iterations:
                total_cell_iterations = cells_with_pml * iterations

            return SolverInfo(
                iterations=iterations,
                time_step_s=solver_data.get("time_step_s"),
                grid_resolution_mm=grid_data.get("resolution_mm"),
                total_cell_iterations=total_cell_iterations,
                power_balance_pct=results_data.get("power_balance_pct"),
                total_edges=edges_data.get("total_edges"),
            )
        except Exception:
            return SolverInfo()

    def _extract_hardware_info(self) -> HardwareInfo:
        """Extract hardware information from verbose.log if available."""
        if not self.project_dir:
            return HardwareInfo()

        verbose_log_path = os.path.join(self.project_dir, "verbose.log")
        if not os.path.exists(verbose_log_path):
            return HardwareInfo()

        try:
            from goliat.analysis.parse_verbose_log import parse_verbose_log

            metrics = parse_verbose_log(verbose_log_path)
            hardware_data = metrics.get("hardware", {})
            gpu_data = hardware_data.get("gpu", {})

            return HardwareInfo(
                gpu_model=gpu_data.get("name"),
                gpu_memory_mb=gpu_data.get("memory_mb"),
                peak_memory_gb=hardware_data.get("peak_memory_gb"),
            )
        except Exception:
            return HardwareInfo()

    def _extract_performance_metrics(self) -> PerformanceMetrics:
        """Extract performance metrics from verbose.log if available."""
        if not self.project_dir:
            return PerformanceMetrics()

        verbose_log_path = os.path.join(self.project_dir, "verbose.log")
        if not os.path.exists(verbose_log_path):
            return PerformanceMetrics()

        try:
            # Import the parse function
            from goliat.analysis.parse_verbose_log import parse_verbose_log

            metrics = parse_verbose_log(verbose_log_path)
            summary = metrics.get("summary", {})

            return PerformanceMetrics(
                avg_mcells_per_s=summary.get("avg_mcells_per_s"),
                peak_mcells_per_s=summary.get("peak_mcells_per_s"),
                min_mcells_per_s=summary.get("min_mcells_per_s"),
            )
        except Exception:
            return PerformanceMetrics()

    def _extract_grid_info(self) -> GridInfo:
        """Extract grid information from verbose.log if available."""
        if not self.project_dir:
            return GridInfo()

        verbose_log_path = os.path.join(self.project_dir, "verbose.log")
        if not os.path.exists(verbose_log_path):
            return GridInfo()

        try:
            from goliat.analysis.parse_verbose_log import parse_verbose_log

            metrics = parse_verbose_log(verbose_log_path)
            grid_data = metrics.get("grid", {})

            return GridInfo(
                total_cells=grid_data.get("total_cells"),
                total_mcells=grid_data.get("total_mcells"),
                total_cells_with_pml=grid_data.get("total_cells_with_pml"),
                total_mcells_with_pml=grid_data.get("total_mcells_with_pml"),
                dimensions=grid_data.get("dimensions"),
                dimensions_with_pml=grid_data.get("dimensions_with_pml"),
            )
        except Exception:
            return GridInfo()

    def _extract_file_sizes(self) -> FileSizeInfo:
        """Extract file sizes for key output files."""
        if not self.project_dir:
            return FileSizeInfo()

        # Sim4Life typically puts results in a folder named {project_name}_Results
        # but sometimes files might be in the project dir or a generic Results folder.
        project_filename = os.path.basename(self.project_path) if self.project_path else ""
        s4l_results_dir = os.path.join(self.project_dir, project_filename + "_Results")
        generic_results_dir = os.path.join(self.project_dir, "Results")

        info = FileSizeInfo()

        # We'll search in all plausible locations
        search_dirs = [self.project_dir, s4l_results_dir, generic_results_dir]

        # Clean up search dirs (remove non-existent ones)
        search_dirs = [d for d in search_dirs if d and os.path.exists(d)]

        # Debug logging for troubleshooting (hidden from standard progress log)
        self.verbose_logger.debug(f"Searching for output files in: {search_dirs}")

        # _Output.h5 files
        output_h5_files = []
        for d in search_dirs:
            matches = glob.glob(os.path.join(d, "*_Output.h5"))
            output_h5_files.extend(matches)

        if output_h5_files:
            # Take the largest one (there should typically be only one)
            largest_h5 = max(output_h5_files, key=os.path.getsize)
            info.output_h5_bytes = os.path.getsize(largest_h5)
            info.output_h5_mb = info.output_h5_bytes / (1024 * 1024)
            self.verbose_logger.debug(f"Found largest Output.h5: {largest_h5} ({info.output_h5_mb:.2f} MB)")
        else:
            self.verbose_logger.debug("No *_Output.h5 files found.")

        # Project .smash file
        if self.project_path and os.path.exists(self.project_path):
            info.project_smash_bytes = os.path.getsize(self.project_path)
            info.project_smash_mb = info.project_smash_bytes / (1024 * 1024)
            self.verbose_logger.debug(f"Measured project file: {self.project_path} ({info.project_smash_mb:.2f} MB)")
        else:
            self.verbose_logger.debug(f"Project file not found at: {self.project_path}")

        return info


def export_simulation_metadata(
    profiler: "Profiler",
    project_path: str,
    simulation_name: str,
    study_type: str,
    phantom_name: str,
    frequency_mhz: int | list[int],
    config_path: Optional[str] = None,
    extract_sapd: bool = False,
) -> tuple[Optional[str], Optional[str]]:
    """Convenience function to export simulation metadata.

    Args:
        profiler: The profiler instance with timing data.
        project_path: Path to the .smash project file.
        simulation_name: Name of the simulation.
        study_type: Type of study ("near_field" or "far_field").
        phantom_name: Name of the phantom used.
        frequency_mhz: Simulation frequency in MHz.
        config_path: Path to the config file.
        extract_sapd: Whether SAPD extraction was enabled.

    Returns:
        Tuple of (pickle_path, json_path) or (None, None) if export failed.
    """
    exporter = MetadataExporter(
        profiler=profiler,
        project_path=project_path,
        simulation_name=simulation_name,
        study_type=study_type,
        phantom_name=phantom_name,
        frequency_mhz=frequency_mhz,
        config_path=config_path,
        extract_sapd=extract_sapd,
    )
    return exporter.export()
