"""Tests for CLI commands module."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from cli.commands import init_config, show_status, show_version, validate_config


@pytest.fixture
def tmp_project_dir(tmp_path):
    """Create a temporary project directory structure."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    goliat_dir = tmp_path / "goliat"
    goliat_dir.mkdir()

    # Create template configs
    near_field_template = {
        "extends": "base_config.json",
        "study_type": "near_field",
        "phantoms": ["thelonious"],
        "antenna_config": {"700": {"model_type": "test"}},
    }
    far_field_template = {
        "extends": "base_config.json",
        "study_type": "far_field",
        "phantoms": ["thelonious"],
        "frequencies_mhz": [700],
    }

    with open(configs_dir / "near_field_config.json", "w") as f:
        json.dump(near_field_template, f)
    with open(configs_dir / "far_field_config.json", "w") as f:
        json.dump(far_field_template, f)

    return tmp_path


class TestInitConfig:
    """Tests for init_config command."""

    def test_init_config_near_field(self, tmp_project_dir, capsys):
        """Test initializing near-field config."""
        output_path = tmp_project_dir / "configs" / "my_near_field_config.json"

        init_config("near_field", str(output_path), str(tmp_project_dir))

        assert output_path.exists()
        with open(output_path, "r") as f:
            config = json.load(f)
        assert config["study_type"] == "near_field"

        captured = capsys.readouterr()
        assert "Created config file" in captured.out

    def test_init_config_far_field(self, tmp_project_dir, capsys):
        """Test initializing far-field config."""
        output_path = tmp_project_dir / "configs" / "my_far_field_config.json"

        init_config("far_field", str(output_path), str(tmp_project_dir))

        assert output_path.exists()
        with open(output_path, "r") as f:
            config = json.load(f)
        assert config["study_type"] == "far_field"

    def test_init_config_default_output(self, tmp_project_dir):
        """Test initializing config with default output path."""
        init_config("near_field", None, str(tmp_project_dir))

        output_path = tmp_project_dir / "configs" / "my_near_field_config.json"
        assert output_path.exists()

    def test_init_config_template_not_found(self, tmp_path, capsys):
        """Test when template file doesn't exist."""
        with pytest.raises(SystemExit):
            init_config("nonexistent_type", None, str(tmp_path))

        captured = capsys.readouterr()
        assert "Template file not found" in captured.out

    def test_init_config_existing_file(self, tmp_project_dir, monkeypatch):
        """Test initializing config when file already exists."""
        output_path = tmp_project_dir / "configs" / "my_near_field_config.json"
        output_path.write_text('{"existing": "data"}')

        # Mock user input to decline overwrite
        monkeypatch.setattr("builtins.input", lambda _: "n")

        init_config("near_field", str(output_path), str(tmp_project_dir))

        # File should remain unchanged
        assert json.loads(output_path.read_text()) == {"existing": "data"}


class TestShowStatus:
    """Tests for show_status command."""

    @patch("goliat.utils.setup.check_package_installed")
    def test_show_status(self, mock_check_installed, tmp_project_dir, capsys):
        """Test showing status."""
        mock_check_installed.return_value = True

        # Create data directories
        data_dir = tmp_project_dir / "data"
        phantoms_dir = data_dir / "phantoms"
        antennas_dir = data_dir / "antennas" / "centered"
        phantoms_dir.mkdir(parents=True)
        antennas_dir.mkdir(parents=True)
        (phantoms_dir / "phantom1.sab").touch()
        (antennas_dir / "antenna1.sab").touch()

        show_status(str(tmp_project_dir))

        captured = capsys.readouterr()
        assert "GOLIAT Status" in captured.out
        assert "Package installed" in captured.out

    @patch("goliat.utils.setup.check_package_installed")
    def test_show_status_not_installed(self, mock_check_installed, tmp_project_dir, capsys):
        """Test showing status when package not installed."""
        mock_check_installed.return_value = False

        show_status(str(tmp_project_dir))

        captured = capsys.readouterr()
        assert "Package installed" in captured.out


class TestValidateConfig:
    """Tests for validate_config command."""

    def test_validate_config_valid_near_field(self, tmp_project_dir, capsys):
        """Test validating a valid near-field config."""
        config_path = tmp_project_dir / "configs" / "near_field_config.json"

        # Mock Config to avoid needing full setup
        with patch("goliat.config.Config") as mock_config_class:
            mock_config = MagicMock()
            mock_config.__getitem__.side_effect = lambda key: {
                "study_type": "near_field",
                "phantoms": ["thelonious"],
                "antenna_config": {"700": {"model_type": "test"}},
            }.get(key)
            mock_config_class.return_value = mock_config

            validate_config(str(config_path), str(tmp_project_dir))

            captured = capsys.readouterr()
            assert "Config is valid" in captured.out

    def test_validate_config_valid_far_field(self, tmp_project_dir, capsys):
        """Test validating a valid far-field config."""
        config_path = tmp_project_dir / "configs" / "far_field_config.json"

        with patch("goliat.config.Config") as mock_config_class:
            mock_config = MagicMock()
            mock_config.__getitem__.side_effect = lambda key: {
                "study_type": "far_field",
                "phantoms": ["thelonious"],
                "frequencies_mhz": [700],
            }.get(key)
            mock_config_class.return_value = mock_config

            validate_config(str(config_path), str(tmp_project_dir))

            captured = capsys.readouterr()
            assert "Config is valid" in captured.out

    def test_validate_config_missing_study_type(self, tmp_project_dir, capsys):
        """Test validating config with missing study_type."""
        config_path = tmp_project_dir / "configs" / "invalid_config.json"

        with patch("goliat.config.Config") as mock_config_class:
            mock_config = MagicMock()
            mock_config.__getitem__.return_value = None
            mock_config_class.return_value = mock_config

            with pytest.raises(SystemExit):
                validate_config(str(config_path), str(tmp_project_dir))

            captured = capsys.readouterr()
            assert "Missing 'study_type'" in captured.out

    def test_validate_config_missing_phantoms(self, tmp_project_dir, capsys):
        """Test validating config with missing phantoms."""
        config_path = tmp_project_dir / "configs" / "invalid_config.json"

        with patch("goliat.config.Config") as mock_config_class:
            mock_config = MagicMock()
            mock_config.__getitem__.side_effect = lambda key: {
                "study_type": "near_field",
                "phantoms": [],
            }.get(key)
            mock_config_class.return_value = mock_config

            with pytest.raises(SystemExit):
                validate_config(str(config_path), str(tmp_project_dir))

            captured = capsys.readouterr()
            assert "No phantoms specified" in captured.out


class TestShowVersion:
    """Tests for show_version command."""

    def test_show_version_from_package(self, capsys):
        """Test showing version from package."""
        # Mock the goliat module import
        mock_goliat = MagicMock()
        mock_goliat.__version__ = "1.2.3"

        original_goliat = sys.modules.get("goliat")
        sys.modules["goliat"] = mock_goliat
        try:
            show_version()
            captured = capsys.readouterr()
            assert "GOLIAT 1.2.3" in captured.out
        finally:
            if original_goliat is not None:
                sys.modules["goliat"] = original_goliat
            elif "goliat" in sys.modules:
                del sys.modules["goliat"]

    def test_show_version_fallback(self, tmp_path, capsys):
        """Test showing version from pyproject.toml fallback."""
        pyproject_path = tmp_path / "pyproject.toml"
        # Write a proper TOML file
        toml_content = '[project]\nversion = "2.0.0"\n'
        with open(pyproject_path, "w") as f:
            f.write(toml_content)

        # Mock the base_dir to point to tmp_path
        with patch("cli.commands.os.path.abspath", return_value=str(tmp_path)):
            with patch("builtins.__import__", side_effect=ImportError):
                show_version()
                captured = capsys.readouterr()
                # Should handle gracefully
                assert "GOLIAT" in captured.out
