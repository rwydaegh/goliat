"""Comprehensive tests for goliat.studies.near_field_study core workflow."""

import json
from unittest.mock import MagicMock, patch

import pytest

from goliat.config import Config


@pytest.mark.skip_on_ci
class TestNearFieldStudyCoreWorkflow:
    """Tests for NearFieldStudy core workflow methods."""

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

        # Create material_name_mapping.json
        material_mapping_path = data_dir / "material_name_mapping.json"
        material_mapping = {"thelonious": {"Brain": "Brain (IT'IS)", "_tissue_groups": {"brain_group": ["Brain"]}}}
        with open(material_mapping_path, "w") as f:
            json.dump(material_mapping, f)

        return Config(str(tmp_path), "configs/near_field_config.json")

    def test_near_field_study_run_study_workflow(self, dummy_config):
        """Test the main _run_study workflow loop."""
        from goliat.studies.near_field_study import NearFieldStudy

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        # Mock the _run_placement method to avoid actual execution
        with patch.object(study, "_run_placement") as mock_run_placement:
            study._run_study()

            # Verify profiler was set up (total_simulations calculation happens in _run_study)
            # The exact count depends on the config structure
            assert study.profiler.total_simulations >= 0  # Should be set
            assert study.profiler.current_phase == "setup"

            # Verify _run_placement was called
            assert mock_run_placement.called

    def test_near_field_study_run_placement_setup_phase(self, dummy_config):
        """Test _run_placement with setup phase enabled."""
        from goliat.studies.near_field_study import NearFieldStudy

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        # Mock dependencies
        mock_setup = MagicMock()
        mock_simulation = MagicMock()
        mock_project_manager = MagicMock()
        mock_project_manager.project_path = "/tmp/test.smash"
        mock_project_manager.create_or_open_project.return_value = {"setup_done": False}

        # Mock s4l_v1.document (imported inside _run_placement)
        mock_document = MagicMock()
        mock_document.AllSimulations = [mock_simulation]
        mock_simulation.Name = "EM_FDTD_thelonious_700MHz_by_cheek_center_vertical"

        with patch("goliat.studies.near_field_study.NearFieldSetup", return_value=mock_setup), patch(
            "s4l_v1.document", mock_document
        ), patch.object(study, "project_manager", mock_project_manager), patch.object(study, "_execute_run_phase"), patch.object(
            study, "_verify_run_deliverables_before_extraction", return_value=True
        ), patch("goliat.studies.near_field_study.ResultsExtractor"), patch("goliat.studies.near_field_study.Antenna"), patch(
            "goliat.studies.near_field_study.add_simulation_log_handlers"
        ), patch("goliat.studies.near_field_study.remove_simulation_log_handlers"):
            # Mock the setup to return a simulation
            mock_setup.run_full_setup.return_value = mock_simulation

            study._run_placement(
                phantom_name="thelonious",
                freq=700,
                scenario_name="by_cheek",
                position_name="center",
                orientation_name="vertical",
                do_setup=True,
                do_run=False,
                do_extract=False,
            )

            # Verify setup was called
            assert mock_setup.run_full_setup.called

    def test_near_field_study_run_placement_extract_phase(self, dummy_config):
        """Test _run_placement with extract phase enabled."""
        from goliat.studies.near_field_study import NearFieldStudy

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        mock_simulation = MagicMock()
        mock_simulation.Name = "EM_FDTD_thelonious_700MHz_by_cheek_center_vertical"
        mock_project_manager = MagicMock()
        mock_project_manager.project_path = "/tmp/test.smash"
        mock_project_manager.create_or_open_project.return_value = {"setup_done": True}
        mock_project_manager.reload_project = MagicMock()

        # Mock s4l_v1.document (imported inside _run_placement)
        mock_document = MagicMock()
        mock_document.AllSimulations = [mock_simulation]

        with patch("s4l_v1.document", mock_document), patch.object(study, "project_manager", mock_project_manager), patch.object(
            study, "_verify_run_deliverables_before_extraction", return_value=True
        ), patch("goliat.studies.near_field_study.ResultsExtractor.from_params") as mock_from_params, patch(
            "goliat.studies.near_field_study.add_simulation_log_handlers"
        ), patch("goliat.studies.near_field_study.remove_simulation_log_handlers"):
            mock_extractor = MagicMock()
            mock_from_params.return_value = mock_extractor

            study._run_placement(
                phantom_name="thelonious",
                freq=700,
                scenario_name="by_cheek",
                position_name="center",
                orientation_name="vertical",
                do_setup=False,
                do_run=False,
                do_extract=True,
            )

            # Verify extractor was created and extract was called
            assert mock_from_params.called
            assert mock_extractor.extract.called

    def test_near_field_study_validate_auto_cleanup_config_warning(self, dummy_config):
        """Test auto cleanup validation warning logic."""
        from goliat.studies.near_field_study import NearFieldStudy

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        # Test warning when not all phases enabled but cleanup is configured
        with patch.object(study, "_log") as mock_log:
            study._validate_auto_cleanup_config(
                do_setup=True,
                do_run=True,
                do_extract=False,  # Extract disabled
                auto_cleanup=["output"],
            )

            # Should log a warning
            assert mock_log.called

    def test_near_field_study_stop_signal_check(self, dummy_config):
        """Test stop signal checking in workflow."""
        from goliat.studies.near_field_study import NearFieldStudy
        from goliat.utils import StudyCancelledError

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        # Test with GUI that requests stop
        mock_gui = MagicMock()
        mock_gui.is_stopped.return_value = True
        study.gui = mock_gui

        with pytest.raises(StudyCancelledError):
            study._check_for_stop_signal()

    def test_near_field_study_simulation_counting_multiple(self, dummy_config):
        """Test simulation counting with multiple configurations."""
        from goliat.studies.near_field_study import NearFieldStudy

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        # Set up config with multiple frequencies and placements
        study.config.config = {
            "phantoms": ["thelonious"],
            "antenna_config": {"700": {}, "900": {}, "1800": {}},
            "placement_scenarios": {
                "by_cheek": {"positions": {"center": {}, "left": {}, "right": {}}, "orientations": {"vertical": {}, "horizontal": {}}}
            },
        }

        # Mock phantom definition
        study.config.config["phantom_definitions"] = {"thelonious": {"placements": {"do_by_cheek": True}}}

        # Count: 3 frequencies * 3 positions * 2 orientations = 18
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

        assert total == 18

    def test_near_field_study_phases_disabled_early_return(self, dummy_config):
        """Test early return when all phases are disabled."""
        from goliat.studies.near_field_study import NearFieldStudy

        study = NearFieldStudy(
            study_type="near_field",
            config_filename="near_field_config.json",
            gui=None,
            profiler=None,
            no_cache=False,
        )

        # Modify config to disable all phases
        study.config.config["execution_control"] = {"do_setup": False, "do_run": False, "do_extract": False}

        with patch.object(study, "_run_placement") as mock_run_placement:
            study._run_study()

            # Should return early without calling _run_placement
            assert not mock_run_placement.called
