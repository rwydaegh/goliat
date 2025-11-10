"""Tests for goliat.studies.base_study module."""

from unittest.mock import MagicMock, patch

import pytest

from goliat.utils import StudyCancelledError


@pytest.mark.skip_on_ci
def test_base_study_initialization(tmp_path, monkeypatch):
    """Test BaseStudy initialization."""
    # Mock dependencies
    with patch("goliat.studies.base_study.Config") as mock_config_class, patch(
        "goliat.studies.base_study.Profiler"
    ) as _mock_profiler_class, patch("goliat.studies.base_study.ProjectManager") as _mock_pm_class:
        mock_config = MagicMock()
        mock_config.get_profiling_config.return_value = {}
        mock_config.__getitem__.side_effect = lambda key: {"execution_control": {"do_setup": True, "do_run": True, "do_extract": True}}.get(
            key
        )
        mock_config.profiling_config_path = str(tmp_path / "profiling_config.json")
        mock_config_class.return_value = mock_config

        from goliat.studies.base_study import BaseStudy

        study = BaseStudy("near_field", config_filename="test_config.json")

        assert study.study_type == "near_field"
        assert study.config == mock_config
        assert study.profiler is not None
        assert study.project_manager is not None


@pytest.mark.skip_on_ci
def test_base_study_check_for_stop_signal():
    """Test checking for stop signal from GUI."""
    with patch("goliat.studies.base_study.Config") as mock_config_class, patch(
        "goliat.studies.base_study.Profiler"
    ) as _mock_profiler_class, patch("goliat.studies.base_study.ProjectManager") as _mock_pm_class:
        mock_config = MagicMock()
        mock_config.get_profiling_config.return_value = {}
        mock_config.__getitem__.return_value = {}
        mock_config.profiling_config_path = "dummy.json"
        mock_config_class.return_value = mock_config

        from goliat.studies.base_study import BaseStudy

        study = BaseStudy("near_field")

        # No GUI, should not raise
        study._check_for_stop_signal()

        # GUI with stop signal
        mock_gui = MagicMock()
        mock_gui.is_stopped.return_value = True
        study.gui = mock_gui

        with pytest.raises(StudyCancelledError, match="Study cancelled by user"):
            study._check_for_stop_signal()


@pytest.mark.skip_on_ci
def test_base_study_subtask_context_manager():
    """Test subtask context manager."""
    with patch("goliat.studies.base_study.Config") as mock_config_class, patch(
        "goliat.studies.base_study.Profiler"
    ) as _mock_profiler_class, patch("goliat.studies.base_study.ProjectManager") as _mock_pm_class:
        mock_config = MagicMock()
        mock_config.get_profiling_config.return_value = {}
        mock_config.__getitem__.return_value = {}
        mock_config.profiling_config_path = "dummy.json"
        mock_config_class.return_value = mock_config

        mock_profiler = MagicMock()
        mock_profiler.subtask_stack = []
        mock_profiler.current_phase = "setup"
        mock_profiler.subtask_times = {"test_task": [0.5]}
        _mock_profiler_class.return_value = mock_profiler

        from goliat.studies.base_study import BaseStudy

        study = BaseStudy("near_field")

        # Test subtask context manager
        with study.subtask("test_task"):
            pass

        # Verify profiler was called
        mock_profiler.subtask.assert_called_once()
