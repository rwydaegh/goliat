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


def get_color(log_type):
    """
    Retrieves the colorama color code for a given log type.

    This function looks up the log type in the global COLOR_MAP and returns the
    corresponding colorama Fore object. If the log type is not found, it defaults
    to white.

    Args:
        log_type (str): The type of log message (e.g., 'info', 'warning', 'error').

    Returns:
        str: The colorama color code for the log type.
    """
    return COLOR_MAP.get(log_type, Fore.WHITE)
