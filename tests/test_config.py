import json
import os

import pytest

from src.config import Config


# Create a dummy base_config.json for testing
@pytest.fixture(scope="module")
def dummy_configs(tmp_path_factory):
    project_dir = tmp_path_factory.mktemp("project")
    config_dir = project_dir / "configs"
    data_dir = project_dir / "data"
    config_dir.mkdir()
    data_dir.mkdir()

    base_config_path = config_dir / "base_config.json"
    near_field_config_path = config_dir / "near_field_config.json"

    base_content = {
        "simulation_parameters": {
            "global_auto_termination": "GlobalAutoTerminationUserDefined",
            "convergence_level_dB": -15,
        },
        "download_email": "test@example.com",
    }
    near_field_content = {
        "extends": "base_config.json",
        "study_type": "near_field",
        "phantoms": ["thelonious"],
        "frequencies_mhz": [700],
    }

    with open(base_config_path, "w") as f:
        json.dump(base_content, f)
    with open(near_field_config_path, "w") as f:
        json.dump(near_field_content, f)

    # Create dummy material_name_mapping.json
    material_mapping_path = data_dir / "material_name_mapping.json"
    material_content = {
        "thelonious": {
            "Brain": "Brain (IT'IS)",
            "_tissue_groups": {"brain_group": ["Brain"]},
        }
    }
    with open(material_mapping_path, "w") as f:
        json.dump(material_content, f)

    # Create dummy profiling_config.json
    profiling_config_path = config_dir / "profiling_config.json"
    profiling_content = {"near_field": {"avg_setup_time": 100.0}}
    with open(profiling_config_path, "w") as f:
        json.dump(profiling_content, f)

    return {
        "base_dir": project_dir,
        "config_dir": config_dir,
        "data_dir": data_dir,
        "base_config_path": base_config_path,
        "near_field_config_path": near_field_config_path,
        "material_mapping_path": material_mapping_path,
        "profiling_config_path": profiling_config_path,
    }


def test_config_load_and_inheritance(dummy_configs):
    # Temporarily set environment variables for oSPARC credentials
    os.environ["OSPARC_API_KEY"] = "dummy_key"
    os.environ["OSPARC_API_SECRET"] = "dummy_secret"
    os.environ["OSPARC_API_SERVER"] = "https://api.example.com"

    config_instance = Config(
        dummy_configs["base_dir"], "configs/near_field_config.json"
    )

    assert config_instance.get_setting("study_type") == "near_field"
    assert config_instance.get_setting("download_email") == "test@example.com"
    assert (
        config_instance.get_setting("simulation_parameters.convergence_level_dB") == -15
    )
    assert config_instance.get_setting("phantoms") == ["thelonious"]
    assert config_instance.get_setting("frequencies_mhz") == [700]

    # Test material mapping
    material_map = config_instance.get_material_mapping("thelonious")
    assert material_map["Brain"] == "Brain (IT'IS)"
    assert "brain_group" in material_map["_tissue_groups"]

    # Test profiling config
    profiling_data = config_instance.get_profiling_config("near_field")
    assert profiling_data["avg_setup_time"] == 100.0

    # Test oSPARC credentials
    osparc_creds = config_instance.get_osparc_credentials()
    assert osparc_creds["api_key"] == "dummy_key"
    assert osparc_creds["api_secret"] == "dummy_secret"
    assert osparc_creds["api_server"] == "https://api.example.com"
    assert osparc_creds["api_version"] == "v0"

    # Clean up environment variables
    del os.environ["OSPARC_API_KEY"]
    del os.environ["OSPARC_API_SECRET"]
    del os.environ["OSPARC_API_SERVER"]


def test_get_setting_non_existent(dummy_configs):
    config_instance = Config(
        dummy_configs["base_dir"], "configs/near_field_config.json"
    )
    assert (
        config_instance.get_setting("non_existent.path", "default_value")
        == "default_value"
    )
    assert (
        config_instance.get_setting("simulation_parameters.non_existent_param") is None
    )


def test_config_path_resolution(dummy_configs):
    # Test with full path
    full_path_config = Config(
        dummy_configs["base_dir"], str(dummy_configs["near_field_config_path"])
    )
    assert full_path_config.get_setting("study_type") == "near_field"

    # Test with just filename (assumes in 'configs' dir)
    filename_only_config = Config(dummy_configs["base_dir"], "near_field_config")
    assert filename_only_config.get_setting("study_type") == "near_field"


def test_osparc_credentials_missing(dummy_configs):
    # Ensure environment variables are not set
    if "OSPARC_API_KEY" in os.environ:
        del os.environ["OSPARC_API_KEY"]
    if "OSPARC_API_SECRET" in os.environ:
        del os.environ["OSPARC_API_SECRET"]
    if "OSPARC_API_SERVER" in os.environ:
        del os.environ["OSPARC_API_SERVER"]

    config_instance = Config(
        dummy_configs["base_dir"], "configs/near_field_config.json"
    )
    with pytest.raises(ValueError, match="Missing oSPARC credentials"):
        config_instance.get_osparc_credentials()
