from unittest.mock import MagicMock, patch

import pytest

# Mock s4l_v1 and XCoreModeling
mocks = {
    "s4l_v1": MagicMock(),
    "s4l_v1.materials": MagicMock(),
    "s4l_v1.materials.database": MagicMock(),
    "XCoreModeling": MagicMock(),
}

with patch.dict("sys.modules", mocks):
    from src.setups.material_setup import MaterialSetup


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_material_mapping.return_value = {}
    return config


def test_material_setup_initialization(mock_config):
    setup = MaterialSetup(
        config=mock_config,
        simulation=MagicMock(),
        antenna=None,
        phantom_name="test_phantom",
        verbose_logger=MagicMock(),
        progress_logger=MagicMock(),
    )
    assert setup.config == mock_config


# More detailed tests would require a more complex setup.
