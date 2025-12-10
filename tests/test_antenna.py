"""Tests for goliat.antenna module."""

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
        """Test getting centered antenna path when file exists."""
        antenna = Antenna(mock_config, 700)
        centered_antennas_dir = tmp_path / "antennas" / "centered"
        centered_antennas_dir.mkdir(parents=True)

        # Create the expected file
        expected_file = centered_antennas_dir / "700MHz_centered.sab"
        expected_file.touch()

        path = antenna.get_centered_antenna_path(str(centered_antennas_dir))
        assert path == str(expected_file)

    def test_get_centered_antenna_path_different_frequency(self, mock_config, tmp_path):
        """Test getting centered antenna path for different frequency when file exists."""
        antenna = Antenna(mock_config, 900)
        centered_antennas_dir = tmp_path / "antennas" / "centered"
        centered_antennas_dir.mkdir(parents=True)

        # Create the expected file
        expected_file = centered_antennas_dir / "900MHz_centered.sab"
        expected_file.touch()

        path = antenna.get_centered_antenna_path(str(centered_antennas_dir))
        assert path == str(expected_file)

    def test_get_centered_antenna_path_fallback_to_nearest(self, mock_config, tmp_path, caplog):
        """Test fallback to nearest frequency when exact file doesn't exist."""
        import logging

        caplog.set_level(logging.WARNING)

        antenna = Antenna(mock_config, 1400)
        centered_antennas_dir = tmp_path / "antennas" / "centered"
        centered_antennas_dir.mkdir(parents=True)

        # Create files for nearby frequencies, but not 1400
        # Use 1300 and 1450 so that 1450 is unambiguously the nearest (50 vs 100 MHz)
        (centered_antennas_dir / "1300MHz_centered.sab").touch()
        (centered_antennas_dir / "1450MHz_centered.sab").touch()
        (centered_antennas_dir / "1500MHz_centered.sab").touch()

        path = antenna.get_centered_antenna_path(str(centered_antennas_dir))
        # Should use 1450 as it's nearest to 1400 (50 MHz away vs 100 MHz for 1300)
        expected = centered_antennas_dir / "1450MHz_centered.sab"
        assert path == str(expected)

        # Check that warnings were logged
        assert "not found" in caplog.text.lower()
        assert "1450" in caplog.text
        assert "1400" in caplog.text

    def test_get_centered_antenna_path_no_files(self, mock_config, tmp_path):
        """Test error when no antenna files exist."""
        antenna = Antenna(mock_config, 700)
        centered_antennas_dir = tmp_path / "antennas" / "centered"
        centered_antennas_dir.mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="No antenna files found"):
            antenna.get_centered_antenna_path(str(centered_antennas_dir))

    def test_get_centered_antenna_path_nonexistent_directory(self, mock_config, tmp_path):
        """Test error when directory doesn't exist."""
        antenna = Antenna(mock_config, 700)
        centered_antennas_dir = tmp_path / "antennas" / "centered"

        with pytest.raises(FileNotFoundError, match="does not exist"):
            antenna.get_centered_antenna_path(str(centered_antennas_dir))
