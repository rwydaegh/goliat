"""Tests for goliat.utils.setup module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from goliat.utils.setup import (
    check_package_installed,
    check_repo_root,
    find_sim4life_python_executables,
    update_bashrc,
)


class TestCheckPackageInstalled:
    """Tests for check_package_installed function."""

    def test_package_installed_via_pip(self, monkeypatch):
        """Test detecting package installed via pip."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps([{"name": "goliat", "version": "1.0.0"}])
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            assert check_package_installed() is True

    def test_package_not_installed_via_pip(self, monkeypatch):
        """Test detecting package not installed via pip."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps([{"name": "other-package", "version": "1.0.0"}])
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            # Also mock the fallback check
            with patch("goliat.utils.setup.os.path.exists", return_value=False):
                assert check_package_installed() is False

    def test_package_installed_via_egg_info(self, monkeypatch, tmp_path):
        """Test detecting package via egg-info directory."""
        mock_result = MagicMock()
        mock_result.returncode = 1  # Simulate pip list failure
        mock_result.stdout = ""  # Empty stdout

        with patch("subprocess.run", return_value=mock_result):
            # Create a mock egg-info directory
            base_dir = tmp_path
            egg_info_dir = base_dir / "goliat.egg-info"
            egg_info_dir.mkdir()

            with patch("goliat.utils.setup.os.path.abspath", return_value=str(base_dir)):
                with patch("goliat.utils.setup.os.path.exists", side_effect=lambda p: p == str(egg_info_dir)):
                    assert check_package_installed() is True

    def test_package_not_importable(self, monkeypatch):
        """Test when package cannot be imported."""
        # Mock importlib.util.find_spec to return None (package not found)
        # Also mock pip list to return empty and egg-info to not exist
        with patch("importlib.util.find_spec", return_value=None):
            mock_result = MagicMock()
            mock_result.stdout = json.dumps([])
            mock_result.returncode = 0
            with patch("subprocess.run", return_value=mock_result):
                with patch("goliat.utils.package.os.path.exists", return_value=False):
                    assert check_package_installed() is False


class TestCheckRepoRoot:
    """Tests for check_repo_root function."""

    def test_in_repo_root(self, tmp_path, monkeypatch):
        """Test when running from repo root."""
        configs_dir = tmp_path / "configs"
        goliat_dir = tmp_path / "goliat"
        configs_dir.mkdir()
        goliat_dir.mkdir()

        monkeypatch.chdir(tmp_path)
        # Should not raise
        check_repo_root()

    def test_not_in_repo_root(self, tmp_path, monkeypatch):
        """Test when not running from repo root."""
        monkeypatch.chdir(tmp_path)
        # Should raise SystemExit
        with pytest.raises(SystemExit):
            check_repo_root()


class TestFindSim4LifePythonExecutables:
    """Tests for find_sim4life_python_executables function."""

    @patch("goliat.utils.setup.sys.platform", "win32")
    @patch("goliat.utils.setup.os.path.exists")
    @patch("glob.glob")
    def test_finds_sim4life_executables(self, mock_glob, mock_exists):
        """Test finding Sim4Life Python executables."""

        # Mock drive existence - only C drive exists
        def exists_side_effect(path):
            if path.endswith(":\\"):
                return path == "C:\\"
            return False

        mock_exists.side_effect = exists_side_effect

        # Mock glob results - return unique results (no duplicates)
        mock_glob.return_value = [
            "C:\\Program Files\\Sim4Life_8.2.0.16876\\Python",
            "C:\\Program Files\\Sim4Life_9.0.0.12345\\Python",
        ]

        with patch("goliat.utils.setup.os.path.isdir", return_value=True):
            results = find_sim4life_python_executables()
            # The function checks both versions (8.2 and 9.0) for each drive
            # Since we only have C drive and return 2 results, we should get 2
            assert len(results) >= 2
            assert any("Sim4Life_8.2" in r for r in results)
            assert any("Sim4Life_9.0" in r for r in results)

    @patch("goliat.utils.setup.sys.platform", "win32")
    @patch("goliat.utils.setup.os.path.exists")
    @patch("glob.glob")
    def test_finds_no_executables(self, mock_glob, mock_exists):
        """Test when no Sim4Life executables are found."""

        def exists_side_effect(path):
            if path.endswith(":\\"):
                return path == "C:\\"
            return False

        mock_exists.side_effect = exists_side_effect
        mock_glob.return_value = []

        results = find_sim4life_python_executables()
        assert len(results) == 0


class TestUpdateBashrc:
    """Tests for update_bashrc function."""

    def test_update_bashrc_creates_file(self, tmp_path, monkeypatch):
        """Test creating/updating .bashrc file."""
        monkeypatch.chdir(tmp_path)

        python_path = "C:\\Program Files\\Sim4Life_8.2.0.16876\\Python"
        update_bashrc(python_path)

        bashrc_path = tmp_path / ".bashrc"
        assert bashrc_path.exists()

        with open(bashrc_path, "r") as f:
            content = f.read()
            assert "export PATH=" in content
            # Path conversion should use uppercase /C/ (drive letter is uppercased)
            assert "/C/Program Files/Sim4Life_8.2.0.16876/Python" in content

    def test_update_bashrc_strips_quotes(self, tmp_path, monkeypatch):
        """Test that quotes are stripped from path."""
        monkeypatch.chdir(tmp_path)

        python_path = '"C:\\Program Files\\Sim4Life_8.2.0.16876\\Python"'
        update_bashrc(python_path)

        bashrc_path = tmp_path / ".bashrc"
        with open(bashrc_path, "r") as f:
            content = f.read()
            # Function writes 2 lines, each with quotes around path: 4 quotes total
            assert content.count('"') == 4  # Two lines: Python and Scripts paths
