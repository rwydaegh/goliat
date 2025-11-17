"""System utilization management component."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

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
        # Initialize last values to avoid issues before first update
        self._last_cpu_percent: float = 0.0
        self._last_ram_percent: float = 0.0  # With cache (most natural - memory.percent)
        self._last_ram_percent_no_cache: float = 0.0  # Without cache
        self._last_gpu_percent: Optional[float] = None
        self._last_gpu_vram_percent: Optional[float] = None

    def update(self) -> None:
        """Updates CPU, RAM, and GPU utilization displays.

        Called every second by Qt timer. Gets current utilization values
        from SystemMonitor and updates the progress bars and labels.
        """
        # Update CPU utilization
        cpu_percent = SystemMonitor.get_cpu_utilization()
        self.gui.cpu_bar.setValue(int(cpu_percent))
        self.gui.cpu_bar.setFormat(f"{cpu_percent:.0f}%")

        # Update RAM utilization - use "most natural" metric (with cache) for main tab
        # Get detailed RAM metrics (with and without cache)
        ram_with_cache, ram_without_cache, total_gb = SystemMonitor.get_ram_utilization_detailed()
        used_gb, _ = SystemMonitor.get_ram_utilization()
        
        if total_gb > 0:
            # Use RAM with cache (most natural - memory.percent) for main tab display
            ram_percent = ram_with_cache
            
            self.gui.ram_bar.setValue(int(ram_percent))
            self.gui.ram_bar.setFormat(f"{used_gb:.1f}/{total_gb:.1f} GB")
        else:
            ram_percent = 0.0
            ram_without_cache = 0.0
            self.gui.ram_bar.setValue(0)
            self.gui.ram_bar.setFormat("N/A")

        # Update GPU utilization
        gpu_percent: Optional[float] = None
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

        # Store current values for plot update (updated less frequently via graph_manager)
        self._last_cpu_percent = cpu_percent
        self._last_ram_percent = ram_percent  # With cache (most natural)
        self._last_ram_percent_no_cache = ram_without_cache if total_gb > 0 else 0.0
        self._last_gpu_percent = gpu_percent
        
        # Get GPU VRAM utilization for plot (not shown in main tab)
        if self.gui.gpu_available:
            vram_info = SystemMonitor.get_gpu_vram_utilization()
            if vram_info is not None:
                used_vram_gb, total_vram_gb = vram_info
                if total_vram_gb > 0:
                    self._last_gpu_vram_percent = (used_vram_gb / total_vram_gb) * 100
                else:
                    self._last_gpu_vram_percent = None
            else:
                self._last_gpu_vram_percent = None
        else:
            self._last_gpu_vram_percent = None

    def update_plot(self) -> None:
        """Updates the system utilization plot with current values.

        Called less frequently (every 2 seconds) to avoid excessive plot updates.
        Writes to CSV and adds data point to plot.
        """
        current_time = datetime.now()
        
        # Write to CSV (includes both RAM metrics and GPU VRAM)
        self.gui.data_manager.write_system_utilization(
            self._last_cpu_percent,
            self._last_ram_percent,
            self._last_ram_percent_no_cache,
            self._last_gpu_percent,
            self._last_gpu_vram_percent
        )
        
        # Add to plot (includes both RAM metrics and GPU VRAM)
        if hasattr(self.gui, "system_utilization_plot"):
            # Get system info for legend
            from goliat.gui.components.system_monitor import SystemMonitor
            cpu_cores = SystemMonitor.get_cpu_cores()
            total_ram_gb = SystemMonitor.get_total_ram_gb()
            gpu_name = SystemMonitor.get_gpu_name()
            
            # Get GPU VRAM total for legend
            total_gpu_vram_gb = 0.0
            if self.gui.gpu_available:
                vram_info = SystemMonitor.get_gpu_vram_utilization()
                if vram_info is not None:
                    _, total_gpu_vram_gb = vram_info
            
            self.gui.system_utilization_plot.add_data_point(
                current_time,
                self._last_cpu_percent,
                self._last_ram_percent,
                self._last_ram_percent_no_cache,
                self._last_gpu_percent,
                self._last_gpu_vram_percent,
                cpu_cores=cpu_cores,
                total_ram_gb=total_ram_gb,
                gpu_name=gpu_name,
                total_gpu_vram_gb=total_gpu_vram_gb
            )
