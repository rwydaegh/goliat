"""Error Advisor - Automatic AI recommendations when errors occur.

This module integrates with GOLIAT's logging system to provide
AI-powered recommendations when warnings or errors are detected.

Usage:
    # In run_study.py or similar:
    from goliat.ai.error_advisor import ErrorAdvisor

    advisor = ErrorAdvisor()

    # Option 1: Check after an error occurs
    try:
        study.run()
    except Exception as e:
        diagnosis = advisor.diagnose_error(e, recent_logs)
        print(f"AI Diagnosis: {diagnosis}")

    # Option 2: Periodic check during long runs
    advisor.check_logs_periodically(log_file_path, interval_seconds=60)
"""

import os
import threading
from typing import Optional, Callable
from dataclasses import dataclass

from .config import AIConfig, get_default_config
from .types import BackendType, SeverityType


@dataclass
class Recommendation:
    """A recommendation from the AI advisor."""

    severity: SeverityType
    message: str
    suggested_fix: str
    related_files: list[str]


class ErrorAdvisor:
    """AI-powered error advisor that monitors logs and provides recommendations.

    The advisor can work in two modes:
    1. On-demand: Call diagnose_error() when an error occurs
    2. Continuous: Call start_monitoring() to periodically check logs

    Example:
        advisor = ErrorAdvisor()

        # On-demand diagnosis
        recommendation = advisor.diagnose_error(
            error_message="iSolve.exe failed with return code 1",
            log_context=recent_log_output
        )

        # Or continuous monitoring
        advisor.start_monitoring(
            log_file="logs/session.progress.log",
            callback=lambda rec: print(f"AI: {rec.message}")
        )
    """

    def __init__(self, backend: BackendType = "openai", enabled: bool = True, config: Optional[AIConfig] = None):
        """Initialize the error advisor.

        Args:
            backend: AI backend to use ("openai" or "local")
            enabled: Whether the advisor is enabled (can be disabled to save costs)
            config: Configuration instance. Uses default if None.
        """
        self.config = config or get_default_config()
        self.config.backend = backend  # Override backend from config
        self.backend: BackendType = backend
        self.enabled = enabled
        self._assistant = None
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._last_log_position = 0
        self._error_count = 0

    @property
    def assistant(self):
        """Lazily initialize the assistant."""
        if self._assistant is None and self.enabled:
            try:
                from goliat.ai.assistant import GOLIATAssistant

                self._assistant = GOLIATAssistant(backend=self.backend)
            except Exception as e:
                print(f"Warning: Could not initialize AI advisor: {e}")
                self.enabled = False
        return self._assistant

    def diagnose_error(self, error_message: str, log_context: str = "", config_context: str = "") -> Optional[Recommendation]:
        """Diagnose an error and return a recommendation.

        Args:
            error_message: The error message or exception string
            log_context: Recent log output for context
            config_context: Relevant config snippet if applicable

        Returns:
            Recommendation object, or None if disabled/failed
        """
        if not self.enabled or not self.assistant:
            return None

        try:
            response = self.assistant.debug(error_message, log_context, config_context)

            # Parse response into structured recommendation
            # (In practice, you might want the LLM to return structured JSON)
            severity = "error"
            if "warning" in error_message.lower():
                severity = "warning"

            return Recommendation(
                severity=severity,
                message=f"AI Diagnosis: {error_message}",
                suggested_fix=response,
                related_files=[],  # Could extract from response
            )
        except Exception as e:
            print(f"Warning: AI diagnosis failed: {e}")
            return None

    def check_logs(self, log_content: str) -> Optional[Recommendation]:
        """Check log content for issues and return recommendations if found.

        Args:
            log_content: The log content to analyze

        Returns:
            Recommendation if issues found, None otherwise
        """
        if not self.enabled or not self.assistant:
            return None

        # Quick heuristic check before calling LLM
        has_potential_issues = any(kw.lower() in log_content.lower() for kw in self.config.error_advisor.warning_keywords)

        if not has_potential_issues:
            return None

        try:
            response = self.assistant.recommend(log_content)

            if response and "Logs look healthy" not in response:
                return Recommendation(
                    severity="warning", message="Potential issues detected in logs", suggested_fix=response, related_files=[]
                )
        except Exception as e:
            print(f"Warning: Log analysis failed: {e}")

        return None

    def start_monitoring(self, log_file: str, callback: Callable[[Recommendation], None], interval_seconds: Optional[int] = None):
        """Start continuous monitoring of a log file.

        Args:
            log_file: Path to the log file to monitor
            callback: Function to call when recommendations are generated
            interval_seconds: How often to check for new log content (uses config default if None)
        """
        if interval_seconds is None:
            interval_seconds = self.config.error_advisor.default_monitoring_interval_seconds
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            print("Warning: Monitoring already running")
            return

        self._stop_monitoring.clear()

        def monitor_loop():
            while not self._stop_monitoring.is_set():
                try:
                    if os.path.exists(log_file):
                        with open(log_file, encoding="utf-8", errors="ignore") as f:
                            f.seek(self._last_log_position)
                            new_content = f.read()
                            self._last_log_position = f.tell()

                        if new_content.strip():
                            recommendation = self.check_logs(new_content)
                            if recommendation:
                                callback(recommendation)
                except Exception as e:
                    print(f"Warning: Monitoring error: {e}")

                self._stop_monitoring.wait(interval_seconds)

        self._monitoring_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitoring_thread.start()

    def stop_monitoring(self):
        """Stop continuous monitoring."""
        self._stop_monitoring.set()
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=self.config.error_advisor.thread_join_timeout_seconds)


# Convenience functions for integration with logging system

_global_advisor: Optional[ErrorAdvisor] = None


def get_advisor() -> ErrorAdvisor:
    """Get or create a global ErrorAdvisor instance."""
    global _global_advisor
    if _global_advisor is None:
        _global_advisor = ErrorAdvisor()
    return _global_advisor


def diagnose_on_error(error: Exception, log_context: str = "") -> Optional[str]:
    """Convenience function to get AI diagnosis for an error.

    Can be called from exception handlers:

        except Exception as e:
            diagnosis = diagnose_on_error(e, recent_logs)
            if diagnosis:
                logger.info(f"AI suggests: {diagnosis}")
    """
    advisor = get_advisor()
    recommendation = advisor.diagnose_error(str(error), log_context)
    if recommendation:
        return recommendation.suggested_fix
    return None


def setup_log_monitoring(log_file: str, on_recommendation: Optional[Callable[[Recommendation], None]] = None):
    """Set up automatic log monitoring with AI analysis.

    Args:
        log_file: Path to the log file to monitor
        on_recommendation: Callback when recommendations are generated.
                          If None, prints to stdout.
    """
    advisor = get_advisor()

    if on_recommendation is None:

        def default_callback(rec: Recommendation):
            separator = "=" * advisor.config.error_advisor.print_separator_length
            print(f"\n{separator}")
            print(f"🤖 AI Advisor ({rec.severity.upper()})")
            print(separator)
            print(rec.suggested_fix)
            print(f"{separator}\n")

        on_recommendation = default_callback

    advisor.start_monitoring(log_file, on_recommendation)
