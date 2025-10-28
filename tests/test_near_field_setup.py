from unittest.mock import MagicMock, patch

import pytest

# Mock s4l_v1 and other dependencies
mocks = {
    "s4l_v1": MagicMock(),
    "s4l_v1.simulation": MagicMock(),
    "s4l_v1.model": MagicMock(),
    "XCoreModeling": MagicMock(),
    "numpy": MagicMock(),
}

with patch.dict("sys.modules", mocks):
    from src.setups.near_field_setup import NearFieldSetup


@pytest.fixture
def mock_config():
    config = MagicMock()
    return config


@pytest.fixture
def mock_antenna():
    antenna = MagicMock()
    return antenna


def test_near_field_setup_initialization(mock_config, mock_antenna):
    setup = NearFieldSetup(
        config=mock_config,
        phantom_name="test_phantom",
        frequency_mhz=700,
        placement_name="by_cheek_center_vertical",
        antenna=mock_antenna,
        verbose_logger=MagicMock(),
        progress_logger=MagicMock(),
    )
    assert setup.phantom_name == "test_phantom"
    assert setup.base_placement_name == "by_cheek"
    # Removed assertions for position_name and orientation_name as they are not part of NearFieldSetup


# Full setup tests are too complex for this simple testing approach
