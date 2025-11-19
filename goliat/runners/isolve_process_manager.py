"""Process manager for iSolve subprocess execution with non-blocking I/O."""

import gc
import subprocess
import threading
import time
from queue import Empty, Queue
from typing import TYPE_CHECKING, List, Optional

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

from ..logging_manager import LoggingMixin
from ..utils import StudyCancelledError

if TYPE_CHECKING:
    from logging import Logger

    from ..gui_manager import QueueGUI


def _reader_thread(pipe, queue: Queue) -> None:
    """Reads lines from a subprocess pipe and puts them onto a queue.

    This function runs in a separate thread to prevent blocking the main thread.
    It continuously reads lines from the pipe (which is connected to the
    subprocess stdout) and puts them into a queue. The main thread can then
    poll the queue non-blockingly.

    The thread is daemonized so it won't prevent program exit if the main
    thread terminates unexpectedly.

    Args:
        pipe: The pipe to read from (process.stdout).
        queue: The queue to put read lines onto for main thread consumption.
    """
    try:
        for line in iter(pipe.readline, ""):
            queue.put(line)
    finally:
        pipe.close()


class ISolveProcessManager(LoggingMixin):
    """Manages iSolve subprocess lifecycle and non-blocking I/O."""

    def __init__(
        self,
        command: List[str],
        gui: Optional["QueueGUI"],
        verbose_logger: "Logger",
        progress_logger: "Logger",
    ):
        """Initialize process manager.

        Args:
            command: Command to execute (e.g., [isolve_path, "-i", input_file]).
            gui: GUI proxy for stop signal checks.
            verbose_logger: Logger for verbose output.
            progress_logger: Logger for progress output.
        """
        self.command = command
        self.gui = gui
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        self.process: Optional[subprocess.Popen] = None
        self.output_queue: Optional[Queue] = None
        self.reader_thread: Optional[threading.Thread] = None
        self._is_running = False

    def start(self) -> None:
        """Start the subprocess and begin reading output."""
        self.process = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.output_queue = Queue()
        self.reader_thread = threading.Thread(target=_reader_thread, args=(self.process.stdout, self.output_queue))
        self.reader_thread.daemon = True
        self.reader_thread.start()
        self._is_running = True

    def is_running(self) -> bool:
        """Check if process is still running."""
        return self._is_running and self.process is not None and self.process.poll() is None

    def read_available_lines(self) -> List[str]:
        """Read all available lines from output queue (non-blocking).

        Returns:
            List of lines read (may be empty if no output available).
        """
        if self.output_queue is None:
            return []

        lines = []
        try:
            while True:
                lines.append(self.output_queue.get_nowait())
        except Empty:
            pass
        return lines

    def read_all_remaining_lines(self) -> List[str]:
        """Read all remaining lines after process completes.

        Should be called after is_running() returns False.
        Ensures reader thread has finished and queue is drained.

        Returns:
            List of all remaining lines.
        """
        if self.reader_thread is not None and self.reader_thread.is_alive():
            self.reader_thread.join()

        lines = []
        if self.output_queue is not None:
            while not self.output_queue.empty():
                try:
                    lines.append(self.output_queue.get_nowait())
                except Empty:
                    break
        return lines

    def get_return_code(self) -> Optional[int]:
        """Get process return code (None if still running)."""
        return self.process.returncode if self.process else None

    def read_stderr(self) -> str:
        """Read stderr output (fallback - most errors are in stdout).

        Returns:
            Stripped stderr string or empty string.
        """
        if self.process is None or self.process.stderr is None:
            return ""

        try:
            stderr_output = self.process.stderr.read()
            if stderr_output:
                return stderr_output.strip()
        except Exception:
            pass
        return ""

    def terminate(self, timeout: float = 2.0) -> None:
        """Terminate process gracefully, force kill if needed.

        Args:
            timeout: Seconds to wait for graceful termination.
        """
        if self.process is None:
            return

        if self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            except Exception:
                pass

    def cleanup(self) -> None:
        """Clean up process and threads."""
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
                except Exception:
                    pass
            self.process = None

        if self.reader_thread is not None and self.reader_thread.is_alive():
            self.reader_thread.join()

        self._is_running = False

        # Adaptive delay based on memory usage (more memory = longer wait)
        if psutil is not None:
            try:
                memory = psutil.virtual_memory()
                used_gb = memory.used / (1024**3)
                # Scale delay: 0.5s base + 0.1s per 10GB used (max 3s)
                delay = min(0.5 + (used_gb / 10.0) * 0.1, 3.0)
                time.sleep(delay)
            except Exception:
                time.sleep(0.5)  # Fallback to default
        else:
            time.sleep(0.5)

        # Force garbage collection to free Python-side memory
        gc.collect()

    def check_stop_signal(self) -> None:
        """Check for stop signal and terminate if requested.

        Raises:
            StudyCancelledError: If stop signal detected.
        """
        if self.gui and self.gui.is_stopped():
            self._log("Stop signal detected, terminating iSolve subprocess...", log_type="warning")
            self.terminate(timeout=2)
            raise StudyCancelledError("Study cancelled by user.")
