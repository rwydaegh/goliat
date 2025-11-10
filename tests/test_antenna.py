"""Tests for goliat.antenna module."""

import os
from unittest.mock import MagicMock

import pytest

from goliat.antenna import Antenna


@pytest.fixture
def mock_config():
    """Create a mock config object."""
    config = MagicMock()
    antenna_config = {
        "700": {
            "model_type": "antenna_model_700",
            "source_name": "Source_700MHz",
        },
        "900": {
            "model_type": "antenna_model_900",
            "source_name": "Source_900MHz",
        },
    }
    config.__getitem__.side_effect = lambda key: antenna_config if key == "antenna_config" else None
    return config


class TestAntenna:
    """Tests for Antenna class."""

    def test_antenna_initialization(self, mock_config):
        """Test antenna initialization."""
        antenna = Antenna(mock_config, 700)
        assert antenna.config == mock_config
        assert antenna.frequency_mhz == 700

    def test_get_config_for_frequency_valid(self, mock_config):
        """Test getting config for a valid frequency."""
        antenna = Antenna(mock_config, 700)
        config = antenna.get_config_for_frequency()
        assert config["model_type"] == "antenna_model_700"
        assert config["source_name"] == "Source_700MHz"

    def test_get_config_for_frequency_invalid(self, mock_config):
        """Test getting config for an invalid frequency."""
        antenna = Antenna(mock_config, 500)
        with pytest.raises(ValueError, match="Antenna configuration not defined for frequency: 500 MHz"):
            antenna.get_config_for_frequency()

    def test_get_model_type(self, mock_config):
        """Test getting model type."""
        antenna = Antenna(mock_config, 700)
        assert antenna.get_model_type() == "antenna_model_700"

    def test_get_source_entity_name(self, mock_config):
        """Test getting source entity name."""
        antenna = Antenna(mock_config, 700)
        assert antenna.get_source_entity_name() == "Source_700MHz"

    def test_get_centered_antenna_path(self, mock_config, tmp_path):
        """Test getting centered antenna path."""
        antenna = Antenna(mock_config, 700)
        centered_antennas_dir = str(tmp_path / "antennas" / "centered")

        path = antenna.get_centered_antenna_path(centered_antennas_dir)
        expected = os.path.join(centered_antennas_dir, "700MHz_centered.sab")
        assert path == expected

    def test_get_centered_antenna_path_different_frequency(self, mock_config, tmp_path):
        """Test getting centered antenna path for different frequency."""
        antenna = Antenna(mock_config, 900)
        centered_antennas_dir = str(tmp_path / "antennas" / "centered")

        path = antenna.get_centered_antenna_path(centered_antennas_dir)
        expected = os.path.join(centered_antennas_dir, "900MHz_centered.sab")
        assert path == expected
