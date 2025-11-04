"""Tests for goliat.results_extractor module."""

from goliat.results_extractor import ResultsExtractor


class TestResultsExtractor:
    """Tests for ResultsExtractor class."""

    def test_get_deliverable_filenames(self):
        """Test static method get_deliverable_filenames."""
        filenames = ResultsExtractor.get_deliverable_filenames()

        assert isinstance(filenames, dict)
        assert "json" in filenames
        assert "pkl" in filenames
        assert "html" in filenames
        assert filenames["json"] == "sar_results.json"
        assert filenames["pkl"] == "sar_stats_all_tissues.pkl"
        assert filenames["html"] == "sar_stats_all_tissues.html"
