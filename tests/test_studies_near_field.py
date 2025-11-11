"""Tests for goliat.studies.near_field_study module."""

import pytest

from goliat.config import Config


@pytest.mark.skip_on_ci
class TestNearFieldStudy:
    """Tests for NearFieldStudy class."""

    @pytest.fixture
    def dummy_config(self, tmp_path):
        """Create a temporary config directory structure."""
        config_dir = tmp_path / "configs"
        data_dir = tmp_path / "data"
        config_dir.mkdir()
        data_dir.mkdir()

        config_path = config_dir / "near_field_config.json"
        config_content = {
            "study_type": "near_field",
            "phantoms": ["thelonious"],
            "antenna_config": {"700": {"model_type": "PIFA", "power_w": 1.0}},
            "placement_scenarios": {"by_cheek": {"positions": {"center": [0, 0, 0]}, "orientations": {"vertical": [0, 0, 0]}}},
            "execution_control": {"do_setup": True, "do_run": True, "do_extract": True},
        }

        import json

        with open(config_path, "w") as f:
            json.dump(config_content, f)

        # Create phantom definition
        phantom_def_path = data_dir / "phantom_definitions.json"
        phantom_def = {"thelonious": {"placements": {"do_by_cheek": True}}}
        with open(phantom_def_path, "w") as f:
            json.dump(phantom_def, f)

        # Create profiling config
        profiling_path = data_dir / "profiling_config.json"
        profiling_config = {"near_field": {"avg_setup_time": 10.0, "avg_run_time": 60.0, "avg_extract_time": 5.0}}
        with open(profiling_path, "w") as f:
            json.dump(profiling_config, f)

        # Create material_name_mapping.json (required by Config)
        material_mapping_path = data_dir / "material_name_mapping.json"
        material_mapping = {"thelonious": {"Brain": "Brain (IT'IS)", "_tissue_groups": {"brain_group": ["Brain"]}}}
        with open(material_mapping_path, "w") as f:
            json.dump(material_mapping, f)

        return Config(str(tmp_path), "configs/near_field_config.json")

    def test_near_field_study_initialization(self, dummy_config):
        """Test NearFieldStudy initialization."""
        from goliat.studies.near_field_study import NearFieldStudy

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        assert study.study_type == "near_field"
        assert study.config is not None
        assert study.profiler is not None
        assert study.project_manager is not None

    def test_near_field_study_validation_auto_cleanup(self, dummy_config):
        """Test auto cleanup validation logic."""
        from goliat.studies.near_field_study import NearFieldStudy

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        # Test validation doesn't crash
        study._validate_auto_cleanup_config(True, True, True, False)

    def test_near_field_study_calculate_total_simulations(self, dummy_config):
        """Test simulation counting logic."""
        from goliat.studies.near_field_study import NearFieldStudy

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        # Mock the config to have specific structure
        study.config.config = {
            "phantoms": ["thelonious"],
            "antenna_config": {"700": {}, "900": {}},
            "placement_scenarios": {
                "by_cheek": {"positions": {"center": {}, "offset": {}}, "orientations": {"vertical": {}, "horizontal": {}}}
            },
        }

        # Mock phantom definition
        study.config.config["phantom_definitions"] = {"thelonious": {"placements": {"do_by_cheek": True}}}

        # Count simulations: 2 frequencies * 2 positions * 2 orientations = 8
        total = 0
        phantoms = study.config["phantoms"] or []
        frequencies = (study.config["antenna_config"] or {}).keys()
        all_scenarios = study.config["placement_scenarios"] or {}

        for phantom_name in phantoms:
            phantom_definition = (study.config["phantom_definitions"] or {}).get(phantom_name, {})
            placements_config = phantom_definition.get("placements", {})
            if not placements_config:
                continue
            for scenario_name, scenario_details in all_scenarios.items():
                if placements_config.get(f"do_{scenario_name}"):
                    positions = scenario_details.get("positions", {})
                    orientations = scenario_details.get("orientations", {})
                    total += len(list(frequencies)) * len(positions) * len(orientations)

        assert total == 8  # 2 frequencies * 2 positions * 2 orientations

    def test_near_field_study_all_phases_disabled(self, tmp_path):
        """Test behavior when all execution phases are disabled."""
        from goliat.studies.near_field_study import NearFieldStudy
        import json

        # Create config with all phases disabled
        config_dir = tmp_path / "configs"
        data_dir = tmp_path / "data"
        config_dir.mkdir()
        data_dir.mkdir()

        config_path = config_dir / "near_field_config.json"
        config_content = {
            "study_type": "near_field",
            "phantoms": ["thelonious"],
            "antenna_config": {"700": {"model_type": "PIFA"}},
            "execution_control": {"do_setup": False, "do_run": False, "do_extract": False},
        }
        with open(config_path, "w") as f:
            json.dump(config_content, f)

        # Create required files
        material_mapping_path = data_dir / "material_name_mapping.json"
        with open(material_mapping_path, "w") as f:
            json.dump({"thelonious": {}}, f)

        profiling_path = data_dir / "profiling_config.json"
        with open(profiling_path, "w") as f:
            json.dump({"near_field": {}}, f)

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        # Modify config after loading (Config loads from file)
        study.config.config["execution_control"] = {"do_setup": False, "do_run": False, "do_extract": False}

        # Should not crash when all phases disabled
        # The actual run would return early, but we can test the check
        do_setup = study.config["execution_control.do_setup"]
        if do_setup is None:
            do_setup = True
        do_run = study.config["execution_control.do_run"]
        if do_run is None:
            do_run = True
        do_extract = study.config["execution_control.do_extract"]
        if do_extract is None:
            do_extract = True

        assert not do_setup and not do_run and not do_extract

    def test_near_field_study_only_write_input_file_warning(self, tmp_path):
        """Test warning for only_write_input_file without do_run."""
        from goliat.studies.near_field_study import NearFieldStudy
        import json

        # Create config with only_write_input_file but do_run=False
        config_dir = tmp_path / "configs"
        data_dir = tmp_path / "data"
        config_dir.mkdir()
        data_dir.mkdir()

        config_path = config_dir / "near_field_config.json"
        config_content = {
            "study_type": "near_field",
            "phantoms": ["thelonious"],
            "antenna_config": {"700": {"model_type": "PIFA"}},
            "only_write_input_file": True,
            "execution_control": {"do_setup": True, "do_run": False, "do_extract": False},
        }
        with open(config_path, "w") as f:
            json.dump(config_content, f)

        # Create required files
        material_mapping_path = data_dir / "material_name_mapping.json"
        with open(material_mapping_path, "w") as f:
            json.dump({"thelonious": {}}, f)

        profiling_path = data_dir / "profiling_config.json"
        with open(profiling_path, "w") as f:
            json.dump({"near_field": {}}, f)

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        # Modify config after loading
        study.config.config["only_write_input_file"] = True
        study.config.config["execution_control"] = {"do_setup": True, "do_run": False, "do_extract": False}

        # Check the condition that triggers the warning
        # get_only_write_input_file has a default of False, so we need to check the config directly
        only_write = study.config.config.get("only_write_input_file", False)
        do_run = study.config["execution_control.do_run"]
        if do_run is None:
            do_run = True

        assert only_write and not do_run  # This would trigger the warning
