"""Tests for the optional run_tag simulation-output-isolation feature."""

from unittest.mock import MagicMock

import pytest


class TestApplyRunTag:
    """Unit tests for the pure apply_run_tag helper."""

    def test_none_tag_passthrough(self):
        from goliat.utils.run_tag import apply_run_tag

        assert apply_run_tag("environmental_x_pos_theta", None) == "environmental_x_pos_theta"

    def test_empty_string_tag_passthrough(self):
        from goliat.utils.run_tag import apply_run_tag

        assert apply_run_tag("environmental_x_pos_theta", "") == "environmental_x_pos_theta"

    def test_whitespace_only_tag_passthrough(self):
        from goliat.utils.run_tag import apply_run_tag

        # Whitespace-only sanitizes to empty -> treated as no tag.
        assert apply_run_tag("environmental_x_pos_theta", "   ") == "environmental_x_pos_theta"

    def test_normal_tag(self):
        from goliat.utils.run_tag import apply_run_tag

        assert apply_run_tag("environmental_x_pos_theta", "h0.58") == "environmental_x_pos_theta__h0.58"

    def test_tag_allows_dot_dash_underscore(self):
        from goliat.utils.run_tag import apply_run_tag

        assert apply_run_tag("base", "a.b-c_d") == "base__a.b-c_d"

    def test_tag_with_spaces_sanitized(self):
        from goliat.utils.run_tag import apply_run_tag

        assert apply_run_tag("base", "my tag") == "base__my_tag"

    def test_tag_with_slashes_sanitized(self):
        from goliat.utils.run_tag import apply_run_tag

        # Forward and back slashes must not introduce path separators.
        assert apply_run_tag("base", "a/b\\c") == "base__a_b_c"

    def test_tag_with_illegal_chars_sanitized(self):
        from goliat.utils.run_tag import apply_run_tag

        assert apply_run_tag("base", "a:b*c?d") == "base__a_b_c_d"

    def test_tag_stripped_before_sanitize(self):
        from goliat.utils.run_tag import apply_run_tag

        assert apply_run_tag("base", "  h0.58  ") == "base__h0.58"

    def test_reexported_from_utils_package(self):
        from goliat.utils import apply_run_tag

        assert apply_run_tag("base", "tag") == "base__tag"

    def test_non_string_tag_passthrough(self):
        """Non-string tags (e.g. a misconfigured dict/int in JSON) are ignored, not raised."""
        from goliat.utils.run_tag import apply_run_tag

        assert apply_run_tag("base", {"450": 1}) == "base"
        assert apply_run_tag("base", 123) == "base"


@pytest.mark.skip_on_ci
class TestProjectManagerPathRunTag:
    """Path-construction regression / tagging for ProjectManager."""

    def _make_manager(self, base_dir, run_tag):
        from goliat.project_manager import ProjectManager

        config = MagicMock()
        config.base_dir = base_dir
        config.__getitem__.side_effect = lambda key: {"run_tag": run_tag}.get(key)
        return ProjectManager(
            config=config,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            no_cache=False,
        )

    def test_build_project_path_unchanged_far_field(self, tmp_path):
        # _build_project_path itself is identity-only; run_tag is applied by the
        # caller (create_or_open_project) before this is invoked, so the path
        # here is unchanged regardless of run_tag.
        manager = self._make_manager(str(tmp_path), None)
        project_dir, project_filename = manager._build_project_path("far_field", "Duke", 450, "environmental_x_pos_theta")
        assert project_dir.replace("\\", "/").endswith("results/far_field/duke/450MHz/environmental_x_pos_theta")
        assert project_filename == "far_field_duke_450MHz_environmental_x_pos_theta.smash"

    def test_create_or_open_project_untagged_paths_identical(self, tmp_path):
        manager = self._make_manager(str(tmp_path), None)
        manager.config.__getitem__.side_effect = lambda key: {
            "study_type": "far_field",
            "run_tag": None,
        }.get(key)
        manager.config.build_simulation_config.return_value = {}
        manager.execution_control = {"do_setup": False}
        # do_setup=False reaches an early return path that does not require S4L.
        try:
            manager.create_or_open_project(
                phantom_name="Duke",
                frequency_mhz=450,
                scenario_name="environmental",
                position_name="x_pos",
                orientation_name="theta",
            )
        except Exception:
            # We only care about the path that was constructed, not later S4L work.
            pass
        assert manager.project_path.endswith(
            "results/far_field/duke/450MHz/environmental_x_pos_theta/far_field_duke_450MHz_environmental_x_pos_theta.smash"
        )

    def test_create_or_open_project_tagged_paths_suffixed(self, tmp_path):
        manager = self._make_manager(str(tmp_path), "h0.58")
        manager.config.__getitem__.side_effect = lambda key: {
            "study_type": "far_field",
            "run_tag": "h0.58",
        }.get(key)
        manager.config.build_simulation_config.return_value = {}
        manager.execution_control = {"do_setup": False}
        try:
            manager.create_or_open_project(
                phantom_name="Duke",
                frequency_mhz=450,
                scenario_name="environmental",
                position_name="x_pos",
                orientation_name="theta",
            )
        except Exception:
            pass
        # Both the directory and the .smash filename must carry the suffix.
        assert manager.project_path.endswith(
            "results/far_field/duke/450MHz/environmental_x_pos_theta__h0.58/far_field_duke_450MHz_environmental_x_pos_theta__h0.58.smash"
        )


@pytest.mark.skip_on_ci
class TestResultsExtractorPlacementRunTag:
    """placement_name tagging for ResultsExtractor via config-on-context."""

    def _make_config(self, run_tag):
        config = MagicMock()
        config.__getitem__.side_effect = lambda key: {"run_tag": run_tag}.get(key)
        config.get_auto_cleanup_previous_results.return_value = False
        config.base_dir = "/tmp"
        return config

    def test_placement_name_untagged_unchanged(self):
        from goliat.results_extractor import ResultsExtractor

        extractor = ResultsExtractor.from_params(
            config=self._make_config(None),
            simulation=MagicMock(),
            phantom_name="duke",
            frequency_mhz=450,
            scenario_name="environmental",
            position_name="x_pos",
            orientation_name="theta",
            study_type="far_field",
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
        )
        assert extractor.placement_name == "environmental_x_pos_theta"

    def test_placement_name_tagged_suffixed(self):
        from goliat.results_extractor import ResultsExtractor

        extractor = ResultsExtractor.from_params(
            config=self._make_config("h0.58"),
            simulation=MagicMock(),
            phantom_name="duke",
            frequency_mhz=450,
            scenario_name="environmental",
            position_name="x_pos",
            orientation_name="theta",
            study_type="far_field",
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
        )
        assert extractor.placement_name == "environmental_x_pos_theta__h0.58"
