from colorama import Fore, Style

# Define a mapping from a log type to a color.
# This provides a single point of control for all terminal colors.
COLOR_MAP = {
    "default": Fore.WHITE,
    "progress": Fore.GREEN,
    "info": Fore.CYAN,
    "verbose": Fore.BLUE,
    "warning": Fore.YELLOW,
    "error": Fore.RED,
    "fatal": Fore.MAGENTA,
    "success": Fore.GREEN + Style.BRIGHT,
    "header": Fore.MAGENTA + Style.BRIGHT,
    "highlight": Fore.YELLOW + Style.BRIGHT,
}


def get_color(log_type: str) -> str:
    """Retrieves the colorama color code for a given log type.

    Args:
        log_type: The type of log message (e.g., 'info', 'warning').

    Returns:
        The colorama color code for the log type.
    """
    return COLOR_MAP.get(log_type, Fore.WHITE)
