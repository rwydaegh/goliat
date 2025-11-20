"""Execution strategy for manual iSolve subprocess execution."""

import gc
import os
import sys
import time
import traceback
from typing import TYPE_CHECKING

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

try:
    import win32gui
    import win32con
except ImportError:
    win32gui = None  # type: ignore
    win32con = None  # type: ignore

from ..logging_manager import LoggingMixin
from ..utils import StudyCancelledError, open_project
from ..utils.python_interpreter import find_sim4life_root
from .execution_strategy import ExecutionStrategy
from .isolve_output_parser import ISolveOutputParser
from .isolve_process_manager import ISolveProcessManager
from .keep_awake_handler import KeepAwakeHandler
from .post_simulation_handler import PostSimulationHandler
from .retry_handler import RetryHandler

if TYPE_CHECKING:
    from .isolve_process_manager import ISolveProcessManager


def _close_flexnet_window():
    """Close FlexNet License Finder window if it exists."""
    if win32gui and win32con:
        try:
            hwnd = win32gui.FindWindow(None, "FlexNet License Finder")
            if hwnd:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        except Exception:
            pass


class ISolveManualStrategy(ExecutionStrategy, LoggingMixin):
    """Execution strategy for running iSolve.exe directly via subprocess."""

    def __init__(self, *args, **kwargs):
        """Initialize iSolve manual strategy."""
        super().__init__(*args, **kwargs)
        self.current_isolve_process = None
        self.current_process_manager = None

    def _check_for_memory_error_and_exit(self, detected_errors: list, stderr_output: str = "") -> None:
        """Check for memory/alloc errors and terminate process if found.

        Args:
            detected_errors: List of error messages detected in stdout.
            stderr_output: Error output from stderr stream.
        """
        # Combine all error messages for checking
        all_errors = list(detected_errors)
        if stderr_output:
            all_errors.append(stderr_output)

        # Check if any error contains 'alloc' or 'memory' (case-insensitive)
        for error_msg in all_errors:
            error_lower = error_msg.lower()
            if "alloc" in error_lower or "memory" in error_lower:
                # Log error at progress level
                self._log(
                    f"iSolve: Memory/allocation error detected: {error_msg}",
                    level="progress",
                    log_type="error",
                )
                # Terminate the entire Python process
                sys.exit(1)

    def _prepare_isolve_command(self) -> list[str]:
        """Prepare iSolve command and validate paths.

        Returns:
            Command list for subprocess execution.

        Raises:
            FileNotFoundError: If iSolve.exe or input file not found.
            RuntimeError: If simulation object lacks required method.
        """
        s4l_root = find_sim4life_root()
        isolve_path = os.path.join(s4l_root, "Solvers", "iSolve.exe")
        if not os.path.exists(isolve_path):
            raise FileNotFoundError(f"iSolve.exe not found at the expected path: {isolve_path}")

        if not hasattr(self.simulation, "GetInputFileName"):
            raise RuntimeError("Could not get input file name from simulation object.")

        relative_path = self.simulation.GetInputFileName()
        project_dir = os.path.dirname(self.project_path)
        input_file_path = os.path.join(project_dir, relative_path)
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"Solver input file not found at: {input_file_path}")

        solver_kernel = (self.config["solver_settings"] or {}).get("kernel", "Software")
        log_msg = f"Running iSolve with {solver_kernel} on {os.path.basename(input_file_path)}"
        self._log(log_msg, log_type="info")  # verbose only

        return [isolve_path, "-i", input_file_path, "--enable_crash_reports"]

    def _process_output_line(
        self,
        line: str,
        output_parser: ISolveOutputParser,
        keep_awake_handler: KeepAwakeHandler,
        detected_errors: list,
    ) -> None:
        """Process a single output line from iSolve.

        Args:
            line: Raw output line from iSolve.
            output_parser: Parser for iSolve output.
            keep_awake_handler: Handler for keep-awake functionality.
            detected_errors: List to append detected errors to.
        """
        parsed = output_parser.parse_line(line)
        self.verbose_logger.info(parsed.raw_line.strip())

        # Close FlexNet License Finder window if commercial license detected
        if "Using commercial license features." in parsed.raw_line:
            _close_flexnet_window()

        # Detect iSolve error patterns in stdout (iSolve writes errors to stdout)
        if parsed.is_error:
            detected_errors.append(parsed.error_message)
            # Log immediately as progress-level error so it reaches web interface
            self._log(
                f"iSolve: {parsed.error_message}",
                level="progress",
                log_type="error",
            )
            # Check for memory/alloc errors and exit immediately if found
            self._check_for_memory_error_and_exit([parsed.error_message])

        if "Time Update, estimated remaining time" in parsed.raw_line:
            keep_awake_handler.trigger_on_progress()

        # Check for progress milestones (0%, 33%, 66%)
        if parsed.has_progress and parsed.progress_info:
            if output_parser.should_log_milestone(parsed.progress_info.percentage):
                output_parser.log_milestone(parsed.progress_info)

    def _monitor_running_process(
        self,
        process_manager: ISolveProcessManager,
        output_parser: ISolveOutputParser,
        keep_awake_handler: KeepAwakeHandler,
        detected_errors: list,
    ) -> None:
        """Monitor running iSolve process and process output in real-time.

        Args:
            process_manager: Manager for the iSolve subprocess.
            output_parser: Parser for iSolve output.
            keep_awake_handler: Handler for keep-awake functionality.
            detected_errors: List to append detected errors to.
        """
        while process_manager.is_running():
            process_manager.check_stop_signal()

            # Read all available lines from the queue
            lines = process_manager.read_available_lines()
            for line in lines:
                self._process_output_line(line, output_parser, keep_awake_handler, detected_errors)

            # Sleep briefly to prevent busy-wait if no output
            if not lines:
                time.sleep(0.1)

    def _process_remaining_output(
        self,
        process_manager: ISolveProcessManager,
        output_parser: ISolveOutputParser,
        detected_errors: list,
    ) -> None:
        """Process all remaining output after process finishes.

        Args:
            process_manager: Manager for the iSolve subprocess.
            output_parser: Parser for iSolve output.
            detected_errors: List to append detected errors to.
        """
        remaining_lines = process_manager.read_all_remaining_lines()
        for line in remaining_lines:
            parsed = output_parser.parse_line(line)
            self.verbose_logger.info(parsed.raw_line.strip())

            # Close FlexNet License Finder window if commercial license detected
            if "Using commercial license features." in parsed.raw_line:
                _close_flexnet_window()

            # Detect iSolve error patterns in remaining stdout output
            if parsed.is_error:
                detected_errors.append(parsed.error_message)
                # Log immediately as progress-level error so it reaches web interface
                self._log(
                    f"iSolve: {parsed.error_message}",
                    level="progress",
                    log_type="error",
                )
                # Check for memory/alloc errors and exit immediately if found
                self._check_for_memory_error_and_exit([parsed.error_message])

            # Check for progress milestones in remaining output
            if parsed.has_progress and parsed.progress_info:
                if output_parser.should_log_milestone(parsed.progress_info.percentage):
                    output_parser.log_milestone(parsed.progress_info)

    def _prepare_for_retry(
        self,
        retry_handler: RetryHandler,
        output_parser: ISolveOutputParser,
        keep_awake_handler: KeepAwakeHandler,
    ) -> None:
        """Prepare for retry attempt: check memory, reload if needed, reset handlers.

        Args:
            retry_handler: Handler for retry logic.
            output_parser: Parser for iSolve output.
            keep_awake_handler: Handler for keep-awake functionality.
        """
        # Check memory and reload if needed before retry
        if psutil is not None:
            try:
                memory = psutil.virtual_memory()
                if memory.percent > 60.0:
                    # Reload project to free memory before retry
                    open_project(self.project_path)
                    gc.collect()
            except Exception:
                pass

        retry_handler.record_attempt()
        output_parser.reset_milestones()
        keep_awake_handler.reset()

    def _handle_process_failure(
        self,
        process_manager: ISolveProcessManager,
        return_code: int,
        detected_errors: list,
        stderr_output: str,
        retry_handler: RetryHandler,
        output_parser: ISolveOutputParser,
        keep_awake_handler: KeepAwakeHandler,
    ) -> bool:
        """Handle process failure: log errors, cleanup, and prepare for retry if needed.

        Args:
            process_manager: Manager for the iSolve subprocess.
            return_code: Process return code.
            detected_errors: List of errors detected in stdout.
            stderr_output: Error output from stderr.
            retry_handler: Handler for retry logic.
            output_parser: Parser for iSolve output.
            keep_awake_handler: Handler for keep-awake functionality.

        Returns:
            True if should retry, False otherwise.
        """
        # Failed, check for stop signal before retrying
        self._check_for_stop_signal()

        # Log stderr output to progress level with error type if available
        # (only if we didn't already detect errors in stdout)
        # Most iSolve errors are in stdout and already logged above
        if stderr_output and not detected_errors:
            self._log(
                f"iSolve: {stderr_output}",
                level="progress",
                log_type="error",
            )

        # If we detected errors in stdout but process failed, ensure they're visible
        # (they're already logged above, but this ensures completeness)
        if detected_errors and return_code != 0:
            # Errors were already logged when detected in stdout stream
            # This is just for clarity - no duplicate logging needed
            pass

        # Clean up failed process before retrying
        process_manager.cleanup()

        if retry_handler.should_retry(return_code, detected_errors):
            self._prepare_for_retry(retry_handler, output_parser, keep_awake_handler)
            return True
        return False

    def _handle_execution_exception(
        self,
        e: Exception,
        process_manager: ISolveProcessManager | None,
        detected_errors: list,
        retry_handler: RetryHandler,
        output_parser: ISolveOutputParser,
        keep_awake_handler: KeepAwakeHandler,
    ) -> bool:
        """Handle exception during process execution: capture errors, log, and prepare for retry if needed.

        Args:
            e: The exception that occurred.
            process_manager: Manager for the iSolve subprocess (may be None).
            detected_errors: List of errors detected in stdout.
            retry_handler: Handler for retry logic.
            output_parser: Parser for iSolve output.
            keep_awake_handler: Handler for keep-awake functionality.

        Returns:
            True if should retry, False otherwise.
        """
        # Capture stderr output if process exists (as fallback)
        stderr_output = ""
        if process_manager is not None and process_manager.process and process_manager.process.stderr:
            try:
                stderr_output = process_manager.process.stderr.read()
                if stderr_output:
                    stderr_output = stderr_output.strip()
            except Exception:
                pass

        # Check for memory/alloc errors in detected errors, stderr, or exception message
        exception_msg = str(e)
        # Add exception message to detected_errors for checking
        combined_errors = list(detected_errors)
        if exception_msg:
            combined_errors.append(exception_msg)
        self._check_for_memory_error_and_exit(combined_errors, stderr_output)

        # Log stderr output to progress level with error type if available
        # (only if we didn't already detect errors in stdout)
        # Most iSolve errors are in stdout and already logged above
        if stderr_output and not detected_errors:
            self._log(
                f"iSolve: {stderr_output}",
                level="progress",
                log_type="error",
            )

        # Also log the exception itself if it's not already covered
        if not detected_errors:
            self._log(
                f"iSolve: Exception during execution: {e}",
                level="progress",
                log_type="error",
            )

        # Clean up failed process before retrying
        if process_manager is not None and process_manager.process is not None:
            process_manager.cleanup()

        if retry_handler.should_retry(None, detected_errors):
            self._prepare_for_retry(retry_handler, output_parser, keep_awake_handler)
            return True
        return False

    def run(self) -> None:
        """Runs iSolve.exe directly with real-time output logging.

        This method bypasses Sim4Life's API and runs the solver executable directly.
        This is useful when you need more control over the execution environment or when
        the API has issues. The key challenge is capturing output in real-time without
        blocking the main thread.

        The solution uses a background thread with a queue:
        - A daemon thread reads stdout line-by-line and puts lines into a queue
        - The main thread polls the queue non-blockingly and logs output
        - After process completion, remaining output is drained from the queue

        This approach allows the GUI to remain responsive and users to see progress
        updates as they happen. Without threading, reading stdout would block until
        the process finishes, making it impossible to show real-time progress.

        Steps:
        1. Locate iSolve.exe relative to Python executable
        2. Spawn subprocess with stdout/stderr pipes
        3. Start background thread to read stdout into queue
        4. Poll process and queue, logging output without blocking
        5. After completion, reload project to load results into Sim4Life

        Raises:
            FileNotFoundError: If iSolve.exe or input file not found.
            RuntimeError: If iSolve exits with non-zero code or simulation
                          can't be found after reload.
        """
        command = self._prepare_isolve_command()

        try:
            self._log("    - Execute iSolve...", level="progress", log_type="progress")
            with self.profiler.subtask("run_isolve_execution"):
                output_parser = ISolveOutputParser(self.verbose_logger, self.progress_logger, self.gui)
                keep_awake_handler = KeepAwakeHandler(self.config)
                retry_handler = RetryHandler(self.progress_logger, self.gui)

                # Call keep_awake before first attempt
                keep_awake_handler.trigger_before_retry()

                while True:
                    # Check for stop signal before starting new subprocess
                    self._check_for_stop_signal()

                    # Call keep_awake before each retry attempt
                    if retry_handler.get_attempt_number() > 0:
                        keep_awake_handler.trigger_before_retry()

                    # Track iSolve errors detected in stdout (iSolve writes errors to stdout, not stderr)
                    # Initialize outside try block so it's available in exception handler
                    detected_errors = []
                    process_manager: ISolveProcessManager | None = None

                    try:
                        process_manager = ISolveProcessManager(command, self.gui, self.verbose_logger, self.progress_logger)
                        process_manager.start()
                        self.current_isolve_process = process_manager.process
                        self.current_process_manager = process_manager

                        # Monitor running process and process output in real-time
                        self._monitor_running_process(process_manager, output_parser, keep_awake_handler, detected_errors)

                        # Process has finished, get the return code
                        return_code = process_manager.get_return_code()

                        # Process all remaining output after process finishes
                        self._process_remaining_output(process_manager, output_parser, detected_errors)

                        # Read stderr output from iSolve (as fallback - most errors are in stdout)
                        stderr_output = process_manager.read_stderr()

                        # Check for memory/alloc errors and exit if found
                        self._check_for_memory_error_and_exit(detected_errors, stderr_output)

                        # Clear process tracking since it's finished
                        self.current_isolve_process = None
                        self.current_process_manager = None

                        if return_code == 0:
                            # Success, break out of retry loop
                            break

                        # Handle process failure and check if should retry
                        # Only handle failure if return_code is not None (process finished)
                        if return_code is not None:
                            should_retry = self._handle_process_failure(
                                process_manager,
                                return_code,
                                detected_errors,
                                stderr_output,
                                retry_handler,
                                output_parser,
                                keep_awake_handler,
                            )
                        else:
                            # Process didn't finish properly, don't retry
                            should_retry = False
                        if not should_retry:
                            break

                    except StudyCancelledError:
                        # Re-raise cancellation errors immediately
                        if process_manager is not None:
                            process_manager.cleanup()
                        raise
                    except Exception as e:
                        # Handle execution exception and check if should retry
                        should_retry = self._handle_execution_exception(
                            e, process_manager, detected_errors, retry_handler, output_parser, keep_awake_handler
                        )
                        if not should_retry:
                            break

            elapsed = self.profiler.subtask_times["run_isolve_execution"][-1]
            self._log(f"      - Subtask 'run_isolve_execution' done in {elapsed:.2f}s", log_type="verbose")
            self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

            # Post-simulation steps
            post_handler = PostSimulationHandler(self.project_path, self.profiler, self.verbose_logger, self.progress_logger)
            post_handler.wait_and_reload()

        except StudyCancelledError:
            # Clean up subprocess on cancellation
            self._cleanup()
            raise
        except Exception as e:
            # Clean up subprocess on any exception
            self._cleanup()
            self._log(
                f"An unexpected error occurred while running iSolve.exe: {e}",
                level="progress",
                log_type="error",
            )
            self.verbose_logger.error(traceback.format_exc())
            raise
        finally:
            # Always ensure cleanup, even on successful completion
            self._cleanup()

    def _cleanup(self) -> None:
        """Clean up process and threads."""
        if self.current_process_manager is not None:
            self.current_process_manager.cleanup()
            self.current_process_manager = None
        self.current_isolve_process = None
