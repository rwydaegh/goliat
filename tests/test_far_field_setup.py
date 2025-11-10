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
    from goliat.setups.far_field_setup import FarFieldSetup


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.__getitem__.side_effect = lambda key: "environmental" if "far_field_setup.type" in key else None
    return config


def test_far_field_setup_initialization(mock_config):
    setup = FarFieldSetup(
        config=mock_config,
        phantom_name="test_phantom",
        frequency_mhz=700,
        direction_name="x_pos",
        polarization_name="theta",
        project_manager=MagicMock(),
        verbose_logger=MagicMock(),
        progress_logger=MagicMock(),
        profiler=MagicMock(),
    )
    assert setup.phantom_name == "test_phantom"
    assert setup.frequency_mhz == 700
    assert setup.direction_name == "x_pos"
    assert setup.polarization_name == "theta"


# Full setup tests are too complex for this simple testing approach
