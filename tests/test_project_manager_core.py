"""Tests for goliat.project_manager module core functionality."""

import json
import os
from unittest.mock import MagicMock

import pytest


@pytest.mark.skip_on_ci
class TestProjectManager:
    """Tests for ProjectManager class."""

    @pytest.fixture
    def dummy_config(self, tmp_path):
        """Create a temporary config."""
        config = MagicMock()
        config.base_dir = str(tmp_path)
        config.__getitem__.side_effect = lambda key: {"execution_control": {"do_setup": True, "do_run": True, "do_extract": True}}.get(key)
        return config

    def test_project_manager_initialization(self, dummy_config):
        """Test ProjectManager initialization."""
        from goliat.project_manager import ProjectManager

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        assert manager.config == dummy_config
        assert manager.no_cache is False
        assert manager.project_path is None

    def test_project_manager_generate_config_hash(self, dummy_config):
        """Test _generate_config_hash method."""
        from goliat.project_manager import ProjectManager

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        config_dict = {"key1": "value1", "key2": "value2"}
        hash1 = manager._generate_config_hash(config_dict)

        # Same config should produce same hash
        hash2 = manager._generate_config_hash(config_dict)
        assert hash1 == hash2

        # Different config should produce different hash
        config_dict2 = {"key1": "value1", "key2": "value3"}
        hash3 = manager._generate_config_hash(config_dict2)
        assert hash1 != hash3

    def test_project_manager_write_simulation_metadata(self, dummy_config, tmp_path):
        """Test write_simulation_metadata method."""
        from goliat.project_manager import ProjectManager

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        meta_path = str(tmp_path / "metadata.json")
        surgical_config = {"phantom": "thelonious", "frequency": 700, "placement": "by_cheek"}

        manager.write_simulation_metadata(meta_path, surgical_config)

        # Verify metadata file was created
        assert os.path.exists(meta_path)

        # Verify metadata content
        with open(meta_path) as f:
            metadata = json.load(f)

        assert "config_hash" in metadata
        assert "config_snapshot" in metadata
        assert metadata["config_snapshot"] == surgical_config
        assert metadata["run_done"] is False
        assert metadata["extract_done"] is False
        assert "setup_timestamp" in metadata

    def test_project_manager_update_simulation_metadata(self, dummy_config, tmp_path):
        """Test update_simulation_metadata method."""
        from goliat.project_manager import ProjectManager

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        meta_path = str(tmp_path / "metadata.json")

        # First write initial metadata
        surgical_config = {"test": "config"}
        manager.write_simulation_metadata(meta_path, surgical_config)

        # Then update it
        manager.update_simulation_metadata(meta_path, run_done=True, extract_done=False)

        # Verify updates
        with open(meta_path) as f:
            metadata = json.load(f)

        assert metadata["run_done"] is True
        assert metadata["extract_done"] is False

        # Update extract_done
        manager.update_simulation_metadata(meta_path, extract_done=True)

        with open(meta_path) as f:
            metadata = json.load(f)

        assert metadata["run_done"] is True
        assert metadata["extract_done"] is True

    def test_project_manager_update_metadata_file_not_found(self, dummy_config):
        """Test update_simulation_metadata when file doesn't exist."""
        from goliat.project_manager import ProjectManager

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        # Should not crash
        manager.update_simulation_metadata("/nonexistent/path.json", run_done=True)

    def test_project_manager_get_deliverables_status(self, dummy_config, tmp_path):
        """Test _get_deliverables_status method."""
        from goliat.project_manager import ProjectManager
        import time

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        project_dir = str(tmp_path)
        project_filename = "test_project"
        setup_timestamp = time.time()

        # Create results directory and H5 file
        results_dir = os.path.join(project_dir, f"{project_filename}_Results")
        os.makedirs(results_dir, exist_ok=True)

        # Create a mock H5 file larger than 8MB
        h5_file_path = os.path.join(results_dir, "test_Output.h5")
        with open(h5_file_path, "wb") as f:
            f.write(b"0" * (9 * 1024 * 1024))  # 9MB file

        status = manager._get_deliverables_status(project_dir, project_filename, setup_timestamp)

        assert "run_done" in status
        assert "extract_done" in status
        # Run should be done since we have a valid H5 file
        assert status["run_done"] is True

    def test_project_manager_get_deliverables_status_small_file(self, dummy_config, tmp_path):
        """Test _get_deliverables_status with small H5 file (should be ignored)."""
        from goliat.project_manager import ProjectManager
        import time

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        project_dir = str(tmp_path)
        project_filename = "test_project"
        setup_timestamp = time.time()

        # Create results directory and small H5 file
        results_dir = os.path.join(project_dir, f"{project_filename}_Results")
        os.makedirs(results_dir, exist_ok=True)

        # Create a small H5 file (less than 8MB)
        h5_file_path = os.path.join(results_dir, "test_Output.h5")
        with open(h5_file_path, "wb") as f:
            f.write(b"0" * 1024)  # 1KB file

        status = manager._get_deliverables_status(project_dir, project_filename, setup_timestamp)

        # Small file should be ignored
        assert status["run_done"] is False
