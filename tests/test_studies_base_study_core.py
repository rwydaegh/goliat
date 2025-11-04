"""Comprehensive tests for goliat.studies.base_study core methods."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.skip_on_ci
class TestBaseStudyCoreMethods:
    """Tests for BaseStudy core workflow methods."""

    @pytest.fixture
    def base_study(self, tmp_path):
        """Create a BaseStudy instance for testing."""
        from goliat.studies.base_study import BaseStudy
        import json

        # Create minimal config structure
        config_dir = tmp_path / "configs"
        data_dir = tmp_path / "data"
        config_dir.mkdir()
        data_dir.mkdir()

        config_path = config_dir / "near_field_config.json"
        with open(config_path, "w") as f:
            json.dump({"study_type": "near_field", "phantoms": []}, f)

        material_mapping_path = data_dir / "material_name_mapping.json"
        with open(material_mapping_path, "w") as f:
            json.dump({}, f)

        profiling_path = data_dir / "profiling_config.json"
        with open(profiling_path, "w") as f:
            json.dump({"near_field": {}}, f)

        study = BaseStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        # Mock base_dir to use tmp_path
        study.base_dir = str(tmp_path)

        return study

    def test_base_study_execute_run_phase(self, base_study):
        """Test _execute_run_phase method."""
        mock_simulation = MagicMock()
        mock_project_manager = MagicMock()
        mock_project_manager.project_path = "/tmp/test.smash"

        base_study.project_manager = mock_project_manager

        with patch("goliat.studies.base_study.SimulationRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner

            base_study._execute_run_phase(mock_simulation)

            # Verify SimulationRunner was created and run
            assert mock_runner_class.called
            assert mock_runner.run.called

    def test_base_study_subtask_context_manager(self, base_study):
        """Test subtask context manager."""
        mock_profiler = MagicMock()
        mock_profiler.subtask_stack = []
        mock_profiler.subtask_times = {"test_task": [1.5]}
        mock_profiler.current_phase = "setup"

        base_study.profiler = mock_profiler

        # Test subtask context manager
        with base_study.subtask("test_task"):
            pass

        # Verify profiler.subtask was called
        assert mock_profiler.subtask.called

    def test_base_study_subtask_with_gui(self, base_study):
        """Test subtask context manager with GUI."""
        mock_profiler = MagicMock()
        mock_profiler.subtask_stack = []
        mock_profiler.subtask_times = {"test_task": [1.5]}
        mock_profiler.current_phase = "setup"

        mock_gui = MagicMock()
        base_study.profiler = mock_profiler
        base_study.gui = mock_gui

        with base_study.subtask("test_task"):
            pass

        # Verify GUI methods were called
        assert mock_gui.update_stage_progress.called or mock_gui.start_stage_animation.called

    def test_base_study_verify_run_deliverables_before_extraction(self, base_study):
        """Test _verify_run_deliverables_before_extraction."""
        mock_project_manager = MagicMock()
        mock_project_manager.project_path = "/tmp/test.smash"
        mock_project_manager._get_deliverables_status.return_value = {"run_done": True, "extract_done": False}

        base_study.project_manager = mock_project_manager

        result = base_study._verify_run_deliverables_before_extraction()

        assert result is True
        assert mock_project_manager._get_deliverables_status.called

    def test_base_study_verify_run_deliverables_no_project_path(self, base_study):
        """Test _verify_run_deliverables_before_extraction with no project path."""
        mock_project_manager = MagicMock()
        mock_project_manager.project_path = None

        base_study.project_manager = mock_project_manager

        with patch.object(base_study, "_log") as mock_log:
            result = base_study._verify_run_deliverables_before_extraction()

            assert result is False
            assert mock_log.called

    def test_base_study_verify_and_update_metadata(self, base_study):
        """Test _verify_and_update_metadata."""
        mock_project_manager = MagicMock()
        mock_project_manager.project_path = "/tmp/test.smash"
        mock_project_manager.metadata_path = "/tmp/metadata.json"

        base_study.project_manager = mock_project_manager

        with patch.object(base_study.project_manager, "update_simulation_metadata") as mock_update:
            base_study._verify_and_update_metadata("run")

            assert mock_update.called

    def test_base_study_run_method_error_handling(self, base_study):
        """Test run() method error handling."""
        from goliat.utils import StudyCancelledError

        mock_profiler = MagicMock()
        base_study.profiler = mock_profiler

        # Test StudyCancelledError handling
        with patch("goliat.studies.base_study.ensure_s4l_running"), patch.object(
            base_study, "_run_study", side_effect=StudyCancelledError("Cancelled")
        ):
            with patch.object(base_study, "_log") as mock_log:
                base_study.run()

                # Should log cancellation message
                assert mock_log.called

    def test_base_study_run_method_general_exception(self, base_study):
        """Test run() method general exception handling."""
        mock_profiler = MagicMock()
        base_study.profiler = mock_profiler

        with patch("goliat.studies.base_study.ensure_s4l_running"), patch.object(
            base_study, "_run_study", side_effect=RuntimeError("Test error")
        ):
            with patch.object(base_study, "_log") as mock_log:
                base_study.run()

                # Should log fatal error
                assert mock_log.called

    def test_base_study_run_method_finally_block(self, base_study):
        """Test run() method finally block execution."""
        mock_profiler = MagicMock()
        mock_project_manager = MagicMock()
        mock_gui = MagicMock()

        base_study.profiler = mock_profiler
        base_study.project_manager = mock_project_manager
        base_study.gui = mock_gui

        with patch("goliat.studies.base_study.ensure_s4l_running"), patch.object(base_study, "_run_study"):
            base_study.run()

            # Verify finally block execution
            assert mock_profiler.save_estimates.called
            assert mock_project_manager.cleanup.called
            assert mock_gui.update_profiler.called
