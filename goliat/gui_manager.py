"""Main GUI manager module."""

# Re-export QueueGUI for backward compatibility
# Handle missing PySide6 gracefully in CI/test environments
try:
    from goliat.gui.queue_gui import QueueGUI
except ImportError:
    QueueGUI = None

try:
    from goliat.gui.progress_gui import ProgressGUI
except (ImportError, ModuleNotFoundError):
    # In CI/test environments where PySide6 is not available
    ProgressGUI = None

__all__ = ["QueueGUI", "ProgressGUI"]
