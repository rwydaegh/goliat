from unittest.mock import MagicMock, patch

import pytest

# Mock s4l_v1
mocks = {
    "s4l_v1": MagicMock(),
    "s4l_v1.simulation": MagicMock(),
    "s4l_v1.model": MagicMock(),
}

with patch.dict("sys.modules", mocks):
    from src.setups.boundary_setup import BoundarySetup


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_solver_settings.return_value = {}
    return config


def test_boundary_setup_initialization(mock_config):
    setup = BoundarySetup(mock_config, MagicMock(), MagicMock(), MagicMock())
    assert setup.config == mock_config
