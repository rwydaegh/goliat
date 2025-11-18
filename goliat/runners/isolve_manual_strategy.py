"""Execution strategy for manual iSolve subprocess execution."""

import os
import time
import traceback
from typing import TYPE_CHECKING

from ..logging_manager import LoggingMixin
from ..utils import StudyCancelledError
from ..utils.python_interpreter import find_sim4life_root
from .execution_strategy import ExecutionStrategy
from .isolve_output_parser import ISolveOutputParser
from .isolve_process_manager import ISolveProcessManager
from .keep_awake_handler import KeepAwakeHandler
from .post_simulation_handler import PostSimulationHandler
from .retry_handler import RetryHandler

if TYPE_CHECKING:
    from .isolve_process_manager import ISolveProcessManager


class ISolveManualStrategy(ExecutionStrategy, LoggingMixin):
    """Execution strategy for running iSolve.exe directly via subprocess."""

    def __init__(self, *args, **kwargs):
        """Initialize iSolve manual strategy."""
        super().__init__(*args, **kwargs)
        self.current_isolve_process = None
        self.current_process_manager = None

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
        # --- 1. Setup: Find paths and prepare command ---
        # The input file is now written in the run() method before this is called.

        # Find Sim4Life root directory (works for both direct Python and venvs)
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

        command = [isolve_path, "-i", input_file_path, "--enable_crash_reports"]

        try:
            self._log("    - Execute iSolve...", level="progress", log_type="progress")
            with self.profiler.subtask("run_isolve_execution"):
                output_parser = ISolveOutputParser(self.verbose_logger, self.progress_logger)
                keep_awake_handler = KeepAwakeHandler(self.config)
                retry_handler = RetryHandler(self.progress_logger)

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

                        # --- 3. Main loop: Monitor process and log output without blocking ---
                        while process_manager.is_running():
                            process_manager.check_stop_signal()

                            # Read all available lines from the queue
                            lines = process_manager.read_available_lines()
                            for line in lines:
                                parsed = output_parser.parse_line(line)
                                self.verbose_logger.info(parsed.raw_line.strip())

                                # Detect iSolve error patterns in stdout (iSolve writes errors to stdout)
                                if parsed.is_error:
                                    detected_errors.append(parsed.error_message)
                                    # Log immediately as progress-level error so it reaches web interface
                                    self._log(
                                        f"iSolve: {parsed.error_message}",
                                        level="progress",
                                        log_type="error",
                                    )

                                if "Time Update, estimated remaining time" in parsed.raw_line:
                                    keep_awake_handler.trigger_on_progress()

                                # Check for progress milestones (0%, 33%, 66%)
                                if parsed.has_progress and parsed.progress_info:
                                    if output_parser.should_log_milestone(parsed.progress_info.percentage):
                                        output_parser.log_milestone(parsed.progress_info)

                            # Sleep briefly to prevent busy-wait if no output
                            if not lines:
                                time.sleep(0.1)

                        # Process has finished, get the return code
                        return_code = process_manager.get_return_code()

                        # Read all remaining output
                        remaining_lines = process_manager.read_all_remaining_lines()
                        for line in remaining_lines:
                            parsed = output_parser.parse_line(line)
                            self.verbose_logger.info(parsed.raw_line.strip())

                            # Detect iSolve error patterns in remaining stdout output
                            if parsed.is_error:
                                detected_errors.append(parsed.error_message)
                                # Log immediately as progress-level error so it reaches web interface
                                self._log(
                                    f"iSolve: {parsed.error_message}",
                                    level="progress",
                                    log_type="error",
                                )

                            # Check for progress milestones in remaining output
                            if parsed.has_progress and parsed.progress_info:
                                if output_parser.should_log_milestone(parsed.progress_info.percentage):
                                    output_parser.log_milestone(parsed.progress_info)

                        # Read stderr output from iSolve (as fallback - most errors are in stdout)
                        stderr_output = process_manager.read_stderr()

                        # Clear process tracking since it's finished
                        self.current_isolve_process = None
                        self.current_process_manager = None

                        if return_code == 0:
                            # Success, break out of retry loop
                            break
                        else:
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
                                retry_handler.record_attempt()
                                output_parser.reset_milestones()
                                keep_awake_handler.reset()
                    except StudyCancelledError:
                        # Re-raise cancellation errors immediately
                        if process_manager is not None:
                            process_manager.cleanup()
                        raise
                    except Exception as e:
                        # Capture stderr output if process exists (as fallback)
                        stderr_output = ""
                        if process_manager is not None and process_manager.process and process_manager.process.stderr:
                            try:
                                stderr_output = process_manager.process.stderr.read()
                                if stderr_output:
                                    stderr_output = stderr_output.strip()
                            except Exception:
                                pass

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
                            retry_handler.record_attempt()
                            output_parser.reset_milestones()
                            keep_awake_handler.reset()

            elapsed = self.profiler.subtask_times["run_isolve_execution"][-1]
            self._log(f"      - Subtask 'run_isolve_execution' done in {elapsed:.2f}s", log_type="verbose")
            self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

            # --- 4. Post-simulation steps ---
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
