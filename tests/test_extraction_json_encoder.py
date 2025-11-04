"""Tests for goliat.extraction.json_encoder module."""

import json

import numpy as np
import pytest

from goliat.extraction.json_encoder import NumpyArrayEncoder


class TestNumpyArrayEncoder:
    """Tests for NumpyArrayEncoder class."""

    def test_encode_numpy_array(self):
        """Test encoding numpy array."""
        data = np.array([1, 2, 3, 4, 5])
        result = json.dumps(data, cls=NumpyArrayEncoder)
        decoded = json.loads(result)
        assert decoded == [1, 2, 3, 4, 5]

    def test_encode_numpy_2d_array(self):
        """Test encoding 2D numpy array."""
        data = np.array([[1, 2], [3, 4]])
        result = json.dumps(data, cls=NumpyArrayEncoder)
        decoded = json.loads(result)
        assert decoded == [[1, 2], [3, 4]]

    def test_encode_numpy_integer(self):
        """Test encoding numpy integer."""
        data = np.int64(42)
        result = json.dumps(data, cls=NumpyArrayEncoder)
        decoded = json.loads(result)
        assert decoded == 42
        assert isinstance(decoded, int)

    def test_encode_numpy_float(self):
        """Test encoding numpy float."""
        data = np.float64(3.14)
        result = json.dumps(data, cls=NumpyArrayEncoder)
        decoded = json.loads(result)
        assert decoded == pytest.approx(3.14)
        assert isinstance(decoded, float)

    def test_encode_mixed_types(self):
        """Test encoding dictionary with mixed numpy types."""
        data = {
            "array": np.array([1, 2, 3]),
            "integer": np.int32(10),
            "float": np.float32(2.5),
            "regular_string": "test",
            "regular_int": 5,
        }
        result = json.dumps(data, cls=NumpyArrayEncoder)
        decoded = json.loads(result)
        assert decoded["array"] == [1, 2, 3]
        assert decoded["integer"] == 10
        assert decoded["float"] == pytest.approx(2.5)
        assert decoded["regular_string"] == "test"
        assert decoded["regular_int"] == 5

    def test_encode_regular_types(self):
        """Test that regular Python types are handled normally."""
        data = {"string": "test", "int": 42, "float": 3.14, "list": [1, 2, 3]}
        result = json.dumps(data, cls=NumpyArrayEncoder)
        decoded = json.loads(result)
        assert decoded == data
