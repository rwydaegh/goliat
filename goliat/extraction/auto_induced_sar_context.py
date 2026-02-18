"""Context shim and reporter for running the full SAR extraction pipeline on auto-induced H5 files.

The normal SAR extraction pipeline (SarExtractor + Reporter) is designed to work with a live
Sim4Life simulation object via ResultsExtractor as the parent. For auto-induced analysis we
have combined H5 files on disk instead. This module provides:

- _NoOpStudy: a minimal stub that satisfies SarExtractor's `self.parent.study.profiler` usage
  without actually profiling anything.
- AutoInducedSarContext: a duck-typed shim that provides all attributes SarExtractor and
  Reporter read from their `parent` (normally a ResultsExtractor instance).
- AutoInducedReporter: a Reporter subclass whose _get_results_dir() returns the
  candidate-specific output directory instead of the standard results tree.

This lets us reuse SarExtractor and Reporter verbatim — zero changes to those classes.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from .json_encoder import NumpyArrayEncoder
from .reporter import Reporter
from ..results_extractor import ResultsExtractor

if TYPE_CHECKING:
    from ..extraction.auto_induced_processor import AutoInducedProcessor


# ---------------------------------------------------------------------------
# No-op profiler stubs
# ---------------------------------------------------------------------------


class _NoOpSubtask:
    """Context manager that does nothing — replaces profiler.subtask()."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _NoOpProfiler:
    """Profiler stub that satisfies SarExtractor's profiler usage.

    SarExtractor does:
        with self.parent.study.profiler.subtask("extract_sar_statistics"):
            ...
        elapsed = self.parent.study.profiler.subtask_times["extract_sar_statistics"][-1]

    subtask_times must be a mapping that returns a list with at least one element for any key.
    """

    subtask_times: dict = defaultdict(lambda: [0.0])

    def subtask(self, name: str) -> _NoOpSubtask:
        return _NoOpSubtask()


class _NoOpStudy:
    """Minimal study stub — truthy so SarExtractor's `if self.parent.study:` branch runs."""

    profiler = _NoOpProfiler()


# ---------------------------------------------------------------------------
# AutoInducedSarContext — the parent shim
# ---------------------------------------------------------------------------


class AutoInducedSarContext:
    """Duck-typed shim that satisfies the ResultsExtractor interface used by SarExtractor and Reporter.

    SarExtractor.__init__ reads from parent:
        config, phantom_name, placement_name, verbose_logger, progress_logger, gui, study

    SarExtractor methods also read:
        parent.frequency_mhz, parent.study_type

    Reporter reads from parent:
        config.base_dir, study_type, phantom_name, frequency_mhz, placement_name
        (via _get_results_dir — overridden in AutoInducedReporter so these don't matter)

    Reporter also calls:
        parent._log(...), parent.get_deliverable_filenames()
    """

    def __init__(self, processor: "AutoInducedProcessor", candidate_output_dir: Path):
        """Build the context from the processor and the candidate-specific output directory.

        Args:
            processor: The AutoInducedProcessor instance (provides config, loggers, etc.).
            candidate_output_dir: Directory where this candidate's results will be saved,
                e.g. auto_induced/candidate_01/.
        """
        self.config = processor.config
        self.phantom_name = processor.phantom_name
        self.frequency_mhz = processor.freq
        self.study_type = "far_field"  # ensures whole_body_sar key in _store_all_regions_sar
        self.placement_name = "auto_induced"  # only used in Reporter._get_results_dir, which we override
        self.verbose_logger = processor.verbose_logger
        self.progress_logger = processor.progress_logger
        self.gui = processor.gui
        self.study = _NoOpStudy()  # truthy, so SarExtractor's if-branch runs
        self.simulation = None  # not used by SarExtractor
        self._candidate_output_dir = candidate_output_dir

    def _log(self, message: str, level: str = "verbose", log_type: str = "default") -> None:
        """Forward log messages to the appropriate logger.

        Mirrors LoggingMixin._log but without the caller-info introspection overhead.
        Reporter calls self.parent._log(...) so this must exist on the shim.
        """
        extra = {"log_type": log_type, "caller_info": "[AutoInducedSarContext]"}
        if level == "progress":
            self.progress_logger.info(message, extra=extra)
        else:
            self.verbose_logger.info(message, extra=extra)

    def get_deliverable_filenames(self) -> dict:
        """Delegate to ResultsExtractor static method.

        Reporter calls self.parent.get_deliverable_filenames() to get the standard
        filenames (sar_results.json, sar_stats_all_tissues.pkl, etc.).
        """
        return ResultsExtractor.get_deliverable_filenames()


# ---------------------------------------------------------------------------
# AutoInducedReporter — Reporter with overridden results directory
# ---------------------------------------------------------------------------


class AutoInducedReporter(Reporter):
    """Reporter subclass that writes to the candidate-specific output directory.

    The only change from Reporter is _get_results_dir(), which returns the
    candidate_output_dir from the context instead of constructing the standard
    results/{study_type}/{phantom}/{freq}MHz/{placement}/ path.
    """

    def __init__(self, parent: AutoInducedSarContext):
        """Initialise with an AutoInducedSarContext instead of a ResultsExtractor.

        Args:
            parent: The AutoInducedSarContext for this candidate.
        """
        self.parent = parent

    def _get_results_dir(self) -> str:
        """Return the candidate-specific output directory."""
        return str(self.parent._candidate_output_dir)


# ---------------------------------------------------------------------------
# JSON saving helper (mirrors ResultsExtractor._save_json_results)
# ---------------------------------------------------------------------------


def save_candidate_json(results_data: dict, candidate_output_dir: Path) -> None:
    """Save sar_results.json for a single auto-induced candidate.

    Mirrors the relevant parts of ResultsExtractor._save_json_results:
    - Filters out _temp_* keys (used internally by SarExtractor)
    - Writes sar_results.json to candidate_output_dir

    Args:
        results_data: The results dict populated by SarExtractor.
        candidate_output_dir: Directory to write sar_results.json into.
    """
    candidate_output_dir.mkdir(parents=True, exist_ok=True)
    deliverables = ResultsExtractor.get_deliverable_filenames()
    results_filepath = candidate_output_dir / deliverables["json"]

    final_data = {k: v for k, v in results_data.items() if not k.startswith("_temp") and k not in ("point_sensor_data", "sapd_results")}

    with open(results_filepath, "w") as f:
        json.dump(final_data, f, indent=4, cls=NumpyArrayEncoder)
