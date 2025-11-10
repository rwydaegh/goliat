from unittest.mock import MagicMock, patch

import pytest

# Mock s4l_v1 and numpy
mocks = {
    "s4l_v1": MagicMock(),
    "s4l_v1.units": MagicMock(),
    "s4l_v1.model": MagicMock(),
    "numpy": MagicMock(),
}

with patch.dict("sys.modules", mocks):
    from goliat.setups.gridding_setup import GriddingSetup


@pytest.fixture
def mock_config():
    config = MagicMock()
    gridding_params = {
        "global_gridding": {"grid_mode": "automatic"},
        "padding": {"padding_mode": "automatic"},
    }
    config.__getitem__.side_effect = lambda key: gridding_params if key == "gridding_parameters" else None
    return config


def test_gridding_setup_initialization(mock_config):
    setup = GriddingSetup(
        config=mock_config,
        simulation=MagicMock(),
        placement_name="test_placement",
        antenna=MagicMock(),
        verbose_logger=MagicMock(),
        progress_logger=MagicMock(),
    )
    assert setup.config == mock_config


# More detailed tests would require a more complex setup.
