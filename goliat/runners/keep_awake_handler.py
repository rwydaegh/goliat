"""Handler for keep_awake script triggering."""

import os
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Config


class KeepAwakeHandler:
    """Handles keep_awake script triggering."""

    def __init__(self, config: "Config"):
        """Initialize keep_awake handler.

        Args:
            config: Configuration object.
        """
        self.config = config
        self.triggered = False

    def trigger_before_retry(self) -> None:
        """Trigger keep_awake before retry attempt."""
        if not (self.config["keep_awake"] or False):
            return

        try:
            # Path: goliat/goliat/runners/keep_awake_handler.py -> goliat/goliat/utils/scripts/
            script_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "utils", "scripts")
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            from keep_awake import keep_awake  # type: ignore

            keep_awake()
        except Exception as e:
            print(f"Warning: keep_awake() failed: {e}")
            if sys.stdout is not None:
                sys.stdout.flush()

    def trigger_on_progress(self) -> None:
        """Trigger keep_awake script on first progress update."""
        if not (self.config["keep_awake"] or False):
            return

        if self.triggered:
            return

        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "utils", "scripts", "keep_awake.py")
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path])
        self.triggered = True

    def reset(self) -> None:
        """Reset triggered flag (for new simulation)."""
        self.triggered = False
