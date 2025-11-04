from colorama import Fore, Style

from goliat.colors import get_color


def test_get_color():
    assert get_color("progress") == Fore.GREEN
    assert get_color("info") == Fore.CYAN
    assert get_color("warning") == Fore.YELLOW
    assert get_color("error") == Fore.RED
    assert get_color("success") == Fore.GREEN + Style.BRIGHT
    assert get_color("non_existent_type") == Fore.WHITE
