from unittest.mock import MagicMock, patch

import pytest

# Since this is a GUI component, we will only write basic tests.
# We will mock the PySide6 dependencies.


@pytest.fixture
def mock_pyside():
    """Mock PySide6 dependencies to avoid GUI instantiation."""
    mocks = {
        "PySide6.QtWidgets": MagicMock(),
        "PySide6.QtCore": MagicMock(),
        "PySide6.QtGui": MagicMock(),
    }
    with patch.dict("sys.modules", mocks):
        yield


@pytest.mark.skip_on_ci
def test_progress_gui_initialization(mock_pyside):
    from src.gui_manager import ProgressGUI

    mock_queue = MagicMock()
    mock_stop_event = MagicMock()
    mock_process = MagicMock()

    # This test will only check if the GUI can be initialized without errors.
    # More complex GUI testing is out of scope.
    try:
        gui = ProgressGUI(mock_queue, mock_stop_event, mock_process)
        assert gui is not None
    except Exception as e:
        pytest.fail(f"ProgressGUI initialization failed: {e}")
