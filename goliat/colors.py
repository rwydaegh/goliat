import os

from colorama import Fore, Style, init

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
    "caller": Fore.BLACK + Style.DIM,
}


def init_colorama():
    """Initialize colorama with appropriate settings for the current environment.

    Preserves ANSI codes when stdout is piped (e.g., in Jupyter notebooks)
    by checking for JUPYTER_NOTEBOOK or COLORAMA_STRIP environment variables.
    """
    # Preserve ANSI codes when stdout is piped (e.g., in Jupyter notebooks)
    strip_codes = os.environ.get("COLORAMA_STRIP", "").lower() == "0" or os.environ.get("JUPYTER_NOTEBOOK", "").lower() == "1"
    init(autoreset=True, strip=not strip_codes, convert=False if strip_codes else True)


def get_color(log_type: str) -> str:
    """Returns the colorama color code for a log type, or white if not found.

    Args:
        log_type: Log type key (e.g., 'info', 'warning', 'error').

    Returns:
        Colorama color code string.
    """
    return COLOR_MAP.get(log_type, Fore.WHITE)
