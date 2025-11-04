import logging
from unittest.mock import MagicMock


from goliat.logging_manager import LoggingMixin, setup_loggers, shutdown_loggers


def test_setup_loggers():
    progress_logger, verbose_logger, _ = setup_loggers()
    assert isinstance(progress_logger, logging.Logger)
    assert isinstance(verbose_logger, logging.Logger)
    assert progress_logger.name == "progress"
    assert verbose_logger.name == "verbose"
    shutdown_loggers()


class TestLoggingMixin:
    def test_log_method(self):
        mixin = LoggingMixin()
        mixin.progress_logger = MagicMock()
        mixin.verbose_logger = MagicMock()
        mixin.gui = None

        mixin._log("test progress", level="progress")
        mixin.progress_logger.info.assert_called_once()

        mixin._log("test verbose", level="verbose")
        mixin.verbose_logger.info.assert_called_once()
