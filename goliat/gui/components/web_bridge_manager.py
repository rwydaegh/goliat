"""Web bridge manager component for remote monitoring."""

import socket
from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from goliat.gui.progress_gui import ProgressGUI

try:
    from PySide6.QtCore import QTimer
except ImportError:
    QTimer = None  # type: ignore


class WebBridgeManager:
    """Manages web GUI bridge initialization and status updates.

    Handles connection to web dashboard, collects system info, and manages
    bridge lifecycle. Keeps web bridge code exactly as is per requirements.
    """

    def __init__(self, gui: "ProgressGUI", server_url: str, machine_id: Optional[str], use_web: bool = True) -> None:
        """Initializes web bridge manager.

        Args:
            gui: ProgressGUI instance.
            server_url: Web dashboard server URL.
            machine_id: Machine ID for identification.
            use_web: Whether to enable web bridge (default: True).
        """
        self.gui = gui
        self.server_url = server_url
        self.machine_id = machine_id
        self.use_web = use_web
        self.web_bridge: Optional[Any] = None
        self.screenshot_timer: Optional[Any] = None
        self.screenshot_capture: Optional[Any] = None

    def initialize(self) -> None:
        """Initializes web GUI bridge for remote monitoring.

        Sets up connection to web dashboard, collects system info, and starts
        the bridge. Handles errors gracefully to allow GUI to continue without web monitoring.
        """
        if not self.use_web:
            # Web bridge disabled via config
            if hasattr(self.gui, "error_counter_label") and hasattr(self.gui, "status_manager"):
                self.gui._update_web_status(False)
            return

        if self.machine_id:
            try:
                from goliat.utils.gui_bridge import WebGUIBridge
                from goliat.gui.components.system_monitor import SystemMonitor

                self.web_bridge = WebGUIBridge(self.server_url, self.machine_id)

                # Collect system info
                gpu_name = SystemMonitor.get_gpu_name()
                cpu_cores = SystemMonitor.get_cpu_cores()
                total_ram_gb = SystemMonitor.get_total_ram_gb()
                hostname = socket.gethostname()

                system_info = {"gpuName": gpu_name or "N/A", "cpuCores": cpu_cores, "totalRamGB": total_ram_gb, "hostname": hostname}
                self.web_bridge.set_system_info(system_info)

                # Set callback to update GUI indicator BEFORE starting
                self.web_bridge.set_connection_callback(self.gui._update_web_status)
                # start() already sends initial heartbeat, no need to send again
                self.web_bridge.start()

                # Initialize screenshot capture
                self._initialize_screenshot_capture()

                self.gui.verbose_logger.info(f"Web GUI bridge enabled: {self.server_url}, machine_id={self.machine_id}")
                self.gui.verbose_logger.info(
                    f"System info: GPU={gpu_name or 'N/A'}, CPU={cpu_cores} cores, RAM={total_ram_gb:.1f} GB, Hostname={hostname}"
                )
            except Exception as e:
                self.gui.verbose_logger.warning(f"Failed to initialize web GUI bridge: {e}. Continuing without web monitoring.")
                if hasattr(self.gui, "error_counter_label") and hasattr(self.gui, "status_manager"):
                    self.gui._update_web_status(False)
        else:
            if hasattr(self.gui, "error_counter_label") and hasattr(self.gui, "status_manager"):
                self.gui._update_web_status(False)

    def sync_progress(self) -> None:
        """Periodically sync actual GUI progress bar values to web dashboard.

        Sends the current progress bar values to the web bridge so the dashboard
        always shows the actual progress, even if progress messages aren't sent.
        """
        if self.web_bridge is None:
            return

        try:
            # Get actual progress bar values
            overall_value = self.gui.overall_progress_bar.value()
            overall_max = self.gui.overall_progress_bar.maximum()
            overall_progress = (overall_value / overall_max * 100) if overall_max > 0 else 0

            stage_value = self.gui.stage_progress_bar.value()
            stage_max = self.gui.stage_progress_bar.maximum()
            stage_progress = (stage_value / stage_max * 100) if stage_max > 0 else 0

            # Send overall progress
            if overall_progress > 0:
                self.web_bridge.enqueue({"type": "overall_progress", "current": overall_progress, "total": 100})

            # Send stage progress if we have a stage name
            if stage_progress > 0 and hasattr(self.gui, "stage_label"):
                stage_name = self.gui.stage_label.text().replace("Current Stage: ", "")
                if stage_name and stage_name != "Current Stage:":
                    self.web_bridge.enqueue({"type": "stage_progress", "name": stage_name, "current": stage_progress, "total": 100})
        except Exception as e:
            # Don't let progress sync errors break the GUI
            if hasattr(self.gui, "verbose_logger"):
                self.gui.verbose_logger.debug(f"Failed to sync progress to web: {e}")

    def _initialize_screenshot_capture(self) -> None:
        """Initialize screenshot capture timer.

        Sets up a timer to capture screenshots every 1 second (1 FPS)
        and send them via the web bridge.
        """
        if QTimer is None:
            return

        try:
            from goliat.gui.components.screenshot_capture import ScreenshotCapture

            self.screenshot_capture = ScreenshotCapture(self.gui)

            # Create timer for screenshot capture (0.2 FPS = every 5000ms)
            if QTimer is not None:
                timer = QTimer(self.gui)
                timer.timeout.connect(self._capture_and_send_screenshots)
                timer.start(5000)  # 5 seconds interval
                self.screenshot_timer = timer

            self.gui.verbose_logger.info("Screenshot capture initialized (0.2 FPS)")

        except Exception as e:
            self.gui.verbose_logger.warning(f"Failed to initialize screenshot capture: {e}. Continuing without screenshots.")

    def _capture_and_send_screenshots(self) -> None:
        """Capture screenshots and send via web bridge.

        Called by QTimer every second. Captures all tabs asynchronously
        and enqueues them for sending via the web bridge.
        """
        if self.web_bridge is None or self.screenshot_capture is None:
            return

        try:
            screenshots = self.screenshot_capture.capture_all_tabs()

            if screenshots:
                # Enqueue screenshots message for web bridge
                self.web_bridge.enqueue({"type": "gui_screenshots", "screenshots": screenshots})

        except Exception as e:
            # Don't let screenshot failures break the GUI
            if hasattr(self.gui, "verbose_logger"):
                self.gui.verbose_logger.debug(f"Failed to capture/send screenshots: {e}")

    def stop(self) -> None:
        """Stops the web bridge and screenshot capture."""
        # Stop screenshot timer
        if self.screenshot_timer is not None:
            try:
                self.screenshot_timer.stop()
            except Exception as e:
                if hasattr(self.gui, "verbose_logger"):
                    self.gui.verbose_logger.warning(f"Error stopping screenshot timer: {e}")

        # Stop web bridge
        if self.web_bridge is not None:
            try:
                self.web_bridge.stop()
            except Exception as e:
                if hasattr(self.gui, "verbose_logger"):
                    self.gui.verbose_logger.warning(f"Error stopping web bridge: {e}")

    def send_finished(self, error: bool = False) -> None:
        """Sends final status update to web before stopping bridge.

        Sends multiple 100% progress updates with delays to ensure the cloud
        receives them even if it's lagging behind. This prevents tasks from
        appearing stuck at 99% on the web interface.

        Args:
            error: Whether study finished with errors.
        """
        # Stop screenshot timer first to prevent new screenshots from being queued
        if self.screenshot_timer is not None:
            try:
                self.screenshot_timer.stop()
            except Exception as e:
                if hasattr(self.gui, "verbose_logger"):
                    self.gui.verbose_logger.warning(f"Error stopping screenshot timer: {e}")

        if self.web_bridge is not None:
            try:
                import time

                # Check if bridge is still running before sending messages
                if not self.web_bridge.running:
                    # Bridge already stopped, just ensure screenshot timer is stopped
                    return

                # Send multiple 100% progress updates with delays to ensure cloud receives them
                # Cloud is often lagging behind, so we send updates multiple times
                for i in range(5):  # Send 5 times to ensure at least one gets through
                    # Check if bridge is still running before each enqueue
                    if not self.web_bridge.running:
                        break
                    self.web_bridge.enqueue({"type": "overall_progress", "current": 100, "total": 100})
                    # Also send stage progress at 100% if we have a stage name
                    if hasattr(self.gui, "stage_label"):
                        stage_name = self.gui.stage_label.text().replace("Current Stage: ", "")
                        if stage_name and stage_name != "Current Stage:":
                            self.web_bridge.enqueue({"type": "stage_progress", "name": stage_name, "current": 100, "total": 100})
                    if i < 4:  # Don't sleep after the last iteration
                        time.sleep(0.5)  # 500ms delay between updates

                # Send finished message only if bridge is still running
                if self.web_bridge.running:
                    self.web_bridge.enqueue(
                        {"type": "finished", "message": "Study finished successfully" if not error else "Study finished with errors"}
                    )

                    # Wait longer for final messages to send (cloud might be processing previous updates)
                    time.sleep(3)  # Increased from 1s to 3s to give cloud more time

                # Stop the bridge (safe to call even if already stopped)
                self.web_bridge.stop()
            except Exception as e:
                if hasattr(self.gui, "verbose_logger"):
                    self.gui.verbose_logger.warning(f"Error stopping web bridge: {e}")
