"""Status management for GUI: colors, counting, and formatting."""


class StatusManager:
    """Manages status colors, counting, and message formatting for GUI.

    Handles color mapping for different log types (info, warning, error, etc.),
    counts warnings and errors for display in error summary, and formats
    messages with HTML color styling for the QTextEdit widget.

    Note: Uses white for 'progress' messages in GUI (unlike terminal colors)
    because all messages shown here are progress updates. This improves
    readability in the dark-themed GUI.
    """

    def __init__(self) -> None:
        """Initializes status manager with default counters and color map."""
        self.warning_count: int = 0
        self.error_count: int = 0

        # Color mapping - NOTE: Intentionally using white for "progress" in GUI
        # since all messages shown here are progress updates. This deviates from
        # the terminal color scheme defined in goliat/colors.py for better readability.
        self.color_map: dict[str, str] = {
            "default": "#f0f0f0",  # WHITE
            "progress": "#f0f0f0",  # WHITE (GUI-specific override)
            "info": "#17a2b8",  # CYAN
            "verbose": "#007acc",  # BLUE
            "warning": "#ffc107",  # YELLOW
            "error": "#dc3545",  # RED
            "fatal": "#d63384",  # MAGENTA
            "success": "#5cb85c",  # BRIGHT GREEN
            "header": "#e83e8c",  # BRIGHT MAGENTA
            "highlight": "#ffd700",  # BRIGHT YELLOW
            "caller": "#6c757d",  # DIM (gray)
        }

    def get_color(self, log_type: str) -> str:
        """Gets HTML color code for a log type.

        Args:
            log_type: Type of log message.

        Returns:
            HTML color code (hex).
        """
        return self.color_map.get(log_type, "#f0f0f0")

    def format_message(self, message: str, log_type: str = "default") -> str:
        """Formats message with HTML color styling.

        Preserves leading spaces by converting them to &nbsp; entities, then
        wraps message in a <span> tag with appropriate color style.

        Args:
            message: Message text to format.
            log_type: Log type for color selection.

        Returns:
            HTML-formatted message string ready for QTextEdit.
        """
        # Preserve leading spaces by converting them to &nbsp;
        preserved_message = message.replace(" ", "&nbsp;")
        color = self.get_color(log_type)
        return f'<span style="color:{color};">{preserved_message}</span>'

    def record_log(self, log_type: str) -> None:
        """Records log entry and updates warning/error counters.

        Args:
            log_type: Type of log message.
        """
        if log_type == "warning":
            self.warning_count += 1
        elif log_type in ["error", "fatal"]:
            self.error_count += 1

    def get_error_summary(self, web_connected: bool = False) -> str:
        """Gets formatted summary of warnings and errors with optional web status.

        Args:
            web_connected: Whether web dashboard is connected (optional).

        Returns:
            Formatted string with emoji indicators and counts.
        """
        web_status = "🟢" if web_connected else "🔴"
        return f"⚠️ Warnings: {self.warning_count} | ❌ Errors: {self.error_count} | {web_status} Web"
