"""Tests for goliat.extraction.cleaner module."""

from unittest.mock import MagicMock, patch

import pytest

from goliat.extraction.cleaner import Cleaner


@pytest.fixture
def mock_parent():
    """Create a mock parent ResultsExtractor."""
    parent = MagicMock()
    parent.config = MagicMock()
    parent.config.get_auto_cleanup_previous_results.return_value = []
    parent.study = None
    parent._log = MagicMock()
    return parent


@pytest.fixture
def mock_parent_with_study():
    """Create a mock parent with study."""
    parent = MagicMock()
    parent.config = MagicMock()
    parent.config.get_auto_cleanup_previous_results.return_value = ["output"]
    parent.study = MagicMock()
    parent.study.project_manager = MagicMock()
    parent.study.project_manager.project_path = "/tmp/test.smash"
    parent._log = MagicMock()
    return parent


class TestCleaner:
    """Tests for Cleaner class."""

    def test_cleaner_initialization(self, mock_parent):
        """Test cleaner initialization."""
        cleaner = Cleaner(mock_parent)
        assert cleaner.parent == mock_parent

    def test_cleanup_simulation_files_no_cleanup_types(self, mock_parent):
        """Test cleanup when no cleanup types are configured."""
        mock_parent.config.get_auto_cleanup_previous_results.return_value = []
        cleaner = Cleaner(mock_parent)
        cleaner.cleanup_simulation_files()

        # Should return early without doing anything
        mock_parent._log.assert_not_called()

    def test_cleanup_simulation_files_no_study(self, mock_parent):
        """Test cleanup when study object is not available."""
        mock_parent.config.get_auto_cleanup_previous_results.return_value = ["output"]
        mock_parent.study = None
        cleaner = Cleaner(mock_parent)
        cleaner.cleanup_simulation_files()

        # Should log warning
        mock_parent._log.assert_called()
        assert "WARNING" in str(mock_parent._log.call_args)

    def test_cleanup_simulation_files_no_project_path(self, mock_parent):
        """Test cleanup when project path is not set."""
        mock_parent.config.get_auto_cleanup_previous_results.return_value = ["output"]
        mock_parent.study = MagicMock()
        mock_parent.study.project_manager = MagicMock()
        mock_parent.study.project_manager.project_path = None
        cleaner = Cleaner(mock_parent)
        cleaner.cleanup_simulation_files()

        # Should log warning
        mock_parent._log.assert_called()
        assert "WARNING" in str(mock_parent._log.call_args)

    @patch("goliat.extraction.cleaner.glob.glob")
    @patch("goliat.extraction.cleaner.os.remove")
    def test_cleanup_simulation_files_output(self, mock_remove, mock_glob, mock_parent_with_study):
        """Test cleanup of output files."""
        mock_glob.return_value = ["/tmp/test_Results/file1_Output.h5", "/tmp/test_Results/file2_Output.h5"]
        mock_remove.return_value = None

        cleaner = Cleaner(mock_parent_with_study)
        mock_parent_with_study.config.get_auto_cleanup_previous_results.return_value = ["output"]
        cleaner.cleanup_simulation_files()

        # Should delete 2 files
        assert mock_remove.call_count == 2
        mock_parent_with_study._log.assert_called()

    @patch("goliat.extraction.cleaner.glob.glob")
    @patch("goliat.extraction.cleaner.os.remove")
    def test_cleanup_simulation_files_input(self, mock_remove, mock_glob, mock_parent_with_study):
        """Test cleanup of input files."""
        mock_glob.return_value = ["/tmp/test_Results/file1_Input.h5"]

        cleaner = Cleaner(mock_parent_with_study)
        mock_parent_with_study.config.get_auto_cleanup_previous_results.return_value = ["input"]
        cleaner.cleanup_simulation_files()

        assert mock_remove.call_count == 1

    @patch("goliat.extraction.cleaner.glob.glob")
    @patch("goliat.extraction.cleaner.os.remove")
    def test_cleanup_simulation_files_smash(self, mock_remove, mock_glob, mock_parent_with_study):
        """Test cleanup of project files."""
        mock_glob.return_value = ["/tmp/test.smash"]

        cleaner = Cleaner(mock_parent_with_study)
        mock_parent_with_study.config.get_auto_cleanup_previous_results.return_value = ["smash"]
        cleaner.cleanup_simulation_files()

        assert mock_remove.call_count == 1

    @patch("goliat.extraction.cleaner.glob.glob")
    @patch("goliat.extraction.cleaner.os.remove")
    def test_cleanup_simulation_files_multiple_types(self, mock_remove, mock_glob, mock_parent_with_study):
        """Test cleanup of multiple file types."""

        def glob_side_effect(pattern):
            if "*_Output.h5" in pattern:
                return ["/tmp/test_Results/file1_Output.h5"]
            elif "*_Input.h5" in pattern:
                return ["/tmp/test_Results/file1_Input.h5"]
            elif "*.smash" in pattern:
                return ["/tmp/test.smash"]
            return []

        mock_glob.side_effect = glob_side_effect

        cleaner = Cleaner(mock_parent_with_study)
        mock_parent_with_study.config.get_auto_cleanup_previous_results.return_value = ["output", "input", "smash"]
        cleaner.cleanup_simulation_files()

        assert mock_remove.call_count == 3

    @patch("goliat.extraction.cleaner.glob.glob")
    @patch("goliat.extraction.cleaner.os.remove")
    def test_cleanup_simulation_files_delete_error(self, mock_remove, mock_glob, mock_parent_with_study):
        """Test handling of delete errors."""
        mock_glob.return_value = ["/tmp/test_Results/file1_Output.h5"]
        mock_remove.side_effect = PermissionError("Access denied")

        cleaner = Cleaner(mock_parent_with_study)
        mock_parent_with_study.config.get_auto_cleanup_previous_results.return_value = ["output"]
        cleaner.cleanup_simulation_files()

        # Should log warning but continue
        mock_parent_with_study._log.assert_called()
        assert "Warning" in str(mock_parent_with_study._log.call_args)

    @patch("goliat.extraction.cleaner.glob.glob")
    @patch("goliat.extraction.cleaner.os.remove")
    def test_cleanup_simulation_files_unknown_type(self, mock_remove, mock_glob, mock_parent_with_study):
        """Test cleanup with unknown cleanup type."""
        cleaner = Cleaner(mock_parent_with_study)
        mock_parent_with_study.config.get_auto_cleanup_previous_results.return_value = ["unknown_type"]
        cleaner.cleanup_simulation_files()

        # Should not delete anything
        mock_remove.assert_not_called()
