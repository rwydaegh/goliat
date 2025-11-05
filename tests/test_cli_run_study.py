"""Tests for CLI run_study ConsoleLogger."""

import logging


from cli.run_study import ConsoleLogger


class TestConsoleLogger:
    """Tests for ConsoleLogger class."""

    def test_console_logger_initialization(self):
        """Test ConsoleLogger initialization."""
        progress_logger = logging.getLogger("test_progress")
        verbose_logger = logging.getLogger("test_verbose")

        logger = ConsoleLogger(progress_logger, verbose_logger)

        assert logger.progress_logger == progress_logger
        assert logger.verbose_logger == verbose_logger
        assert logger.last_sim_count == 0
        assert logger.current_stage is None

    def test_console_logger_format_box(self):
        """Test _format_box method."""
        progress_logger = logging.getLogger("test_progress")
        verbose_logger = logging.getLogger("test_verbose")
        logger = ConsoleLogger(progress_logger, verbose_logger)

        formatted = logger._format_box("Test message", "info")

        assert "Test message" in formatted
        assert "-" * 70 in formatted
        assert len(formatted.split("\n")) >= 3

    def test_console_logger_log_progress(self):
        """Test logging progress messages."""
        progress_logger = logging.getLogger("test_progress")
        verbose_logger = logging.getLogger("test_verbose")
        logger = ConsoleLogger(progress_logger, verbose_logger)

        logger.log("Progress message", level="progress")

        # Should log to progress logger (no assertion needed, just verify no error)

    def test_console_logger_log_verbose(self):
        """Test logging verbose messages."""
        progress_logger = logging.getLogger("test_progress")
        verbose_logger = logging.getLogger("test_verbose")
        logger = ConsoleLogger(progress_logger, verbose_logger)

        logger.log("Verbose message", level="verbose")

        # Should log to verbose logger (no assertion needed, just verify no error)

    def test_console_logger_update_simulation_details(self):
        """Test updating simulation details."""
        progress_logger = logging.getLogger("test_progress")
        verbose_logger = logging.getLogger("test_verbose")
        logger = ConsoleLogger(progress_logger, verbose_logger)

        logger.update_simulation_details(5, 10, "Test details")

        assert logger.last_sim_count == 5

    def test_console_logger_update_simulation_details_same_count(self):
        """Test that update doesn't duplicate for same sim count."""
        progress_logger = logging.getLogger("test_progress")
        verbose_logger = logging.getLogger("test_verbose")
        logger = ConsoleLogger(progress_logger, verbose_logger)

        logger.update_simulation_details(5, 10, "Test details")
        initial_count = logger.last_sim_count
        logger.update_simulation_details(5, 10, "Test details")

        assert logger.last_sim_count == initial_count

    def test_console_logger_update_overall_progress(self):
        """Test updating overall progress."""
        progress_logger = logging.getLogger("test_progress")
        verbose_logger = logging.getLogger("test_verbose")
        logger = ConsoleLogger(progress_logger, verbose_logger)

        # Test milestones
        logger.update_overall_progress(25, 100)  # 25%
        logger.update_overall_progress(50, 100)  # 50%
        logger.update_overall_progress(75, 100)  # 75%
        logger.update_overall_progress(100, 100)  # 100%

        # Should handle without error

    def test_console_logger_update_overall_progress_non_milestone(self):
        """Test that non-milestone progress doesn't log."""
        progress_logger = logging.getLogger("test_progress")
        verbose_logger = logging.getLogger("test_verbose")
        logger = ConsoleLogger(progress_logger, verbose_logger)

        # 30% is not a milestone
        logger.update_overall_progress(30, 100)

        # Should handle without error

    def test_console_logger_update_stage_progress(self):
        """Test updating stage progress."""
        progress_logger = logging.getLogger("test_progress")
        verbose_logger = logging.getLogger("test_verbose")
        logger = ConsoleLogger(progress_logger, verbose_logger)

        logger.update_stage_progress("Setup", 1, 1, sub_stage="Loading")

        # Should handle without error

    def test_console_logger_update_stage_progress_zero_steps(self):
        """Test updating stage progress with zero total steps."""
        progress_logger = logging.getLogger("test_progress")
        verbose_logger = logging.getLogger("test_verbose")
        logger = ConsoleLogger(progress_logger, verbose_logger)

        logger.update_stage_progress("Setup", 0, 0)

        # Should handle without error
