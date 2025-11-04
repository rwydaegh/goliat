"""Tests for goliat.extraction.reporter module."""

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from goliat.extraction.reporter import Reporter


@pytest.fixture
def mock_parent():
    """Create a mock parent ResultsExtractor."""
    parent = MagicMock()
    parent.config = MagicMock()
    parent.config.base_dir = "/tmp"
    parent.study_type = "near_field"
    parent.phantom_name = "thelonious"
    parent.frequency_mhz = 700
    parent.placement_name = "front_of_eyes_center_vertical"
    parent._log = MagicMock()
    parent.get_deliverable_filenames.return_value = {
        "pkl": "results.pkl",
        "html": "results.html",
    }
    return parent


@pytest.fixture
def mock_parent_far_field():
    """Create a mock parent for far-field study."""
    parent = MagicMock()
    parent.config = MagicMock()
    parent.config.base_dir = "/tmp"
    parent.study_type = "far_field"
    parent.phantom_name = "thelonious"
    parent.frequency_mhz = 700
    parent.placement_name = "environmental_theta_x_pos"
    parent._log = MagicMock()
    parent.get_deliverable_filenames.return_value = {
        "pkl": "results.pkl",
        "html": "results.html",
    }
    return parent


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    df = pd.DataFrame(
        {
            "Tissue": ["Brain", "Skin", "Eyes"],
            "SAR_1g": [1.2, 0.8, 1.5],
            "SAR_10g": [1.0, 0.7, 1.3],
        }
    )
    tissue_groups = {
        "brain_group": ["Brain"],
        "skin_group": ["Skin"],
        "eyes_group": ["Eyes"],
    }
    group_sar_stats = {
        "brain_group": {"SAR_1g": 1.2, "SAR_10g": 1.0},
        "skin_group": {"SAR_1g": 0.8, "SAR_10g": 0.7},
    }
    results_data = {
        "peak_sar_details": {
            "peak_location_x": 0.1,
            "peak_location_y": 0.2,
            "peak_location_z": 0.3,
            "peak_value": 2.5,
        },
        "point_sensor_data": {"sensor1": {"time_s": [0, 1, 2], "E_mag_V_m": [1, 2, 3]}},
    }
    return df, tissue_groups, group_sar_stats, results_data


class TestReporter:
    """Tests for Reporter class."""

    def test_reporter_initialization(self, mock_parent):
        """Test reporter initialization."""
        reporter = Reporter(mock_parent)
        assert reporter.parent == mock_parent

    @patch("goliat.extraction.reporter.os.makedirs")
    @patch("builtins.open", create=True)
    @patch("pickle.dump")
    def test_save_reports_pickle(self, mock_pickle_dump, mock_open, mock_makedirs, mock_parent, sample_data):
        """Test saving pickle report."""
        df, tissue_groups, group_sar_stats, results_data = sample_data
        reporter = Reporter(mock_parent)
        reporter.save_reports(df, tissue_groups, group_sar_stats, results_data)

        mock_makedirs.assert_called()
        mock_pickle_dump.assert_called_once()

    @patch("goliat.extraction.reporter.os.makedirs")
    @patch("builtins.open", create=True)
    def test_save_reports_html(self, mock_open, mock_makedirs, mock_parent, sample_data):
        """Test saving HTML report."""
        df, tissue_groups, group_sar_stats, results_data = sample_data
        reporter = Reporter(mock_parent)

        # Mock file write
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        reporter.save_reports(df, tissue_groups, group_sar_stats, results_data)

        mock_makedirs.assert_called()
        mock_file.write.assert_called()

    def test_get_results_dir_near_field(self, mock_parent):
        """Test getting results directory for near-field study."""
        reporter = Reporter(mock_parent)
        results_dir = reporter._get_results_dir()

        expected = os.path.join(
            "/tmp",
            "results",
            "near_field",
            "thelonious",
            "700MHz",
            "front_of_eyes_center_vertical",
        )
        assert results_dir == expected

    def test_get_results_dir_far_field(self, mock_parent_far_field):
        """Test getting results directory for far-field study."""
        reporter = Reporter(mock_parent_far_field)
        results_dir = reporter._get_results_dir()

        expected = os.path.join(
            "/tmp",
            "results",
            "far_field",
            "thelonious",
            "700MHz",
            "environmental_theta_x_pos",
        )
        assert results_dir == expected

    def test_build_html_content(self, mock_parent, sample_data):
        """Test building HTML content."""
        df, tissue_groups, group_sar_stats, results_data = sample_data
        reporter = Reporter(mock_parent)
        html_content = reporter._build_html_content(df, tissue_groups, group_sar_stats, results_data)

        assert "<h2>Tissue Group Composition</h2>" in html_content
        assert "<h2>Grouped SAR Statistics</h2>" in html_content
        assert "<h2>Peak SAR Details</h2>" in html_content
        assert "Brain" in html_content or "brain" in html_content.lower()
