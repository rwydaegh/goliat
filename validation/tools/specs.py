"""Run-spec builders shared by all validation cases (all overrides are GOLIAT config keys)."""

import copy
import json

COMMON = {
    "far_field_setup": {"type": "environmental", "environmental": {"incident_directions": ["x_pos"], "polarizations": ["theta"]}},
    "solver_settings": {"kernel": "software", "server": "localhost"},
    "manual_isolve": False,
    "use_gui": False,
    "use_web": False,
    "execution_control": {
        "do_setup": True,
        "do_run": True,
        "do_extract": True,
        "only_write_input_file": False,
        "batch_run": False,
        "auto_cleanup_previous_results": [],
    },
    "extraction": {"sar": True, "power_balance": True, "sapd": False, "point_sensors": False, "psSAR_averaging_masses_g": [1, 10]},
    "export_material_properties": True,
}


def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            deep_update(d[k], v)
        else:
            d[k] = copy.deepcopy(v)
    return d


def sphere_run(name, freq_mhz, radius_mm, tissue="Muscle", overrides=None, timeout_s=3000, keep_h5=False):
    cfg = deep_update(copy.deepcopy(COMMON), {"phantoms": ["valsphere"], "frequencies_mhz": [freq_mhz]})
    deep_update(cfg, overrides or {})
    return {
        "name": name,
        "phantom": "valsphere",
        "timeout_s": timeout_s,
        "keep_h5": keep_h5,
        "geometry": {"kind": "sphere", "radius_mm": radius_mm, "ico_level": 6, "tissue_entity": tissue, "itis_material": tissue},
        "config": cfg,
    }


def slab_run(name, freq_mhz, lo_mm, hi_mm, direction="z_neg", tissue="Skin", overrides=None, timeout_s=3000, keep_h5=False):
    cfg = deep_update(
        copy.deepcopy(COMMON),
        {
            "phantoms": ["valslab"],
            "frequencies_mhz": [freq_mhz],
            "far_field_setup": {"environmental": {"incident_directions": [direction]}},
        },
    )
    deep_update(cfg, overrides or {})
    return {
        "name": name,
        "phantom": "valslab",
        "timeout_s": timeout_s,
        "keep_h5": keep_h5,
        "skin_group": True,
        "geometry": {"kind": "box", "lo_mm": lo_mm, "hi_mm": hi_mm, "tissue_entity": tissue, "itis_material": tissue},
        "config": cfg,
    }


LONG = {
    "simulation_parameters": {"simulation_time_multiplier": 20, "convergence_level_dB": -50},
    "auto_induced": {"use_xy_diagonal_for_sim_time": False},
}


def write(path, runs):
    json.dump({"runs": runs}, open(path, "w"), indent=1)
