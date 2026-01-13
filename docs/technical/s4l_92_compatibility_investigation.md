# Sim4Life 9.2 Compatibility Investigation - Brain Dump

*Date: 2026-01-13*
*Context: Debugging GOLIAT compatibility issues with Sim4Life 9.2*

## The Problem

GOLIAT worked perfectly on Sim4Life 8.2 but exhibited these issues on Sim4Life 9.2:
- **`use_gui=false`**: Segmentation fault
- **`use_gui=true`**: Hangs forever

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

---

## The Root Cause

**Sim4Life 9.2 crashes if PySide6 is imported BEFORE Sim4Life starts.**

This is a breaking change from 8.2 where the order didn't matter.

The issue is NOT:
- ❌ `multiprocessing.Queue`
- ❌ `matplotlib.use("Qt5Agg")`
- ❌ Any specific GOLIAT component

The issue IS:
- ✅ **Import order**: PySide6 must be imported AFTER S4L starts

---

## The Fix

Modified `cli/run_study.py` to start S4L at module level, BEFORE any PySide6 imports:

```python
# --- S4L 9.2 Compatibility Fix ---
# Sim4Life 9.2 crashes (segfault) if PySide6 is imported BEFORE S4L starts.
# This affects BOTH the main process AND spawned child processes, since both
# re-import this module and thus import PySide6 at module level.
# Solution: Start S4L early in ALL processes, before any PySide6 imports.
if not os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("CI"):
    try:
        from s4l_v1._api import application as _s4l_app
        if _s4l_app.get_app_safe() is None:
            _s4l_app.run_application(disable_ui_plugins=True)
    except ImportError:
        pass  # Not running in S4L environment, skip
# --- End S4L 9.2 Fix ---

# NOW it's safe to import PySide6
from PySide6.QtWidgets import QApplication
```

### Critical Learning: Must Run in ALL Processes

Initially I tried to only run this in the main process:
```python
if multiprocessing.current_process().name == "MainProcess":
```

This caused the child process to hang because:
1. Child process re-imports `run_study.py`
2. Child process imports PySide6 at module level
3. Child process hasn't started S4L yet
4. → Hang/segfault

**Both main AND child processes need S4L started before PySide6 import.**

---

## GOLIAT Startup Flow

### When `goliat study config.json` is run:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CLI Entry Point (cli/run_study.py)                           │
│    - Module-level imports happen                                │
│    - S4L 9.2 fix: Start S4L early (before PySide6)              │
│    - initial_setup() runs                                       │
│    - PySide6 is imported (now safe)                             │
│    - Config, LoggingMixin, etc. imported                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. main() function                                              │
│    - Parse arguments                                            │
│    - Load Config                                                │
│    - Setup loggers                                              │
│    - Check use_gui setting                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
         ┌────────────────────┴────────────────────┐
         ↓                                         ↓
┌─────────────────────┐                 ┌─────────────────────────┐
│ use_gui=false       │                 │ use_gui=true            │
│ (Headless Mode)     │                 │ (GUI Mode)              │
│                     │                 │                         │
│ - ConsoleLogger     │                 │ - Spawn child process   │
│ - Run study in      │                 │ - Main: run GUI         │
│   main process      │                 │ - Child: run study      │
└─────────────────────┘                 └─────────────────────────┘
```

### GUI Mode Multi-Process Architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAIN PROCESS                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ QApplication (PySide6 event loop)                       │    │
│  │                                                         │    │
│  │  ┌─────────────────────────────────────────────────┐   │    │
│  │  │ ProgressGUI                                      │   │    │
│  │  │  - Shows progress bars                          │   │    │
│  │  │  - Status text log                              │   │    │
│  │  │  - Pie charts, graphs                           │   │    │
│  │  │                                                 │   │    │
│  │  │  QueueHandler polls queue every 100ms           │   │    │
│  │  │  ↑                                              │   │    │
│  │  └──│──────────────────────────────────────────────┘   │    │
│  │     │                                                   │    │
│  └─────│───────────────────────────────────────────────────┘    │
│        │                                                         │
│        │ multiprocessing.Queue                                   │
│        │ (messages flow from child → main)                       │
│        │                                                         │
└────────│─────────────────────────────────────────────────────────┘
         │
         │
┌────────│─────────────────────────────────────────────────────────┐
│        ↓                        CHILD PROCESS                     │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ study_process_wrapper()                                  │     │
│  │                                                          │     │
│  │  - Re-imports run_study.py (→ S4L starts early)          │     │
│  │  - Creates QueueGUI (proxy to Queue)                     │     │
│  │  - Creates Profiler                                      │     │
│  │  - Loads Config                                          │     │
│  │  - Runs the actual study (NearFieldStudy/FarFieldStudy)  │     │
│  │                                                          │     │
│  │  QueueGUI.log() → queue.put({...})                       │     │
│  │  QueueGUI.update_progress() → queue.put({...})           │     │
│  │                                                          │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## Logging Architecture

GOLIAT has two main loggers:
1. **`progress`** - High-level progress messages for GUI/user
2. **`verbose`** - Detailed technical logs

### Logger Setup (`logging_manager.py`):

```python
setup_loggers() returns:
- progress_logger: logging.Logger
- verbose_logger: logging.Logger  
- session_timestamp: str

Each logger has:
- FileHandler → writes to logs/{timestamp}.log and logs/{timestamp}.progress.log
- StreamHandler → writes to stdout (terminal)
```

### Logging in Different Contexts:

| Context | Logger Location | File Output | Console Output | GUI Output |
|---------|-----------------|-------------|----------------|------------|
| Headless (use_gui=false) | Main process | ✓ | ✓ | N/A |
| GUI Main Process | Main process | ✓ | ✓ | Via ProgressGUI |
| GUI Child Process | Child process | ✓ writes to files | Depends on stdout | Via QueueGUI → Queue → GUI |

### QueueGUI: The IPC Bridge

`QueueGUI` is a proxy class that looks like `ProgressGUI` but routes all calls through a `multiprocessing.Queue`:

```python
class QueueGUI:
    def __init__(self, queue, stop_event, profiler, progress_logger, verbose_logger):
        self.queue = queue
        # ...
    
    def log(self, message, level="verbose", log_type="default"):
        # Log locally to file
        # Also send to queue for GUI
        self._send("log", message=message, level=level, log_type=log_type)
    
    def update_overall_progress(self, current, total):
        self._send("overall_progress", current=current, total=total)
    
    def _send(self, msg_type, **kwargs):
        self.queue.put({"type": msg_type, **kwargs})
```

The main process's `QueueHandler` dequeues these and calls the real `ProgressGUI` methods.

---

## Key Technical Details

### multiprocessing.spawn on Windows

Windows uses `spawn` context which:
1. Creates a fresh Python interpreter for child process
2. Re-imports the main module
3. Does NOT share memory with parent
4. Does NOT inherit stdout/stderr connection to parent's terminal

This is why:
- Child process logs to files correctly
- Child process console output may not appear in parent terminal
- Queue is needed for IPC

### S4L Integration Points

```python
from s4l_v1._api import application

# Check if S4L is running
app = application.get_app_safe()  # Returns None if not running

# Start S4L
application.run_application(disable_ui_plugins=True)

# Create documents, simulations, etc.
from s4l_v1 import document
doc = document.New()
```

### The `ensure_s4l_running()` Function

Found in `goliat/utils/core.py`:
```python
def ensure_s4l_running():
    """Ensures Sim4Life is running, starting it if necessary."""
    if application.get_app_safe() is None:
        application.run_application(disable_ui_plugins=True)
```

This was previously where S4L started. The 9.2 fix moves this earlier in the module.

---

## Other Issues Discovered

### 1. `sys.stdout.flush()` crash

When S4L starts early, `sys.stdout` can be `None` in some contexts. Fixed by guarding:
```python
if sys.stdout is not None:
    sys.stdout.flush()
```

### 2. Port 8080 conflict (noted in earlier conversation)

S4L's internal web server conflicts with other processes. This was a known issue.

---

## Lessons Learned

1. **Order matters** - Module-level import order can cause subtle issues
2. **Multiprocessing is tricky** - Child processes re-import modules, executing module-level code again
3. **Test incrementally** - Binary search approach (test_s4l_import_bisect.py) was effective
4. **Document the tests** - Created comprehensive test suite for future debugging
5. **Check all processes** - Issues can appear differently in main vs child processes

---

## Test Files Created

All in `tests/`:
- `test_s4l_multiprocessing.py` - Basic Queue test
- `test_s4l_multiprocessing_extended.py` - Progressive component tests
- `test_s4l_import_order.py` - Import order tests
- `test_s4l_import_bisect.py` - Binary search for problematic imports
- `test_s4l_final_diagnostic.py` - Final isolation tests

These can be used to diagnose future S4L version compatibility issues.

---

## Summary

The Sim4Life 9.2 compatibility issue was caused by a breaking change in how S4L interacts with PySide6/Qt. The fix is simple: **start S4L before importing PySide6**. This must happen in both the main process and any spawned child processes.
