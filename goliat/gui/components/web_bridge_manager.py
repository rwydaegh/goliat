"""Web bridge manager component for remote monitoring."""

import socket
from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from goliat.gui.progress_gui import ProgressGUI


class WebBridgeManager:
    """Manages web GUI bridge initialization and status updates.

    Handles connection to web dashboard, collects system info, and manages
    bridge lifecycle. Keeps web bridge code exactly as is per requirements.
    """

    def __init__(self, gui: "ProgressGUI", server_url: str, machine_id: Optional[str]) -> None:
        """Initializes web bridge manager.

        Args:
            gui: ProgressGUI instance.
            server_url: Web dashboard server URL.
            machine_id: Machine ID for identification.
        """
        self.gui = gui
        self.server_url = server_url
        self.machine_id = machine_id
        self.web_bridge: Optional[Any] = None

    def initialize(self) -> None:
        """Initializes web GUI bridge for remote monitoring.

        Sets up connection to web dashboard, collects system info, and starts
        the bridge. Handles errors gracefully to allow GUI to continue without web monitoring.
        """
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
                self.web_bridge.start()

                # Send initial heartbeat with system info
                self.web_bridge.send_heartbeat_with_system_info(system_info)

                self.gui.verbose_logger.info(f"Web GUI bridge enabled: {self.server_url}, machine_id={self.machine_id}")
                self.gui.verbose_logger.info(
                    f"System info: GPU={gpu_name or 'N/A'}, CPU={cpu_cores} cores, RAM={total_ram_gb:.1f} GB, Hostname={hostname}"
                )
            except ImportError:
                self.gui.verbose_logger.warning(
                    "Web GUI bridge requested but 'requests' library not available. Install with: pip install requests"
                )
                if hasattr(self.gui, "error_counter_label") and hasattr(self.gui, "status_manager"):
                    self.gui._update_web_status(False)
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

    def stop(self) -> None:
        """Stops the web bridge."""
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
        if self.web_bridge is not None:
            try:
                import time

                # Send multiple 100% progress updates with delays to ensure cloud receives them
                # Cloud is often lagging behind, so we send updates multiple times
                for i in range(5):  # Send 5 times to ensure at least one gets through
                    self.web_bridge.enqueue({"type": "overall_progress", "current": 100, "total": 100})
                    # Also send stage progress at 100% if we have a stage name
                    if hasattr(self.gui, "stage_label"):
                        stage_name = self.gui.stage_label.text().replace("Current Stage: ", "")
                        if stage_name and stage_name != "Current Stage:":
                            self.web_bridge.enqueue({"type": "stage_progress", "name": stage_name, "current": 100, "total": 100})
                    if i < 4:  # Don't sleep after the last iteration
                        time.sleep(0.5)  # 500ms delay between updates

                # Send finished message
                self.web_bridge.enqueue(
                    {"type": "finished", "message": "Study finished successfully" if not error else "Study finished with errors"}
                )

                # Wait longer for final messages to send (cloud might be processing previous updates)
                time.sleep(3)  # Increased from 1s to 3s to give cloud more time
                self.web_bridge.stop()
            except Exception as e:
                if hasattr(self.gui, "verbose_logger"):
                    self.gui.verbose_logger.warning(f"Error stopping web bridge: {e}")
