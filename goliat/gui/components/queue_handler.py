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

                if msg_type == "status":
                    self.gui.update_status(msg["message"], msg.get("log_type", "default"))
                elif msg_type == "overall_progress":
                    self.gui.update_overall_progress(msg["current"], msg["total"])
                elif msg_type == "stage_progress":
                    self.gui.update_stage_progress(msg["name"], msg["current"], msg["total"], msg.get("sub_stage", ""))
                elif msg_type == "start_animation":
                    self.gui.start_stage_animation(msg["estimate"], msg["end_value"])
                elif msg_type == "end_animation":
                    self.gui.end_stage_animation()
                elif msg_type == "profiler_update":
                    self.gui.profiler = msg.get("profiler")
                    if self.gui.profiler:
                        self.gui.profiler_phase = self.gui.profiler.current_phase
                        self.gui.timings_table.update(self.gui.profiler)
                        self.gui.piecharts_manager.update(self.gui.profiler)
                elif msg_type == "sim_details":
                    self.gui.update_simulation_details(msg["count"], msg["total"], msg["details"])
                elif msg_type == "finished":
                    self.gui.study_finished()
                elif msg_type == "fatal_error":
                    self.gui.update_status(f"FATAL ERROR: {msg['message']}", log_type="fatal")
                    self.gui.study_finished(error=True)

                # Forward message to web bridge if enabled
                if hasattr(self.gui, "web_bridge") and self.gui.web_bridge is not None:
                    try:
                        # Sanitize profiler_update messages before forwarding
                        if msg_type == "profiler_update" and "profiler" in msg:
                            profiler = msg.get("profiler")
                            # Extract only serializable data from profiler
                            sanitized_msg = {
                                "type": "profiler_update",
                                "eta_seconds": getattr(profiler, "eta_seconds", None) if profiler else None,
                            }
                            self.gui.web_bridge.enqueue(sanitized_msg)
                        else:
                            self.gui.web_bridge.enqueue(msg)
                    except Exception as e:
                        # Don't let web bridge errors crash the GUI
                        self.gui.verbose_logger.warning(f"Failed to forward message to web bridge: {e}")

            except Empty:
                break
            except Exception as e:
                self.gui.verbose_logger.error(f"Error processing GUI queue: {e}\n{traceback.format_exc()}")
