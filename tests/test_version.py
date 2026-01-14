"""Tests for goliat.utils.version module."""

from unittest.mock import patch

from goliat.utils.version import (
    _parse_version_from_path,
    _parse_version_string,
    is_sim4life_92_or_later,
    is_version_supported,
    sort_versions_by_preference,
    SUPPORTED_MAJOR_VERSIONS,
    UNSUPPORTED_VERSIONS,
)


class TestParseVersionFromPath:
    """Tests for _parse_version_from_path function."""

    def test_parse_82_version(self):
        """Test parsing 8.2 version from path."""
        path = r"C:\Program Files\Sim4Life_8.2.0.16876\Python"
        result = _parse_version_from_path(path)
        assert result == (8, 2, 0)

    def test_parse_92_version(self):
        """Test parsing 9.2 version from path."""
        path = r"C:\Program Files\Sim4Life_9.2.0.12345\Python"
        result = _parse_version_from_path(path)
        assert result == (9, 2, 0)

    def test_parse_90_version(self):
        """Test parsing 9.0 version from path (unsupported but parseable)."""
        path = r"C:\Program Files\Sim4Life_9.0.0.12345\Python"
        result = _parse_version_from_path(path)
        assert result == (9, 0, 0)

    def test_parse_with_dash(self):
        """Test parsing version with dash instead of underscore."""
        path = r"C:\Program Files\Sim4Life-9.2.0.12345\Python"
        result = _parse_version_from_path(path)
        assert result == (9, 2, 0)

    def test_parse_unix_path(self):
        """Test parsing version from Unix-style path."""
        path = "/opt/Sim4Life_9.2.0/bin/python"
        result = _parse_version_from_path(path)
        assert result == (9, 2, 0)

    def test_parse_no_version(self):
        """Test parsing path without Sim4Life version."""
        path = r"C:\Python311\python.exe"
        result = _parse_version_from_path(path)
        assert result is None

    def test_parse_empty_path(self):
        """Test parsing empty path."""
        result = _parse_version_from_path("")
        assert result is None

    def test_parse_none_path(self):
        """Test parsing None path."""
        result = _parse_version_from_path(None)
        assert result is None


class TestParseVersionString:
    """Tests for _parse_version_string function."""

    def test_parse_simple_version(self):
        """Test parsing simple version string."""
        result = _parse_version_string("9.2.0")
        assert result == (9, 2, 0)

    def test_parse_version_with_build(self):
        """Test parsing version string with build number."""
        result = _parse_version_string("8.2.0.16876")
        assert result == (8, 2, 0)

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = _parse_version_string("")
        assert result is None

    def test_parse_none(self):
        """Test parsing None."""
        result = _parse_version_string(None)
        assert result is None

    def test_parse_invalid_string(self):
        """Test parsing invalid string."""
        result = _parse_version_string("not-a-version")
        assert result is None


class TestIsVersionSupported:
    """Tests for is_version_supported function."""

    def test_82_is_supported(self):
        """Test that 8.2.x is supported."""
        assert is_version_supported((8, 2, 0)) is True
        assert is_version_supported((8, 2, 5)) is True

    def test_92_is_supported(self):
        """Test that 9.2.x is supported."""
        assert is_version_supported((9, 2, 0)) is True
        assert is_version_supported((9, 2, 1)) is True

    def test_90_is_not_supported(self):
        """Test that 9.0.x is explicitly not supported."""
        assert is_version_supported((9, 0, 0)) is False
        assert is_version_supported((9, 0, 5)) is False

    def test_81_is_not_supported(self):
        """Test that 8.1.x is not supported."""
        assert is_version_supported((8, 1, 0)) is False

    def test_100_is_not_supported(self):
        """Test that future versions are not automatically supported."""
        assert is_version_supported((10, 0, 0)) is False

    def test_none_is_not_supported(self):
        """Test that None version is not supported."""
        assert is_version_supported(None) is False


class TestSortVersionsByPreference:
    """Tests for sort_versions_by_preference function."""

    def test_92_comes_before_82(self):
        """Test that 9.2 is preferred over 8.2."""
        paths = [
            r"C:\Program Files\Sim4Life_8.2.0.16876\Python",
            r"C:\Program Files\Sim4Life_9.2.0.12345\Python",
        ]
        result = sort_versions_by_preference(paths)
        assert "Sim4Life_9.2" in result[0]
        assert "Sim4Life_8.2" in result[1]

    def test_90_is_filtered_out(self):
        """Test that 9.0 versions are filtered out."""
        paths = [
            r"C:\Program Files\Sim4Life_8.2.0.16876\Python",
            r"C:\Program Files\Sim4Life_9.0.0.12345\Python",
            r"C:\Program Files\Sim4Life_9.2.0.12345\Python",
        ]
        result = sort_versions_by_preference(paths)
        assert len(result) == 2
        assert not any("Sim4Life_9.0" in p for p in result)

    def test_empty_list(self):
        """Test empty input list."""
        result = sort_versions_by_preference([])
        assert result == []

    def test_single_version(self):
        """Test single version in list."""
        paths = [r"C:\Program Files\Sim4Life_9.2.0.12345\Python"]
        result = sort_versions_by_preference(paths)
        assert len(result) == 1

    def test_unknown_paths_go_last(self):
        """Test that paths without version info go last."""
        paths = [
            r"C:\Python311\python.exe",
            r"C:\Program Files\Sim4Life_9.2.0.12345\Python",
        ]
        result = sort_versions_by_preference(paths)
        assert len(result) == 2
        assert "Sim4Life_9.2" in result[0]


class TestIsSim4Life92OrLater:
    """Tests for is_sim4life_92_or_later function."""

    def test_with_92_path(self):
        """Test detection with 9.2 executable path."""
        with patch("goliat.utils.version.get_sim4life_version", return_value=(9, 2, 0)):
            assert is_sim4life_92_or_later() is True

    def test_with_82_path(self):
        """Test detection with 8.2 executable path."""
        with patch("goliat.utils.version.get_sim4life_version", return_value=(8, 2, 0)):
            assert is_sim4life_92_or_later() is False

    def test_with_no_version(self):
        """Test when version cannot be detected."""
        with patch("goliat.utils.version.get_sim4life_version", return_value=None):
            assert is_sim4life_92_or_later() is False

    def test_with_93_version(self):
        """Test with future 9.3 version."""
        with patch("goliat.utils.version.get_sim4life_version", return_value=(9, 3, 0)):
            assert is_sim4life_92_or_later() is True


class TestConstants:
    """Tests for module constants."""

    def test_supported_versions_include_82_and_92(self):
        """Test that supported versions include 8.2 and 9.2."""
        assert (8, 2) in SUPPORTED_MAJOR_VERSIONS
        assert (9, 2) in SUPPORTED_MAJOR_VERSIONS

    def test_90_is_unsupported(self):
        """Test that 9.0 is in unsupported versions."""
        assert (9, 0) in UNSUPPORTED_VERSIONS

    def test_92_preferred_over_82(self):
        """Test that 9.2 comes before 8.2 in priority list."""
        idx_92 = SUPPORTED_MAJOR_VERSIONS.index((9, 2))
        idx_82 = SUPPORTED_MAJOR_VERSIONS.index((8, 2))
        assert idx_92 < idx_82  # 9.2 should have lower index (higher priority)
