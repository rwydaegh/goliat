"""Tests for goliat.utils.data module."""

import json
from unittest.mock import MagicMock, patch


from goliat.utils.data import download_and_extract_data, setup_console_logging


class TestSetupConsoleLogging:
    """Tests for setup_console_logging function."""

    def test_setup_console_logging(self):
        """Test setting up console logging."""
        logger = setup_console_logging()
        assert logger is not None
        assert logger.name == "script_logger"
        assert logger.level == 20  # INFO level


class TestDownloadAndExtractData:
    """Tests for download_and_extract_data function."""

    @patch("goliat.utils.data.gdown.download_folder")
    @patch("goliat.utils.data.os.makedirs")
    @patch("goliat.utils.data.os.path.exists")
    def test_download_and_extract_data_standard(self, mock_exists, mock_makedirs, mock_download, tmp_path):
        """Test downloading standard data."""
        # Setup config
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        config_file = configs_dir / "base_config.json"
        config_data = {
            "data_setup": {
                "data_dir": "data",
                "gdrive_url": "https://drive.google.com/drive/folders/test123",
            }
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        mock_exists.return_value = False
        mock_logger = MagicMock()

        download_and_extract_data(str(tmp_path), mock_logger, aws=False)

        mock_makedirs.assert_called()
        mock_download.assert_called_once()
        mock_logger.info.assert_called()

    @patch("goliat.utils.data.gdown.download")
    @patch("goliat.utils.data.os.makedirs")
    @patch("goliat.utils.data.os.path.exists")
    def test_download_and_extract_data_aws(self, mock_exists, mock_makedirs, mock_download, tmp_path):
        """Test downloading AWS-specific data."""
        # Setup config
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        config_file = configs_dir / "base_config.json"
        config_data = {
            "data_setup": {
                "data_dir": "data",
                "gdrive_url": "https://drive.google.com/drive/folders/test123",
                "gdrive_url_aws": "https://drive.google.com/uc?id=test456",
            }
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        def exists_side_effect(path):
            if "configs" in path:
                return True
            return False

        mock_exists.side_effect = exists_side_effect
        mock_logger = MagicMock()

        download_and_extract_data(str(tmp_path), mock_logger, aws=True)

        mock_makedirs.assert_called()
        mock_download.assert_called_once()
        assert "duke_posable.sab" in str(mock_download.call_args)

    @patch("goliat.utils.data.gdown.download_folder")
    @patch("goliat.utils.data.os.makedirs")
    @patch("goliat.utils.data.os.path.exists")
    def test_download_and_extract_data_existing_dir(self, mock_exists, mock_makedirs, mock_download, tmp_path):
        """Test downloading when data directory already exists."""
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        config_file = configs_dir / "base_config.json"
        config_data = {
            "data_setup": {
                "data_dir": "data",
                "gdrive_url": "https://drive.google.com/drive/folders/test123",
            }
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        def exists_side_effect(path):
            if "configs" in path or "data" in path:
                return True
            return False

        mock_exists.side_effect = exists_side_effect
        mock_logger = MagicMock()

        download_and_extract_data(str(tmp_path), mock_logger, aws=False)

        # Should not create directory if it exists
        calls = [str(call) for call in mock_makedirs.call_args_list]
        data_dir_calls = [c for c in calls if "data" in c]
        assert len(data_dir_calls) == 0 or mock_exists.return_value is True
