"""Tests for the free-space validation command."""

import json
import logging

import pytest

from cli import run_free_space_study


class _ConfigStub:
    def __init__(self):
        self.config = {
            "phantoms": ["thelonious"],
            "phantom_definitions": {},
            "antenna_config": {"700": {"model": "example.sab"}},
            "simulation_parameters": {"freespace_antenna_bbox_expansion_mm": [20, 20, 20]},
            "solver_settings": {"kernel": "acceleware"},
        }

    def __getitem__(self, key):
        return self.config.get(key)


def test_create_temp_config_uses_current_schema(tmp_path, monkeypatch):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    monkeypatch.setattr(run_free_space_study, "base_dir", str(tmp_path))

    temp_path = run_free_space_study.create_temp_config(_ConfigStub(), 700)

    with open(temp_path, encoding="utf-8") as handle:
        generated = json.load(handle)

    assert generated["phantoms"] == ["freespace"]
    assert generated["phantom_definitions"]["freespace"]["placements"] == {"do_front_of_eyes_center_vertical": True}
    assert generated["solver_settings"] == {"kernel": "acceleware"}
    assert generated["simulation_parameters"]["freespace_antenna_bbox_expansion_mm"] == pytest.approx([214.13747, 214.13747, 214.13747])


def test_console_logger_accepts_gui_callbacks():
    logger = run_free_space_study.ConsoleLogger(
        logging.getLogger("test.free_space.progress"),
        logging.getLogger("test.free_space.verbose"),
    )

    assert logger.is_stopped() is False
    assert logger.update_stage_progress("Setup", 1, 1, sub_stage="Done") is None
    assert logger.update_simulation_details(1, 1, "freespace") is None
