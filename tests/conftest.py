import sys
from unittest.mock import MagicMock


def pytest_configure(config):
    """
    Dynamically mock Sim4Life-specific modules to prevent ImportError during test collection
    in environments where Sim4Life is not installed.
    """
    # Create a mock for the entire s4l_v1 package
    s4l_v1 = MagicMock()

    # Create mocks for submodules that are imported directly in the source code
    s4l_v1.simulation = MagicMock()
    s4l_v1.simulation.emfdtd = MagicMock()
    s4l_v1.model = MagicMock()
    s4l_v1.document = MagicMock()
    s4l_v1.analysis = MagicMock()
    s4l_v1.units = MagicMock()

    # Insert the mock into sys.modules
    sys.modules["s4l_v1"] = s4l_v1
    sys.modules["s4l_v1.simulation"] = s4l_v1.simulation
    sys.modules["s4l_v1.simulation.emfdtd"] = s4l_v1.simulation.emfdtd
    sys.modules["s4l_v1.model"] = s4l_v1.model
    sys.modules["s4l_v1.document"] = s4l_v1.document
    sys.modules["s4l_v1.analysis"] = s4l_v1.analysis
    sys.modules["s4l_v1.units"] = s4l_v1.units

    # Mock XCoreModeling
    sys.modules["XCoreModeling"] = MagicMock()
