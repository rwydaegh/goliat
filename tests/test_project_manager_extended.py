"""Tests for goliat.project_manager exceptions and simple methods."""

import pytest

from goliat.project_manager import ProjectCorruptionError


def test_project_corruption_error():
    """Test ProjectCorruptionError exception."""
    with pytest.raises(ProjectCorruptionError):
        raise ProjectCorruptionError("Test error message")

    # Test with custom message
    error = ProjectCorruptionError("Custom message")
    assert str(error) == "Custom message"
