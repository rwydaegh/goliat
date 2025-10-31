"""Main GUI manager module."""

# Re-export QueueGUI for backward compatibility
from goliat.gui.queue_gui import QueueGUI
from goliat.gui.progress_gui import ProgressGUI

__all__ = ["QueueGUI", "ProgressGUI"]
