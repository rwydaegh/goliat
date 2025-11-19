"""Constants used throughout the GOLIAT codebase.

This module centralizes magic numbers, thresholds, and hardcoded values
to improve maintainability and reduce technical debt.
"""

# File size thresholds
MIN_H5_FILE_SIZE_BYTES = 8 * 1024 * 1024  # 8MB - minimum size for valid H5 output files
"""Minimum size in bytes for a valid H5 output file.

iSolve sometimes creates incomplete files that are smaller than this threshold.
Files smaller than this are considered invalid.
"""

# File validation thresholds
H5_SIZE_INCREASE_THRESHOLD = 1.1
"""Minimum size increase ratio for Output.h5 compared to Input.h5.

Output.h5 must be at least 10% bigger than Input.h5 to ensure the simulation
completed successfully. This helps detect incomplete or corrupted output files.
"""

# Plotting constants
PLOT_Y_AXIS_BUFFER_MULTIPLIER = 1.1
"""Multiplier for y-axis maximum in plots.

Adds 10% buffer above the maximum value for better visualization.
"""
