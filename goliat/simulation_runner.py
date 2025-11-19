import atexit
import traceback
from typing import TYPE_CHECKING, Optional, Set

from .logging_manager import LoggingMixin
from .runners.execution_strategy import ExecutionStrategy
from .runners.isolve_manual_strategy import ISolveManualStrategy
from .runners.osparc_direct_strategy import OSPARCDirectStrategy
from .runners.sim4life_api_strategy import Sim4LifeAPIStrategy

# Global registry to track active SimulationRunner instances for cleanup
_active_runners: Set["SimulationRunner"] = set()


def _cleanup_all_runners():
    """Cleanup function registered with atexit to ensure all runners clean up their subprocesses."""
    for runner in list(_active_runners):
        try:
            runner._cleanup_isolve_process()
        except Exception:
            pass  # Ignore errors during cleanup


# Register cleanup handler to run on process exit
atexit.register(_cleanup_all_runners)

if TYPE_CHECKING:
    from logging import Logger

    import s4l_v1.simulation.emfdtd

    from .config import Config
    from .gui_manager import QueueGUI
    from .profiler import Profiler
    from .project_manager import ProjectManager


class SimulationRunner(LoggingMixin):
    """Manages simulation execution via the Sim4Life API or iSolve.exe."""

    def __init__(
        self,
        config: "Config",
        project_path: str,
        simulation: "s4l_v1.simulation.emfdtd.Simulation",
        profiler: "Profiler",
        verbose_logger: "Logger",
        progress_logger: "Logger",
        project_manager: "ProjectManager",
        gui: "Optional[QueueGUI]" = None,
    ):
        """Sets up the simulation runner.

        Args:
            config: Configuration object.
            project_path: Path to the Sim4Life project file.
            simulation: The simulation object to run.
            profiler: Profiler for timing subtasks.
            verbose_logger: Logger for detailed output.
            progress_logger: Logger for high-level updates.
            gui: Optional GUI proxy for updates.
            project_manager: ProjectManager instance. Uses its save() method.
        """
        self.config = config
        self.project_path = project_path
        self.simulation = simulation
        self.profiler = profiler
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        self.gui = gui
        self.project_manager = project_manager
        import s4l_v1.document

        self.document = s4l_v1.document
        self.current_strategy: Optional["ExecutionStrategy"] = None  # Track current execution strategy
        _active_runners.add(self)  # Register this instance for global cleanup

    def run(self):
        """Runs the simulation using the configured execution method.

        Writes input file first, then runs via Sim4Life API, manual iSolve,
        or oSPARC depending on config. Handles errors and provides helpful
        messages for common issues.
        """
        if not self.simulation:
            self._log(
                "ERROR: Simulation object not found. Cannot run simulation.",
                level="progress",
                log_type="error",
            )
            return
        self._log(f"Running simulation: {self.simulation.Name}", log_type="verbose")

        server_name = (self.config["solver_settings"] or {}).get("server")

        try:
            if hasattr(self.simulation, "WriteInputFile"):
                self._log(
                    "    - Write input file...",
                    level="progress",
                    log_type="progress",
                )
                with self.profiler.subtask("run_write_input_file"):
                    self.simulation.WriteInputFile()
                    # Force a save to flush files
                    self.project_manager.save()
                elapsed = self.profiler.subtask_times["run_write_input_file"][-1]
                self._log(f"      - Subtask 'run_write_input_file' done in {elapsed:.2f}s", log_type="verbose")
                self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

            # Stop here if we only want to write the input file
            if self.config.get_only_write_input_file():
                self._log(
                    "'only_write_input_file' is true, skipping simulation run.",
                    level="progress",
                    log_type="info",
                )
                return

            # Select and execute appropriate strategy
            strategy = self._create_execution_strategy(server_name)
            self.current_strategy = strategy
            try:
                strategy.run()
            finally:
                self.current_strategy = None

        except Exception as e:
            self._log(
                f"An error occurred during simulation run: {e}",
                level="progress",
                log_type="error",
            )
            # Check if a cloud server was intended for the run
            server_name = (self.config["solver_settings"] or {}).get("server")
            if server_name and server_name != "localhost":
                self._log(
                    "If you are running on the cloud, please ensure you are logged into Sim4Life "
                    "via the GUI and your API credentials are correct.",
                    level="progress",
                    log_type="warning",
                )
            self.verbose_logger.error(traceback.format_exc())

        return self.simulation

    def _create_execution_strategy(self, server_name: Optional[str]) -> ExecutionStrategy:
        """Create the appropriate execution strategy based on configuration.

        Args:
            server_name: Server name from config (None for localhost).

        Returns:
            ExecutionStrategy instance.
        """
        common_args = {
            "config": self.config,
            "project_path": self.project_path,
            "simulation": self.simulation,
            "profiler": self.profiler,
            "verbose_logger": self.verbose_logger,
            "progress_logger": self.progress_logger,
            "project_manager": self.project_manager,
            "gui": self.gui,
        }

        if self.config["manual_isolve"] or False:
            return ISolveManualStrategy(**common_args)
        elif server_name and "osparc" in server_name.lower():
            return OSPARCDirectStrategy(server_name=server_name, **common_args)
        else:
            server_id = self._get_server_id(server_name) if server_name else None
            return Sim4LifeAPIStrategy(server_id=server_id, **common_args)

    def _cleanup_isolve_process(self):
        """Kills the current iSolve subprocess if it's still running.

        This prevents orphaned processes when the parent process terminates.
        Should be called on cancellation, exceptions, and in finally blocks.
        Also registered with atexit to ensure cleanup on abrupt termination.
        """
        if self.current_strategy is not None and isinstance(self.current_strategy, ISolveManualStrategy):
            self.current_strategy._cleanup()

        # Remove from global registry when cleanup is done
        _active_runners.discard(self)

    def _get_server_id(self, server_name: str) -> Optional[str]:
        """Finds a matching server ID from a partial name.

        Searches available Sim4Life servers for one containing the given name.
        Returns None for localhost or if no match found.

        Args:
            server_name: Partial server name to search for.

        Returns:
            Full server identifier string, or None if not found.

        Raises:
            RuntimeError: If server name is specified but no match found.
        """
        if not server_name or server_name.lower() == "localhost":
            return None

        self._log(f"Searching for server: '{server_name}'", log_type="verbose")
        import s4l_v1.simulation

        available_servers = s4l_v1.simulation.GetAvailableServers()

        if not available_servers:
            self._log(
                "No remote servers seem to be available.",
                level="progress",
                log_type="warning",
            )
            return None

        self._log(f"Available servers: {available_servers}", log_type="verbose")

        for server in available_servers:
            if server_name.lower() in server.lower():
                self._log(
                    f"Found matching server: '{server}'",
                    level="progress",
                    log_type="info",
                )
                return server

        self._log(
            f"Server '{server_name}' not found in available servers.",
            level="progress",
            log_type="error",
        )
        raise RuntimeError(f"Server '{server_name}' not found.")
