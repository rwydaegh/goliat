import json

import pytest

from src.data_extractor import get_parameter, get_parameter_from_json


@pytest.fixture
def setup_json_file(tmp_path):
    data = {"level1": {"level2": {"param": "value"}}}
    file_path = tmp_path / "test.json"
    with open(file_path, "w") as f:
        json.dump(data, f)
    return file_path


def test_get_parameter_from_json(setup_json_file):
    # Test existing parameter
    assert get_parameter_from_json(str(setup_json_file), "level1.level2.param") == "value"
    # Test non-existing parameter
    assert get_parameter_from_json(str(setup_json_file), "level1.non_existent") is None
    # Test non-existing file
    assert get_parameter_from_json("non_existent.json", "level1.level2.param") is None


def test_get_parameter(setup_json_file):
    context = {"project_root": str(setup_json_file.parent)}
    source_config = {
        "source_type": "json",
        "file_path_template": "{project_root}/test.json",
        "json_path": "level1.level2.param",
    }
    assert get_parameter(source_config, context) == "value"

    # Test with missing context
    source_config_missing_context = {
        "source_type": "json",
        "file_path_template": "{project_root}/{filename}.json",
        "json_path": "level1.level2.param",
    }
    assert get_parameter(source_config_missing_context, context) is None

    # Test unsupported source type
    unsupported_source_config = {"source_type": "xml"}
    assert get_parameter(unsupported_source_config, context) is None
