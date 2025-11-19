"""Abstract base class for simulation execution strategies."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import s4l_v1.simulation.emfdtd

    from ..config import Config
    from ..gui_manager import QueueGUI
    from ..profiler import Profiler
    from ..project_manager import ProjectManager
    from ..logging_manager import LoggingMixin


class ExecutionStrategy(ABC):
    """Abstract base class for simulation execution strategies."""

    def __init__(
        self,
        config: "Config",
        project_path: str,
        simulation: "s4l_v1.simulation.emfdtd.Simulation",
        profiler: "Profiler",
        verbose_logger: "LoggingMixin",
        progress_logger: "LoggingMixin",
        project_manager: "ProjectManager",
        gui: "QueueGUI | None" = None,
    ):
        """Initialize execution strategy.

        Args:
            config: Configuration object.
            project_path: Path to the Sim4Life project file.
            simulation: The simulation object to run.
            profiler: Profiler for timing subtasks.
            verbose_logger: Logger for detailed output.
            progress_logger: Logger for high-level updates.
            project_manager: ProjectManager instance.
            gui: Optional GUI proxy for updates.
        """
        self.config = config
        self.project_path = project_path
        self.simulation = simulation
        self.profiler = profiler
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        self.project_manager = project_manager
        self.gui = gui

    @abstractmethod
    def run(self) -> None:
        """Execute the simulation using this strategy.

        Raises:
            StudyCancelledError: If execution is cancelled by user.
            RuntimeError: If execution fails.
            FileNotFoundError: If required files are missing.
        """
        pass

    def _check_for_stop_signal(self) -> None:
        """Check for stop signal and raise if requested."""
        from ..utils import StudyCancelledError

        if self.gui and self.gui.is_stopped():
            raise StudyCancelledError("Study cancelled by user.")
