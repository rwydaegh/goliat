"""Tidy long-format loader for env-FF protocol replicates (sT1.5.4).

Walks ``goliat/results/far_field/{phantom}/{freq}MHz/environmental_{axis}_{sign}_{pol}/sar_results.json``
and returns one row per (phantom, freq, direction, polarisation, metric).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

PHANTOMS = ("duke", "eartha", "ella", "thelonious")
FREQS_MHZ = (450, 700, 835, 1450, 2140, 2450, 3500, 5200, 5800)
DIRECTIONS = ("x_pos", "x_neg", "y_pos", "y_neg", "z_pos", "z_neg")
POLARIZATIONS = ("theta", "phi")

# Scalar metrics carried in sar_results.json. Loaded keys map to short metric names.
METRICS: dict[str, str] = {
    "whole_body_sar": "WB_SAR",
    "peak_sar_10g_W_kg": "psSAR10g",
    "skin_group_weighted_avg_sar": "skin_avg",
    "skin_group_peak_sar": "skin_peak",
    "brain_group_weighted_avg_sar": "brain_avg",
    "brain_group_peak_sar": "brain_peak",
    "eyes_group_weighted_avg_sar": "eyes_avg",
    "eyes_group_peak_sar": "eyes_peak",
    "genitals_group_weighted_avg_sar": "genitals_avg",
    "genitals_group_peak_sar": "genitals_peak",
}

_DIR_RE = re.compile(r"^environmental_(x|y|z)_(pos|neg)_(theta|phi)$")


def _read_one(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read %s: %s", path, exc)
        return None


def load_far_field(
    results_root: Path | str,
    phantoms: tuple[str, ...] = PHANTOMS,
    freqs_mhz: tuple[int, ...] = FREQS_MHZ,
) -> pd.DataFrame:
    """Build a tidy long DataFrame from the env-FF result tree.

    Returns columns: ``phantom, freq_mhz, direction, polarization, metric, Y, logY``.
    One row per (phantom, freq, direction, polarisation, metric).
    """
    root = Path(results_root)
    rows: list[dict] = []

    for phantom in phantoms:
        for freq in freqs_mhz:
            freq_dir = root / phantom / f"{freq}MHz"
            if not freq_dir.is_dir():
                log.warning("Missing freq dir: %s", freq_dir)
                continue
            for sim_dir in sorted(freq_dir.iterdir()):
                m = _DIR_RE.match(sim_dir.name)
                if not m:
                    continue
                axis, sign, pol = m.groups()
                direction = f"{axis}_{sign}"

                payload = _read_one(sim_dir / "sar_results.json")
                if payload is None:
                    continue

                for json_key, metric in METRICS.items():
                    val = payload.get(json_key)
                    if val is None or (isinstance(val, float) and not np.isfinite(val)) or val <= 0:
                        # Non-positive metrics cannot be log-transformed; skip them.
                        continue
                    rows.append(
                        dict(
                            phantom=phantom,
                            freq_mhz=int(freq),
                            direction=direction,
                            polarization=pol,
                            metric=metric,
                            Y=float(val),
                            logY=float(np.log(val)),
                        )
                    )

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(f"No env-FF results found under {root}")
    return df
