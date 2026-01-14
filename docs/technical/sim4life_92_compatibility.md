# GOLIAT Sim4Life 9.2 Compatibility Notes

## Status: Complete ✓

This document tracks the compatibility work for supporting both Sim4Life 8.2 and 9.2 in GOLIAT.

---

## 1. Version Detection Module

A new `goliat/utils/version.py` module provides version detection and conditional logic:

```python
from goliat.utils import (
    get_sim4life_version,      # Returns (major, minor, patch) tuple
    is_sim4life_92_or_later,   # True if running 9.2+
    is_version_supported,       # Checks if version is 8.2.x or 9.2.x
    get_version_display_string, # Returns "9.2.0" or similar
)

# Example usage
if is_sim4life_92_or_later():
    # Use 9.2-specific behavior
    pass
```

### Supported Versions
- **8.2.x**: Original supported version
- **9.2.x**: Fully supported (recommended for new installations)

### NOT Supported
- **9.0.x**: Internal/beta release, explicitly excluded

### Hardware Note: Blackwell GPUs
- **RTX 5090, B100, etc.**: On Sim4Life 9.2.1.19976, aXware is not supported on Blackwell architecture GPUs. Only the CUDA solver is available.

---

## 2. Code Updates Completed ✓

| File | Change |
|------|--------|
| `goliat/utils/version.py` | **NEW** - Version detection module |
| `goliat/utils/python_interpreter.py` | Updated to use version module, prioritize 9.2 over 8.2, filter out 9.0 |
| `goliat/utils/__init__.py` | Exports version utilities |
| `goliat/runners/osparc_direct_strategy.py` | Updated version message to "8.2 or 9.2" |
| `docs/user_guide/quick_start.md` | Updated to reference 9.2 as recommended version |

### Already Fixed (on this branch)

- [x] Version detection with `get_sim4life_version()` and `is_sim4life_92_or_later()`
- [x] Prioritize 9.2 over 8.2 when selecting interpreters
- [x] Filter out unsupported 9.0 installs
- [x] Relaxed version check to allow non-8.2 versions (with warning)
- [x] Fixed startup order: S4L must init before PySide6 import
- [x] Fixed stdout handling (None stdout in 9.2)
- [x] Added queue-based logging for child process output
- [x] Updated all version messages to reference "8.2 or 9.2"

---

## 3. API Changes Summary

See `PythonAPIReference_DIFF_8_2_to_9_2/API_CHANGES_SUMMARY.md` for full details. Key breaking changes:

1. **Enum System** - `Boost.Python.enum` → `enum.IntEnum` with `ClassVar` pattern
2. **Argument Names** - Some functions re-indexed from `arg1` to `arg0`
3. **Vector Types** - `XCoreModeling.Vec3` consolidated to `QTech.Vec3`
4. **Return Types** - Many `tuple` returns now `list`
5. **Removed Modules** - `Chromium`, `ImagePostPro`, `XNdArray`

### Already Compatible ✓

| Pattern | Status |
|---------|--------|
| `from QTech import Vec3` | Used in `near_field_setup.py:261` - matches 9.2 pattern |
| `XCoreMath.Vec3` | Still available in 9.2 |
| `s4l_v1.model.Vec3` | Works in both versions |
| No `kNone` enum usage | No breaking enum changes found |
| No `.names`/`.values` on S4L enums | Only used on Python dicts/pandas |
| No `AsVtkImage`/`AsVtkMesh` usage | Removed in 9.2, not used |

---

## 4. .bashrc Handling

The `.bashrc` file is automatically updated to use the newest supported Sim4Life version:
- When multiple versions are found, 9.2 is preferred over 8.2
- Version 9.0 is filtered out and never offered as an option
- The PATH is set to include both Python and Scripts directories

---

## 5. Using Version-Specific Code

For code that needs to behave differently between versions:

```python
from goliat.utils.version import is_sim4life_92_or_later

if is_sim4life_92_or_later():
    # 9.2+ specific code
    import XCore
    XCore.RedirectToStdOut(True)  # Needed in 9.2, not in 8.2
else:
    # 8.2 specific code
    pass
```

---

*Updated: 2026-01-14*
