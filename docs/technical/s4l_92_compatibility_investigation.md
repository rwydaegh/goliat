# Sim4Life 9.2 Compatibility Investigation - Brain Dump

*Date: 2026-01-13*
*Context: Debugging GOLIAT compatibility issues with Sim4Life 9.2*

## The Problem

GOLIAT worked perfectly on Sim4Life 8.2 but exhibited these issues on Sim4Life 9.2:
- **`use_gui=false`**: Segmentation fault
- **`use_gui=true`**: Hangs forever, then later worked but no terminal logging

Initial hypothesis was that `multiprocessing.Queue` was incompatible with S4L 9.2, but this turned out to be wrong.

---

## The Diagnostic Process

### Test 1: Basic Multiprocessing Test (`test_s4l_multiprocessing.py`)
- Created a simple test: start S4L, send "hello world" through a Queue
- **Result**: PASSED on both 8.2 and 9.2
- **Conclusion**: `multiprocessing.Queue` itself is NOT the issue

### Test 2: Extended Component Tests (`test_s4l_multiprocessing_extended.py`)
Progressive tests adding GOLIAT components:
1. Basic S4L startup - PASSED
2. S4L + GOLIAT logging - PASSED
3. S4L + Config loading - PASSED
4. S4L + Document operations - PASSED
5. S4L + PySide6 - PASSED
6. Multiprocess with logging + document - PASSED
7. Full workflow with QueueGUI + Profiler - PASSED
8. NearFieldStudy import (headless) - PASSED
9. NearFieldStudy import (multiprocess) - PASSED

**Key insight**: All individual tests passed! So why does `goliat study` fail?

### Test 3: Import Order Tests (`test_s4l_import_order.py`)
Mimicked the exact import order from `run_study.py`:
- Full import order (like run_study.py) → **SEGFAULT**

This narrowed it down to something about the import order.

### Test 4: Import Bisect (`test_s4l_import_bisect.py`)
Binary search through imports to find the culprit:
- PySide6 + S4L → PASSED
- PySide6 + Config + S4L → SEGFAULT

Wait, but PySide6 alone didn't cause it?

### Test 5: Final Diagnostic (`test_s4l_final_diagnostic.py`)
Tested specific orderings:

| Test | Description | Result |
|------|-------------|--------|
| 1 | Just PySide6 import | SEGFAULT |
| 2 | PySide6 + matplotlib | SEGFAULT |
| 3 | PySide6 + matplotlib.use('Qt5Agg') | SEGFAULT |
| 4 | PySide6 + matplotlib.use('Agg') | SEGFAULT |
| **5** | **matplotlib.use() FIRST, then PySide6** | **PASSED** |
| **6** | **S4L FIRST, then PySide6** | **PASSED** |

### Test 6: Full Study Flow (`test_full_study_flow.py`)
This test mimics the exact `goliat study` flow:
- Main process imports run_study.py (triggers S4L + PySide6 at module level)
- Main process spawns child process
- Child process should print to terminal

**Result on 8.2**: Child output appears in terminal ✓
**Result on 9.2**: Child output MISSING from terminal ✗

This isolated the second issue: when main process has S4L running before spawn, child stdout is broken.

---

## Root Cause Analysis

### Issue 1: Segfault on S4L 9.2
**Cause**: Sim4Life 9.2 crashes if PySide6 is imported BEFORE Sim4Life starts.
This is a breaking change from 8.2 where the order didn't matter.

### Issue 2: Child process stdout broken
**Cause**: When the main process starts S4L and then spawns a child process using `multiprocessing.spawn`, the child inherits broken stdout/stderr file descriptors from the parent. This appears to be something S4L 9.2 does to stdout/stderr that wasn't an issue in 8.2.

The child process still writes to log files correctly, and QueueGUI messages still reach the main process's GUI. Only the direct console output from the child is lost.

---

## The Final Solution

The fix required changes to three files:

### 1. `cli/run_study.py` - Module-level initialization

```python
# --- Pre-check and Setup ---
# Only run initial_setup in main process (not in spawned children)
_is_main_process = multiprocessing.current_process().name == "MainProcess"
if _is_main_process and not os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("CI"):
    initial_setup()

# --- S4L 9.2 Compatibility Fix ---
# Sim4Life 9.2 crashes (segfault) if PySide6 is imported BEFORE S4L starts.
# IMPORTANT: We only do early S4L init in the MAIN process.
# Child processes skip this because when the main process has S4L running,
# spawning a child inherits broken stdout/stderr file descriptors.
# Child processes will init S4L later via ensure_s4l_running() in study_process_wrapper.
if _is_main_process and not os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("CI"):
    try:
        from s4l_v1._api import application as _s4l_app
        if _s4l_app.get_app_safe() is None:
            _s4l_app.run_application(disable_ui_plugins=True)
    except ImportError:
        pass

# --- PySide6 and GUI imports (main process only) ---
# Child processes don't need PySide6 or ProgressGUI. Importing ProgressGUI triggers
# matplotlib.use("Qt5Agg") which conflicts with S4L 9.2 if S4L hasn't started yet.
if _is_main_process:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        # ... error handling ...
    
    from goliat.gui_manager import ProgressGUI, QueueGUI
    # ... rest of imports ...
else:
    # Child process - set these to None
    QApplication = None
    ProgressGUI = None
    QueueGUI = None  # Will be imported directly in study_process_wrapper
```

### 2. `cli/run_study.py` - study_process_wrapper function

```python
def study_process_wrapper(queue, stop_event, config_filename, process_id, no_cache=False, session_timestamp=None):
    # ... setup loggers ...
    
    try:
        # Import QueueGUI directly here (not at module level) because child processes
        # skip the gui_manager import to avoid PySide6/matplotlib conflicts on S4L 9.2.
        from goliat.gui.queue_gui import QueueGUI as _QueueGUI

        gui_proxy = _QueueGUI(queue, stop_event, profiler, progress_logger, verbose_logger)
        # ... rest of study setup ...
```

### 3. `goliat/gui/components/queue_handler.py` - Terminal output

```python
from colorama import Style
from goliat.colors import get_color

class QueueHandler:
    def _handle_status(self, msg: Dict[str, Any]) -> None:
        """Handles status message type."""
        message = msg["message"]
        log_type = msg.get("log_type", "default")
        # Update GUI
        self.gui.update_status(message, log_type)
        # Also print to terminal with colors (child process stdout may be broken on S4L 9.2)
        color = get_color(log_type)
        print(f"{color}{message}{Style.RESET_ALL}")
```

---

## Why This Solution Works

### Main Process Flow:
1. `_is_main_process` check → True
2. `initial_setup()` runs (version warnings, etc.)
3. S4L starts early (before PySide6) → **Avoids segfault**
4. PySide6 imported → Safe now that S4L is running
5. `gui_manager` imported → ProgressGUI and matplotlib configured
6. Child process spawned
7. QApplication.exec() runs (GUI event loop)
8. QueueHandler receives messages from queue and **prints to terminal**

### Child Process Flow:
1. Re-imports run_study.py at module level
2. `_is_main_process` check → False
3. Skips `initial_setup()` → No duplicate warnings
4. Skips S4L early init → **Avoids inheriting broken stdout**
5. Skips PySide6 imports → Doesn't need them
6. `study_process_wrapper()` starts
7. Imports `QueueGUI` directly from `queue_gui.py` (not `gui_manager`)
8. S4L starts via `ensure_s4l_running()` inside the study
9. All log messages sent through queue → **Main process prints them**

---

## Key Technical Insights

### Why child stdout is broken on 9.2

When S4L 9.2 starts, it appears to do something to the underlying file descriptors for stdout/stderr. On Windows with `multiprocessing.spawn`, the child process may inherit these modified descriptors. Even though we restore `sys.stdout` and `sys.stderr` in Python, the underlying C-level file descriptors remain affected.

### Why importing QueueGUI directly works

The import chain matters:
- `from goliat.gui_manager import QueueGUI` → imports `progress_gui.py` → calls `matplotlib.use("Qt5Agg")` → imports PySide6 internals
- `from goliat.gui.queue_gui import QueueGUI` → only imports what QueueGUI needs (no matplotlib, no PySide6)

### Why printing in main process works

The main process's stdout is fine - it's the parent, not affected by spawn inheritance. Since QueueGUI already sends all log messages through the multiprocessing queue, we just add a `print()` call in `QueueHandler._handle_status()` to echo them to terminal.

---

## Files Changed

| File | Change |
|------|--------|
| `cli/run_study.py` | Conditional S4L/PySide6 init based on main/child process |
| `goliat/gui/components/queue_handler.py` | Print status messages to terminal with colors |
| `goliat/runners/keep_awake_handler.py` | Guard `sys.stdout.flush()` with None check |

---

## Test Files Created

All in `tests/`:
- `test_s4l_multiprocessing.py` - Basic Queue test
- `test_s4l_multiprocessing_extended.py` - Progressive component tests
- `test_s4l_import_order.py` - Import order tests
- `test_s4l_import_bisect.py` - Binary search for problematic imports
- `test_s4l_final_diagnostic.py` - Final isolation tests
- `test_child_console.py` - Basic child process stdout test
- `test_child_console_s4l.py` - Child stdout with S4L in child
- `test_child_mimics_study.py` - Child imports run_study.py
- `test_full_study_flow.py` - Full main+child flow test

---

## Lessons Learned

1. **Import order matters** - Module-level import order can cause segfaults in external C libraries
2. **File descriptors vs Python objects** - Restoring `sys.stdout` doesn't fix underlying fd issues
3. **Spawn context inheritance** - Child processes may inherit unexpected state from parent
4. **Test incrementally** - Binary search approach was essential for diagnosis
5. **Route around the problem** - When child stdout is broken, print in the main process instead
6. **Main vs child context** - Use `multiprocessing.current_process().name == "MainProcess"` to differentiate

---

## Verification

To verify the fix works:
1. On S4L 8.2: `goliat study far_field_FR3_barebones` → Works with terminal output ✓
2. On S4L 9.2: `goliat study far_field_FR3_barebones` → Works with terminal output ✓
3. Both versions: GUI shows progress, logs written to files, no segfault, no hang
