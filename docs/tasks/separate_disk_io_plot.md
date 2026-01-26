# Task: Move Disk I/O to Separate Tab

## Goal
Move the SSD Read/Write plotting from the "System Utilization" tab to a new dedicated "Disk I/O" tab. This frees up the right Y-axis on the main utilization plot for future metrics (e.g., page faults, available memory).

## Current State

### System Utilization Plot
- **Location**: `goliat/gui/components/plots/system_utilization_plot.py`
- **Left Y-axis (0-100%)**: CPU, RAM, GPU, GPU VRAM
- **Right Y-axis (MB/s)**: Disk Read, Disk Write (using `ax.twinx()`)

The right axis is currently used for disk I/O, which has different units (MB/s) than the percentage-based metrics.

### Data Flow
1. `SystemMonitor` (in `system_monitor.py`) collects all metrics including `get_disk_io_throughput()`
2. `UtilizationManager` (in `utilization_manager.py`) stores values and calls `update_plot()` every 2 seconds
3. `SystemUtilizationPlot.add_data_point()` receives all data including `disk_read_mbps` and `disk_write_mbps`
4. Data is also written to CSV via `DataManager.write_system_utilization()`

## Files to Modify

### 1. Create: `goliat/gui/components/plots/disk_io_plot.py`
Create a new plot class similar to `TimeRemainingPlot` or `SystemUtilizationPlot`:
- Single Y-axis in MB/s
- Two lines: Disk Read (green `#00ff88`) and Disk Write (orange `#ff8800`)
- Same dark theme styling as other plots
- Same `add_data_point(timestamp, disk_read_mbps, disk_write_mbps)` pattern

### 2. Modify: `goliat/gui/components/plots/__init__.py`
Add export for `DiskIOPlot`:
```python
from .disk_io_plot import DiskIOPlot
__all__ = [..., "DiskIOPlot"]
```

### 3. Modify: `goliat/gui/components/plots/system_utilization_plot.py`
Remove all disk I/O related code:
- Remove `self.disk_read_data` and `self.disk_write_data` lists
- Remove `self.disk_available` flag
- Remove `self.ax2` secondary axis
- Remove `disk_read_mbps` and `disk_write_mbps` from `add_data_point()` signature
- Remove disk plotting logic from `_refresh()`

### 4. Modify: `goliat/gui/components/ui_builder.py`
Add new tab builder method (pattern from line 412-418):
```python
@staticmethod
def _build_disk_io_tab(gui_instance: "ProgressGUI") -> None:
    """Builds the Disk I/O tab."""
    disk_io_widget = QWidget()
    disk_io_layout = QVBoxLayout(disk_io_widget)
    gui_instance.tabs.addTab(disk_io_widget, "Disk I/O")
    gui_instance.disk_io_plot = DiskIOPlot()
    disk_io_layout.addWidget(gui_instance.disk_io_plot.canvas)
```
Call this from `build()` method (around line 210).

Update import to include `DiskIOPlot`.

### 5. Modify: `goliat/gui/components/utilization_manager.py`
In `update_plot()` method (line 95-149):
- Keep collecting disk I/O data (already done at lines 88-93)
- Remove disk params from `system_utilization_plot.add_data_point()` call
- Add new call to `disk_io_plot.add_data_point()`:
```python
if hasattr(self.gui, "disk_io_plot"):
    self.gui.disk_io_plot.add_data_point(
        timestamp=current_time,
        disk_read_mbps=self._last_disk_read_mbps,
        disk_write_mbps=self._last_disk_write_mbps,
    )
```

### 6. No changes needed: `goliat/gui/components/data_manager.py`
CSV format stays the same - disk I/O data continues to be logged.

## Reference: Existing Plot Patterns

### Plot class structure (see `time_remaining_plot.py`):
```python
class SomePlot:
    def __init__(self):
        self.figure = Figure(figsize=(10, 6), facecolor="#2b2b2b")
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.data = []
        self._setup()
    
    def _setup(self):
        # Dark theme styling
        self.ax.set_facecolor("#2b2b2b")
        # ... axis labels, grid, etc.
    
    def add_data_point(self, timestamp, ...):
        # Validate timestamp, append to data, call _refresh()
    
    def _refresh(self):
        # Clear, re-plot, canvas.draw()
```

### Colors used in codebase:
- Background: `#2b2b2b`
- Text/grid: `#f0f0f0`
- Legend bg: `#3c3c3c`
- Disk Read: `#00ff88` (green, dashed)
- Disk Write: `#ff8800` (orange, dashed)

### Imports needed:
```python
from ._matplotlib_imports import Figure, FigureCanvas, mdates
from .utils import convert_to_utc_plus_one, validate_timestamp, clean_plot_data
```

## Testing
1. Run a study with GUI enabled
2. Verify "System Utilization" tab shows only CPU/RAM/GPU/VRAM (no right axis)
3. Verify new "Disk I/O" tab shows read/write throughput
4. Verify CSV still contains all columns including disk data
