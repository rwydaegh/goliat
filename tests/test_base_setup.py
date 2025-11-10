from unittest.mock import MagicMock, patch

import pytest

# Mock s4l_v1
mocks = {
    "s4l_v1": MagicMock(),
    "s4l_v1.simulation": MagicMock(),
    "s4l_v1.model": MagicMock(),
    "XCore": MagicMock(),
}

with patch.dict("sys.modules", mocks):
    from goliat.setups.base_setup import BaseSetup


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.__getitem__.return_value = {}
    return config


def test_base_setup_initialization(mock_config):
    setup = BaseSetup(mock_config, MagicMock(), MagicMock())
    assert setup.config == mock_config


def test_run_full_setup_not_implemented(mock_config):
    setup = BaseSetup(mock_config, MagicMock(), MagicMock())
    with pytest.raises(NotImplementedError):
        setup.run_full_setup(MagicMock())
