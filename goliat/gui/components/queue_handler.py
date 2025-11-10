"""Queue message handler for processing messages from worker process."""

import traceback
from queue import Empty
from typing import TYPE_CHECKING, Dict, Any, Optional

if TYPE_CHECKING:
    from goliat.gui.progress_gui import ProgressGUI


class QueueHandler:
    """Handles processing of messages from the worker process queue.

    Polls the multiprocessing queue and dispatches messages to appropriate
    GUI update methods. This decouples message handling from queue polling,
    making the code cleaner and easier to test.

    Message types:
    - 'status': Log message with color coding
    - 'overall_progress': Update overall progress bar
    - 'stage_progress': Update stage progress bar
    - 'start_animation': Start animated progress bar
    - 'end_animation': Stop animation
    - 'profiler_update': Update profiler state and refresh timing displays
    - 'sim_details': Update simulation counter and details
    - 'finished': Study completed successfully
    - 'fatal_error': Study failed with fatal error
    """

    def __init__(self, gui_instance: "ProgressGUI") -> None:
        """Sets up the queue handler.

        Args:
            gui_instance: ProgressGUI instance to update with messages.
        """
        self.gui: "ProgressGUI" = gui_instance
        self._MESSAGE_HANDLERS = {
            "status": self._handle_status,
            "overall_progress": self._handle_overall_progress,
            "stage_progress": self._handle_stage_progress,
            "start_animation": self._handle_start_animation,
            "end_animation": self._handle_end_animation,
            "profiler_update": self._handle_profiler_update,
            "sim_details": self._handle_sim_details,
            "finished": self._handle_finished,
            "fatal_error": self._handle_fatal_error,
        }

    def _handle_status(self, msg: Dict[str, Any]) -> None:
        """Handles status message type."""
        self.gui.update_status(msg["message"], msg.get("log_type", "default"))

    def _handle_overall_progress(self, msg: Dict[str, Any]) -> None:
        """Handles overall progress message type."""
        self.gui.update_overall_progress(msg["current"], msg["total"])

    def _handle_stage_progress(self, msg: Dict[str, Any]) -> None:
        """Handles stage progress message type."""
        self.gui.update_stage_progress(msg["name"], msg["current"], msg["total"], msg.get("sub_stage", ""))

    def _handle_start_animation(self, msg: Dict[str, Any]) -> None:
        """Handles start animation message type."""
        self.gui.start_stage_animation(msg["estimate"], msg["end_value"])

    def _handle_end_animation(self, msg: Dict[str, Any]) -> None:
        """Handles end animation message type."""
        self.gui.end_stage_animation()

    def _handle_profiler_update(self, msg: Dict[str, Any]) -> None:
        """Handles profiler update message type."""
        self.gui.profiler = msg.get("profiler")
        if self.gui.profiler:
            self.gui.profiler_phase = self.gui.profiler.current_phase
            self.gui.timings_table.update(self.gui.profiler)
            self.gui.piecharts_manager.update(self.gui.profiler)

    def _handle_sim_details(self, msg: Dict[str, Any]) -> None:
        """Handles simulation details message type."""
        self.gui.update_simulation_details(msg["count"], msg["total"], msg["details"])

    def _handle_finished(self, msg: Dict[str, Any]) -> None:
        """Handles finished message type."""
        self.gui.study_finished()

    def _handle_fatal_error(self, msg: Dict[str, Any]) -> None:
        """Handles fatal error message type."""
        self.gui.update_status(f"FATAL ERROR: {msg['message']}", log_type="fatal")
        self.gui.study_finished(error=True)

    def process_queue(self) -> None:
        """Processes messages from worker process queue and updates UI accordingly.

        Polls queue non-blockingly and processes all available messages in one
        call. Handles different message types by calling appropriate GUI methods.
        Catches and logs exceptions to prevent one bad message from crashing GUI.

        This method is called every 100ms by Qt timer to keep UI responsive.

        After processing each message for the GUI, forwards a copy to WebGUIBridge
        if it exists (for web dashboard monitoring).
        """
        while not self.gui.queue.empty():
            try:
                msg: Dict[str, Any] = self.gui.queue.get_nowait()
                msg_type: Optional[str] = msg.get("type")

                # Dispatch message to appropriate handler
                if msg_type:
                    handler = self._MESSAGE_HANDLERS.get(msg_type)
                    if handler:
                        handler(msg)

                # Forward message to web bridge if enabled
                if hasattr(self.gui, "web_bridge_manager") and self.gui.web_bridge_manager.web_bridge is not None:
                    try:
                        # Sanitize profiler_update messages before forwarding
                        if msg_type == "profiler_update" and "profiler" in msg:
                            profiler = msg.get("profiler")
                            # Extract only serializable data from profiler
                            sanitized_msg = {
                                "type": "profiler_update",
                                "eta_seconds": getattr(profiler, "eta_seconds", None) if profiler else None,
                            }
                            self.gui.web_bridge_manager.web_bridge.enqueue(sanitized_msg)
                        else:
                            self.gui.web_bridge_manager.web_bridge.enqueue(msg)
                    except Exception as e:
                        # Don't let web bridge errors crash the GUI
                        self.gui.verbose_logger.warning(f"Failed to forward message to web bridge: {e}")

            except Empty:
                break
            except Exception as e:
                self.gui.verbose_logger.error(f"Error processing GUI queue: {e}\n{traceback.format_exc()}")
