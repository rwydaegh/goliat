# Coloring Rules for Terminal Output

This document outlines the rules for colorizing terminal output using the `colorama` library. The goal is to improve readability and draw the user's attention to the most critical information. All colors are defined in the `COLOR_MAP` dictionary in [`src/colors.py`](src/colors.py:1) to ensure consistency and ease of maintenance.

## How to Use

To apply a color, use the `_log` method from the `LoggingMixin` and specify the `log_type`.

```python
# Example usage:
self._log("This is a warning message.", log_type='warning')
self._log("File saved successfully.", level='progress', log_type='success')
```

**Important**: When adding a `log_type`, do not change the existing `level` parameter (e.g., `level='progress'`). The `level` controls which log file the message goes to, while `log_type` only controls the terminal color.

## Color-to-Type Mapping

This table defines the intended use for each `log_type` and its corresponding color.

| `log_type`  | Color         | Description & Use Cases                                                                                             | Example                                                                                                                            |
|-------------|---------------|---------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| `default`   | White         | Standard, neutral output. Used for messages that don't fit any other category.                                      | `Running full simulation setup...`                                                                                                 |
| `header`    | Bright Magenta| For major section headers that announce the start of a significant phase of the study.                                | `--- Starting Far-Field Study: My Study ---`                                                                                       |
| `progress`  | Green         | High-level progress updates that indicate a specific, positive step forward in the process.                           | `--- Processing Frequency 1/5: 700MHz ---`                                                                                         |
| `success`   | Bright Green  | Indicates the successful completion of a major operation or the entire study.                                       | `--- Study Finished ---` or `All required packages are already installed.`                                                         |
| `info`      | Cyan          | Important, non-critical information that provides context, such as file paths or key configuration settings.        | `Project path set to: D:\...` or `Solver kernel set to: Acceleware`                                                                |
| `highlight` | Bright Yellow | Used to draw attention to a specific value or result within a block of text, such as a key performance metric.        | `Final Balance: 99.87%`                                                                                                            |
| `warning`   | Yellow        | For non-critical issues or potential problems that the user should be aware of, but that don't stop the process.     | `WARNING: Could not extract power balance.` or `GetPower() not available, falling back to manual extraction.`                    |
| `error`     | Red           | For recoverable errors or failures within a specific part of the process. The overall study may continue.             | `ERROR: An error occurred during placement 'by_cheek': ...`                                                                        |
| `fatal`     | Magenta       | For critical, non-recoverable errors that will terminate the study.                                                 | `FATAL ERROR: Could not find simulation bounding box.`                                                                             |
| `verbose`   | Blue          | Detailed, low-level debugging information intended for the `verbose` log stream. Not typically for progress updates.  | `  - Activating line profiler for subtask: setup_simulation`                                                                       |

By following these rules, we can create a more intuitive and effective user experience.