"""Tests for configurable psSAR averaging masses in SarExtractor and analysis strategies."""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from goliat.analysis.base_strategy import _add_extra_mass_columns
from goliat.extraction.sar_extractor import SarExtractor, find_peak_sar_column, normalize_averaging_masses


def test_normalize_defaults_and_values():
    assert normalize_averaging_masses(None) == [10.0]
    assert normalize_averaging_masses([10, 1, 1]) == [1.0, 10.0]
    assert normalize_averaging_masses(1) == [1.0]


@pytest.mark.parametrize("bad", [[], [0], [-1], ["1"], [True], "10", {}])
def test_normalize_rejects_invalid(bad):
    with pytest.raises(ValueError):
        normalize_averaging_masses(bad)


def test_find_peak_sar_column():
    cols = ["Tissue", "Mass-Averaged SAR", "Peak Spatial-Average SAR[IEEE/IEC62704-1] (1g)"]
    assert find_peak_sar_column(cols, 1) == cols[2]
    cols10 = ["Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)", "Peak Spatial-Average SAR[IEEE/IEC62704-1] (1g)"]
    assert find_peak_sar_column(cols10, 10) == cols10[0]
    assert find_peak_sar_column(cols10, 5) is None


def _make_extractor(masses):
    parent = MagicMock()
    parent.config = {"extraction.psSAR_averaging_masses_g": masses}
    ex = SarExtractor(parent, {})
    ex.tissue_grouper = MagicMock()
    ex.tissue_grouper.group_tissues.return_value = {"eyes_group": ["Eye"]}
    ex._log = MagicMock()
    return ex


def test_additional_masses_skipped_by_default():
    ex = _make_extractor([10])
    ex._evaluate_sar_statistics = MagicMock()
    ex._extract_additional_averaging_masses(MagicMock())
    ex._evaluate_sar_statistics.assert_not_called()
    assert ex.results_data == {}


def test_additional_mass_1g_stores_keys_and_backward_compatible():
    ex = _make_extractor([1, 10])
    col = "Peak Spatial-Average SAR[IEEE/IEC62704-1] (1g)"
    df = pd.DataFrame(
        {
            "Tissue": ["All Regions", "Eye"],
            "Total Mass": [10.0, 1.0],
            "Mass-Averaged SAR": [0.1, 0.2],
            col: [3.0, 2.0],
        }
    )
    ex._evaluate_sar_statistics = MagicMock(return_value=object())
    ex._create_sar_dataframe = MagicMock(return_value=df)
    ex.extract_peak_sar_details = MagicMock()
    em = MagicMock()
    ex._extract_additional_averaging_masses(em)

    ex._evaluate_sar_statistics.assert_called_once_with(em, target_mass_g=1.0)
    ex.extract_peak_sar_details.assert_called_once_with(em, target_mass_g=1.0)
    assert ex.results_data["peak_sar_1g_W_kg"] == 3.0
    assert ex.results_data["eyes_group_peak_sar_1g"] == 2.0
    assert "peak_sar_10g_W_kg" not in ex.results_data


def test_invalid_config_does_not_raise():
    ex = _make_extractor([0])
    ex._evaluate_sar_statistics = MagicMock()
    ex._extract_additional_averaging_masses(MagicMock())
    ex._evaluate_sar_statistics.assert_not_called()


def test_evaluator_target_mass_is_set():
    ex = _make_extractor([1])
    evaluator = MagicMock()
    ex.analysis.em_evaluators.SarStatisticsEvaluator.return_value = evaluator
    ex.units = MagicMock()
    ex._evaluate_sar_statistics(MagicMock(), target_mass_g=1.0)
    assert evaluator.PeakSAR.TargetMass[0] == 1.0
    ex.units.Unit.assert_called_with("g")


def test_peak_details_key_for_1g():
    ex = _make_extractor([1])
    ev = MagicMock()
    dc = MagicMock()
    dc.Keys.return_value = ["PeakValue"]
    dc.FieldValue.return_value = 1.5
    ev.Outputs.__getitem__.return_value.Data.DataSimpleDataCollection = dc
    ex.analysis.em_evaluators.AverageSarFieldEvaluator.return_value = ev
    ex.units = MagicMock()
    ex.extract_peak_sar_details(MagicMock(), target_mass_g=1.0)
    assert ex.results_data["peak_sar_details_1g"] == {"PeakValue": 1.5}
    assert "peak_sar_details" not in ex.results_data


def test_analysis_columns():
    entry = {}
    summary = {
        "peak_sar_10g_W_kg": 1.0,
        "peak_sar_1g_W_kg": 2.0,
        "eyes_group_peak_sar_1g": 4.0,
        "eyes_group_peak_sar": 9.0,
        "other": None,
    }
    _add_extra_mass_columns(entry, summary, 0.5)
    assert entry == {"peak_sar_1g": 1.0, "psSAR1g_eyes": 2.0}
