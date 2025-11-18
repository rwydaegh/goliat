"""Execution strategy for Sim4Life API execution."""

from typing import TYPE_CHECKING

from ..logging_manager import LoggingMixin
from .execution_strategy import ExecutionStrategy

if TYPE_CHECKING:
    pass


class Sim4LifeAPIStrategy(ExecutionStrategy, LoggingMixin):
    """Execution strategy for running simulations via Sim4Life API."""

    def __init__(self, server_id: str | None, *args, **kwargs):
        """Initialize Sim4Life API strategy.

        Args:
            server_id: Server ID to use (None for localhost).
            *args: Passed to parent class.
            **kwargs: Passed to parent class.
        """
        super().__init__(*args, **kwargs)
        self.server_id = server_id

    def run(self) -> None:
        """Run simulation using Sim4Life API.

        Raises:
            RuntimeError: If simulation execution fails.
        """
        self.simulation.RunSimulation(wait=True, server_id=self.server_id)
        server_name = (self.config["solver_settings"] or {}).get("server", "localhost")
        log_msg = f"Simulation finished on '{server_name}'."
        self._log(log_msg, level="progress", log_type="success")
