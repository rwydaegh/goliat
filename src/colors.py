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
    Returns the color for a given log type.
    Defaults to white if the type is not found.
    """
    return COLOR_MAP.get(log_type, Fore.WHITE)