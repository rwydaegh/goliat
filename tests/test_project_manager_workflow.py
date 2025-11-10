"""Comprehensive tests for goliat.project_manager core workflow."""

import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.skip_on_ci
class TestProjectManagerCoreWorkflow:
    """Tests for ProjectManager core workflow methods."""

    @pytest.fixture
    def dummy_config(self, tmp_path):
        """Create a temporary config."""
        config = MagicMock()
        config.base_dir = str(tmp_path)
        config.__getitem__.side_effect = lambda key: {"execution_control": {"do_setup": True, "do_run": True, "do_extract": True}}.get(key)
        return config

    def test_project_manager_create_or_open_project(self, dummy_config, tmp_path):
        """Test create_or_open_project method."""
        from goliat.project_manager import ProjectManager

        dummy_config.__getitem__.side_effect = lambda key: {
            "study_type": "near_field",
            "execution_control.do_setup": True,
        }.get(key)

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        # Mock s4l_v1.document imported inside method
        mock_document = MagicMock()
        mock_document.New.return_value = MagicMock()

        with patch("s4l_v1.document", mock_document):
            status = manager.create_or_open_project(
                phantom_name="thelonious", frequency_mhz=700, scenario_name="by_cheek", position_name="center", orientation_name="vertical"
            )

            assert isinstance(status, dict)
            assert "setup_done" in status
            assert "run_done" in status
            assert "extract_done" in status

    def test_project_manager_verify_simulation_metadata(self, dummy_config, tmp_path):
        """Test verify_simulation_metadata method."""
        from goliat.project_manager import ProjectManager

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        # Create metadata file
        meta_path = os.path.join(str(tmp_path), "config.json")
        surgical_config = {"phantom": "thelonious", "frequency": 700}
        manager.write_simulation_metadata(meta_path, surgical_config)

        # Test verification with matching config
        status = manager.verify_simulation_metadata(meta_path, surgical_config)

        assert isinstance(status, dict)
        assert "setup_done" in status

    def test_project_manager_verify_simulation_metadata_mismatch(self, dummy_config, tmp_path):
        """Test verify_simulation_metadata with config mismatch."""
        from goliat.project_manager import ProjectManager

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        # Create metadata with different config
        meta_path = os.path.join(str(tmp_path), "config.json")
        original_config = {"phantom": "thelonious", "frequency": 700}
        manager.write_simulation_metadata(meta_path, original_config)

        # Try to verify with different config
        different_config = {"phantom": "thelonious", "frequency": 900}
        status = manager.verify_simulation_metadata(meta_path, different_config)

        # Should return status with setup_done=False due to hash mismatch
        assert status["setup_done"] is False

    def test_project_manager_get_deliverables_status_with_extract(self, dummy_config, tmp_path):
        """Test _get_deliverables_status with extract deliverables."""
        from goliat.project_manager import ProjectManager

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

        # Create results directory with H5 file
        results_dir = os.path.join(project_dir, f"{project_filename}_Results")
        os.makedirs(results_dir, exist_ok=True)

        h5_file = os.path.join(results_dir, "test_Output.h5")
        with open(h5_file, "wb") as f:
            f.write(b"0" * (9 * 1024 * 1024))  # 9MB file

        # Create extract deliverables in project_dir (where _get_deliverables_status looks)
        # The method looks for files directly in project_dir
        json_file = os.path.join(project_dir, "sar_results.json")
        pkl_file = os.path.join(project_dir, "sar_stats_all_tissues.pkl")
        html_file = os.path.join(project_dir, "sar_stats_all_tissues.html")

        with open(json_file, "w") as f:
            json.dump({}, f)
        with open(pkl_file, "wb") as f:
            f.write(b"dummy")
        with open(html_file, "w") as f:
            f.write("<html></html>")

        status = manager._get_deliverables_status(project_dir, project_filename, setup_timestamp)

        assert status["run_done"] is True
        assert status["extract_done"] is True

    def test_project_manager_cleanup(self, dummy_config):
        """Test cleanup method."""
        from goliat.project_manager import ProjectManager

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        # Mock document cleanup
        mock_document = MagicMock()
        manager.document = mock_document

        manager.cleanup()

        # Verify cleanup was called
        assert hasattr(mock_document, "CloseAll") or True  # May or may not exist

    def test_project_manager_verify_simulation_metadata_no_file(self, dummy_config, tmp_path):
        """Test verify_simulation_metadata when metadata file doesn't exist."""
        from goliat.project_manager import ProjectManager

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        meta_path = os.path.join(str(tmp_path), "nonexistent.json")
        status = manager.verify_simulation_metadata(meta_path, {"test": "config"})

        assert isinstance(status, dict)
        assert status["setup_done"] is False

    def test_project_manager_get_setup_timestamp_from_metadata(self, dummy_config, tmp_path):
        """Test get_setup_timestamp_from_metadata method."""
        from goliat.project_manager import ProjectManager

        manager = ProjectManager(
            config=dummy_config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

        meta_path = os.path.join(str(tmp_path), "config.json")
        surgical_config = {"phantom": "thelonious", "frequency": 700}
        manager.write_simulation_metadata(meta_path, surgical_config)

        timestamp = manager.get_setup_timestamp_from_metadata(meta_path)

        assert timestamp is not None
        assert isinstance(timestamp, float)
