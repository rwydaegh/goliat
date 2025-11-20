"""Parser for iSolve stdout output to detect errors and extract progress information."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Set

from ..logging_manager import LoggingMixin

if TYPE_CHECKING:
    from logging import Logger
    from ..gui_manager import QueueGUI


@dataclass
class ProgressInfo:
    """Extracted progress information from iSolve output."""

    percentage: int
    time_remaining: str
    mcells_per_sec: str


@dataclass
class ParsedLine:
    """Result of parsing a single output line."""

    raw_line: str
    is_error: bool
    error_message: Optional[str]
    has_progress: bool
    progress_info: Optional[ProgressInfo] = None


class ISolveOutputParser(LoggingMixin):
    """Parses iSolve stdout output for errors and progress milestones."""

    def __init__(self, verbose_logger: "Logger", progress_logger: "Logger", gui: Optional["QueueGUI"] = None):
        """Initialize parser.

        Args:
            verbose_logger: Logger for verbose output.
            progress_logger: Logger for progress output.
            gui: Optional GUI proxy for sending progress messages.
        """
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        self.gui = gui
        self.logged_milestones: Set[int] = set()
        self.progress_pattern = re.compile(
            r"\[PROGRESS\]:\s*(\d+)%\s*\[.*?\]\s*Time Update[^@]*estimated remaining time\s+([^@]+?)\s+@\s+([\d.]+)\s+MCells/s"
        )

    def parse_line(self, line: str) -> ParsedLine:
        """Parse a single output line.

        Args:
            line: Raw output line (may include newline).

        Returns:
            ParsedLine with detected information.
        """
        stripped = line.strip()

        # Check for errors
        is_error = self._is_error_line(stripped)
        error_message = stripped if is_error else None

        # Check for progress
        progress_info = self._extract_progress(stripped)

        return ParsedLine(
            raw_line=line,
            is_error=is_error,
            error_message=error_message,
            has_progress=progress_info is not None,
            progress_info=progress_info,
        )

    def should_log_milestone(self, percentage: int) -> bool:
        """Check if milestone should be logged (0%, 33%, 66%).

        Uses 2% data for 0% milestone (more accurate).
        Tracks logged milestones to prevent duplicates.

        Args:
            percentage: Progress percentage from line.

        Returns:
            True if milestone should be logged.
        """
        if percentage == 2 and 0 not in self.logged_milestones:
            return True
        elif percentage >= 33 and 33 not in self.logged_milestones:
            return True
        elif percentage >= 66 and 66 not in self.logged_milestones:
            return True
        return False

    def log_milestone(self, progress_info: ProgressInfo) -> None:
        """Log a progress milestone.

        Args:
            progress_info: Progress information to log.
        """
        percentage = progress_info.percentage

        # For 0%, use 2% data (more accurate) but log as 0%
        if percentage == 2 and 0 not in self.logged_milestones:
            self.logged_milestones.add(0)
            self._log(
                f"      - FDTD: 0% ({progress_info.time_remaining} remaining @ {progress_info.mcells_per_sec} MCells/s)",
                level="progress",
                log_type="default",
            )
        elif percentage >= 33 and 33 not in self.logged_milestones:
            self.logged_milestones.add(33)
            self._log(
                f"      - FDTD: 33% ({progress_info.time_remaining} remaining @ {progress_info.mcells_per_sec} MCells/s)",
                level="progress",
                log_type="default",
            )
        elif percentage >= 66 and 66 not in self.logged_milestones:
            self.logged_milestones.add(66)
            self._log(
                f"      - FDTD: 66% ({progress_info.time_remaining} remaining @ {progress_info.mcells_per_sec} MCells/s)",
                level="progress",
                log_type="default",
            )

    def reset_milestones(self) -> None:
        """Reset logged milestones (for retry attempts)."""
        self.logged_milestones.clear()

    def _is_error_line(self, line: str) -> bool:
        """Check if line contains error pattern.

        iSolve writes errors to stdout (not stderr), so we need to detect them
        in the stdout stream. Common error patterns include:
        - "iSolve: Error:"
        - "Error: bad allocation"
        - "Error: Simulation '...' reports the following failure:"
        - "Error: iSolve framework failed"

        Args:
            line: The output line to check for error patterns.

        Returns:
            True if the line contains an iSolve error pattern, False otherwise.
        """
        if not line:
            return False

        error_patterns = [
            "iSolve: Error:",
            "Error: bad allocation",
            "Error: Simulation",
            "Error: iSolve framework failed",
            "reports the following failure:",
        ]

        return any(pattern in line for pattern in error_patterns)

    def _extract_progress(self, line: str) -> Optional[ProgressInfo]:
        """Extract progress information from line.

        Args:
            line: Output line to check for progress information.

        Returns:
            ProgressInfo if progress found, None otherwise.
        """
        match = self.progress_pattern.search(line)
        if match:
            percentage = int(match.group(1))
            time_remaining = match.group(2).strip()
            mcells_per_sec = match.group(3)

            # Format time remaining as HH:MM:SS
            time_formatted = self._format_time_remaining(time_remaining)

            return ProgressInfo(
                percentage=percentage,
                time_remaining=time_formatted,
                mcells_per_sec=mcells_per_sec,
            )
        return None

    def _format_time_remaining(self, time_str: str) -> str:
        """Convert time remaining string to HH:MM:SS format.

        Parses strings like "1 hours 9 minutes", "3 minutes 27 seconds", or "27 seconds"
        to "1:09:00", "0:03:27", or "0:00:27" respectively.

        Args:
            time_str: Time string from iSolve output.

        Returns:
            Formatted time as "HH:MM:SS" where HH is hours, MM is minutes, and SS is seconds.
        """
        hours = 0
        minutes = 0
        seconds = 0

        # Extract hours (handles both "hour" and "hours")
        hours_match = re.search(r"(\d+)\s+hours?", time_str, re.IGNORECASE)
        if hours_match:
            hours = int(hours_match.group(1))

        # Extract minutes (handles both "minute" and "minutes")
        minutes_match = re.search(r"(\d+)\s+minutes?", time_str, re.IGNORECASE)
        if minutes_match:
            minutes = int(minutes_match.group(1))

        # Extract seconds (handles both "second" and "seconds")
        seconds_match = re.search(r"(\d+)\s+seconds?", time_str, re.IGNORECASE)
        if seconds_match:
            seconds = int(seconds_match.group(1))

        return f"{hours}:{minutes:02d}:{seconds:02d}"
