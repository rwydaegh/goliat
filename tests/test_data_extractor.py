"""Tests for goliat.data_extractor module."""

import json


from goliat.data_extractor import get_parameter, get_parameter_from_json


class TestGetParameterFromJson:
    """Tests for get_parameter_from_json function."""

    def test_get_parameter_from_json_simple_key(self, tmp_path):
        """Test extracting a simple key from JSON."""
        json_file = tmp_path / "test.json"
        data = {"key": "value"}
        with open(json_file, "w") as f:
            json.dump(data, f)

        result = get_parameter_from_json(str(json_file), "key")
        assert result == "value"

    def test_get_parameter_from_json_nested_key(self, tmp_path):
        """Test extracting a nested key from JSON."""
        json_file = tmp_path / "test.json"
        data = {"section": {"subsection": {"key": "value"}}}
        with open(json_file, "w") as f:
            json.dump(data, f)

        result = get_parameter_from_json(str(json_file), "section.subsection.key")
        assert result == "value"

    def test_get_parameter_from_json_missing_file(self):
        """Test when JSON file doesn't exist."""
        result = get_parameter_from_json("nonexistent.json", "key")
        assert result is None

    def test_get_parameter_from_json_missing_key(self, tmp_path):
        """Test when key doesn't exist in JSON."""
        json_file = tmp_path / "test.json"
        data = {"other_key": "value"}
        with open(json_file, "w") as f:
            json.dump(data, f)

        result = get_parameter_from_json(str(json_file), "missing_key")
        assert result is None

    def test_get_parameter_from_json_missing_nested_key(self, tmp_path):
        """Test when nested key doesn't exist."""
        json_file = tmp_path / "test.json"
        data = {"section": {"other_key": "value"}}
        with open(json_file, "w") as f:
            json.dump(data, f)

        result = get_parameter_from_json(str(json_file), "section.missing_key")
        assert result is None

    def test_get_parameter_from_json_invalid_json(self, tmp_path):
        """Test when JSON file is invalid."""
        json_file = tmp_path / "test.json"
        with open(json_file, "w") as f:
            f.write("invalid json {")

        result = get_parameter_from_json(str(json_file), "key")
        assert result is None


class TestGetParameter:
    """Tests for get_parameter function."""

    def test_get_parameter_json_source(self, tmp_path):
        """Test getting parameter from JSON source."""
        json_file = tmp_path / "data.json"
        data = {"result": {"value": 42}}
        with open(json_file, "w") as f:
            json.dump(data, f)

        source_config = {
            "source_type": "json",
            "file_path_template": "data.json",
            "json_path": "result.value",
        }
        context = {"project_root": str(tmp_path)}

        result = get_parameter(source_config, context)
        assert result == 42

    def test_get_parameter_json_source_missing_file(self, tmp_path):
        """Test getting parameter when JSON file is missing."""
        source_config = {
            "source_type": "json",
            "file_path_template": "missing.json",
            "json_path": "key",
        }
        context = {"project_root": str(tmp_path)}

        result = get_parameter(source_config, context)
        assert result is None

    def test_get_parameter_json_source_missing_context(self, tmp_path):
        """Test getting parameter when context is missing."""
        json_file = tmp_path / "data.json"
        data = {"value": 42}
        with open(json_file, "w") as f:
            json.dump(data, f)

        source_config = {
            "source_type": "json",
            "file_path_template": "data.json",
            "json_path": "value",
        }
        context = {}  # Missing project_root

        # Should handle missing context gracefully
        result = get_parameter(source_config, context)
        # Could be None or handle error, depending on implementation
        assert result is None or isinstance(result, type(None))

    def test_get_parameter_unsupported_source_type(self, tmp_path):
        """Test getting parameter with unsupported source type."""
        source_config = {
            "source_type": "unsupported",
            "file_path_template": "data.json",
            "json_path": "key",
        }
        context = {"project_root": str(tmp_path)}

        result = get_parameter(source_config, context)
        assert result is None

    def test_get_parameter_missing_source_type(self, tmp_path):
        """Test getting parameter when source_type is missing."""
        source_config = {
            "file_path_template": "data.json",
            "json_path": "key",
        }
        context = {"project_root": str(tmp_path)}

        result = get_parameter(source_config, context)
        assert result is None

    def test_get_parameter_missing_file_path_template(self, tmp_path):
        """Test getting parameter when file_path_template is missing."""
        source_config = {
            "source_type": "json",
            "json_path": "key",
        }
        context = {"project_root": str(tmp_path)}

        result = get_parameter(source_config, context)
        assert result is None

    def test_get_parameter_missing_json_path(self, tmp_path):
        """Test getting parameter when json_path is missing."""
        json_file = tmp_path / "data.json"
        data = {"value": 42}
        with open(json_file, "w") as f:
            json.dump(data, f)

        source_config = {
            "source_type": "json",
            "file_path_template": "data.json",
        }
        context = {"project_root": str(tmp_path)}

        result = get_parameter(source_config, context)
        assert result is None
