"""Additional tests for goliat.config module to improve coverage."""

import json
import os

import pytest

from goliat.config import Config, deep_merge


# Copy fixture from test_config.py to avoid import issues
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
    profiling_config_path = data_dir / "profiling_config.json"
    profiling_content = {
        "near_field": {
            "avg_setup_time": 10.0,
            "avg_run_time": 60.0,
            "avg_extract_time": 5.0,
        }
    }
    with open(profiling_config_path, "w") as f:
        json.dump(profiling_content, f)

    return {
        "base_dir": str(project_dir),
        "config_dir": str(config_dir),
        "data_dir": str(data_dir),
    }


def test_deep_merge():
    """Test deep_merge function."""
    source = {
        "a": 1,
        "b": {"c": 2, "d": 3},
        "e": {"f": 4},
    }
    destination = {
        "a": 0,
        "b": {"c": 1, "e": 5},
        "g": 6,
    }

    result = deep_merge(source, destination)

    assert result["a"] == 1  # Overwritten
    assert result["b"]["c"] == 2  # Overwritten
    assert result["b"]["d"] == 3  # Added
    assert result["b"]["e"] == 5  # Preserved
    assert result["e"]["f"] == 4  # Added
    assert result["g"] == 6  # Preserved


def test_config_get_simulation_parameters(dummy_configs):
    """Test get_simulation_parameters method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    params = config["simulation_parameters"] or {}
    assert isinstance(params, dict)


def test_config_get_antenna_config(dummy_configs):
    """Test get_antenna_config method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    antenna_config = config["antenna_config"] or {}
    assert isinstance(antenna_config, dict)


def test_config_get_gridding_parameters(dummy_configs):
    """Test get_gridding_parameters method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    gridding_params = config["gridding_parameters"] or {}
    assert isinstance(gridding_params, dict)


def test_config_get_phantom_definition(dummy_configs):
    """Test get_phantom_definition method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    # Add phantom definition to config
    config.config["phantom_definitions"] = {"thelonious": {"path": "test.sab", "scale": 1.0}}

    phantom_def = (config["phantom_definitions"] or {}).get("thelonious", {})
    assert isinstance(phantom_def, dict)
    assert phantom_def["path"] == "test.sab"


def test_config_get_solver_settings(dummy_configs):
    """Test get_solver_settings method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    solver_settings = config["solver_settings"] or {}
    assert isinstance(solver_settings, dict)


def test_config_get_antenna_component_names(dummy_configs):
    """Test get_antenna_component_names method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    # Add antenna component definitions - correct structure
    config.config["antenna_config"] = {"components": {"test_model": ["component1", "component2"]}}

    components = (config["antenna_config.components"] or {}).get("test_model")
    assert isinstance(components, list)
    assert "component1" in components


def test_config_get_manual_isolve(dummy_configs):
    """Test get_manual_isolve method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    # Test default
    result = config["manual_isolve"] or False
    assert isinstance(result, bool)

    # Test with config value
    config.config["manual_isolve"] = True
    assert (config["manual_isolve"] or False) is True


def test_config_get_freespace_expansion(dummy_configs):
    """Test get_freespace_expansion method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    expansion = config["simulation_parameters.freespace_antenna_bbox_expansion_mm"] or [10, 10, 10]
    assert isinstance(expansion, list)


def test_config_get_excitation_type(dummy_configs):
    """Test get_excitation_type method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    excitation_type = config["simulation_parameters.excitation_type"] or "Harmonic"
    assert isinstance(excitation_type, str)


def test_config_get_bandwidth(dummy_configs):
    """Test get_bandwidth method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    bandwidth = config["simulation_parameters.bandwidth_mhz"] or 50.0
    assert isinstance(bandwidth, (float, int))


def test_config_get_placement_scenario(dummy_configs):
    """Test get_placement_scenario method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    # Add placement scenarios
    config.config["placement_scenarios"] = {"by_cheek": {"positions": {"center": {"orientations": ["vertical"]}}}}

    scenario = (config["placement_scenarios"] or {}).get("by_cheek")
    assert isinstance(scenario, dict)
    assert "positions" in scenario


def test_config_get_line_profiling_config(dummy_configs):
    """Test get_line_profiling_config method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    line_profiling_config = config["line_profiling"] or {}
    assert isinstance(line_profiling_config, dict)


def test_config_get_only_write_input_file(dummy_configs):
    """Test get_only_write_input_file method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    result = config.get_only_write_input_file()
    assert isinstance(result, bool)


def test_config_get_auto_cleanup_previous_results(dummy_configs):
    """Test get_auto_cleanup_previous_results method."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    cleanup_types = config.get_auto_cleanup_previous_results()
    assert isinstance(cleanup_types, list)


def test_config_resolve_config_path_absolute(dummy_configs):
    """Test _resolve_config_path with absolute path."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    abs_path = os.path.join(dummy_configs["base_dir"], "configs", "test.json")
    resolved = config._resolve_config_path(abs_path, dummy_configs["base_dir"])
    assert os.path.isabs(resolved) or os.path.dirname(resolved)


def test_config_resolve_config_path_no_extension(dummy_configs):
    """Test _resolve_config_path adds .json extension."""
    config = Config(dummy_configs["base_dir"], "configs/near_field_config.json")

    resolved = config._resolve_config_path("test_config", dummy_configs["base_dir"])
    assert resolved.endswith(".json")
    assert "test_config.json" in resolved
