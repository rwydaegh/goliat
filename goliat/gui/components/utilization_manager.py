"""System utilization management component."""

from typing import TYPE_CHECKING

from goliat.gui.components.system_monitor import SystemMonitor

if TYPE_CHECKING:
    from goliat.gui.progress_gui import ProgressGUI


class UtilizationManager:
    """Manages CPU, RAM, and GPU utilization displays."""

    def __init__(self, gui: "ProgressGUI") -> None:
        """Initializes utilization manager.

        Args:
            gui: ProgressGUI instance.
        """
        self.gui = gui

    def update(self) -> None:
        """Updates CPU, RAM, and GPU utilization displays.

        Called every second by Qt timer. Gets current utilization values
        from SystemMonitor and updates the progress bars and labels.
        """
        # Update CPU utilization
        cpu_percent = SystemMonitor.get_cpu_utilization()
        self.gui.cpu_bar.setValue(int(cpu_percent))
        self.gui.cpu_bar.setFormat(f"{cpu_percent:.0f}%")

        # Update RAM utilization
        used_gb, total_gb = SystemMonitor.get_ram_utilization()
        if total_gb > 0:
            ram_percent = (used_gb / total_gb) * 100
            self.gui.ram_bar.setValue(int(ram_percent))
            self.gui.ram_bar.setFormat(f"{used_gb:.1f}/{total_gb:.1f} GB")
        else:
            self.gui.ram_bar.setValue(0)
            self.gui.ram_bar.setFormat("N/A")

        # Update GPU utilization
        if self.gui.gpu_available:
            gpu_percent = SystemMonitor.get_gpu_utilization()
            if gpu_percent is not None:
                self.gui.gpu_bar.setValue(int(gpu_percent))
                self.gui.gpu_bar.setFormat(f"{gpu_percent:.0f}%")
            else:
                self.gui.gpu_bar.setValue(0)
                self.gui.gpu_bar.setFormat("N/A")
                self.gui.gpu_available = False  # GPU became unavailable
        else:
            self.gui.gpu_bar.setValue(0)
            self.gui.gpu_bar.setFormat("N/A")
