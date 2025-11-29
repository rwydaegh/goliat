"""Parallel plot execution utilities for speeding up plot generation."""

import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable

import matplotlib

# Set thread-safe backend before importing pyplot
matplotlib.use("Agg")  # Thread-safe, non-interactive backend

import matplotlib.pyplot as plt


# Top-level function to ensure picklability for ProcessPoolExecutor
def _execute_plot_task(func: Callable, *args, **kwargs):
    """Executes a plot function with proper matplotlib setup in a separate process.

    Args:
        func: Original plot function.
        *args: Positional arguments for the function.
        **kwargs: Keyword arguments for the function.

    Returns:
        Result of the function call.
    """
    # Re-import matplotlib inside the process to ensure fresh state
    import matplotlib

    # Set backend to Agg (non-interactive)
    matplotlib.use("Agg", force=True)

    # Import pyplot after setting backend

    # Configure styles if available
    try:
        import scienceplots  # noqa: F401

        plt.style.use(["science", "ieee", "no-latex"])
    except ImportError:
        pass

    # Ensure no interactive mode
    plt.ioff()

    try:
        return func(*args, **kwargs)
    finally:
        # Clean up figures to free memory
        plt.close("all")


class ParallelPlotExecutor:
    """Executes plot generation tasks in parallel using process pool.

    Uses ProcessPoolExecutor for plot generation tasks to ensure full isolation
    of matplotlib state, avoiding thread-safety issues with rcParams and backends.
    """

    def __init__(self, max_workers: int | None = None):
        """Initialize parallel plot executor.

        Args:
            max_workers: Maximum number of worker processes. If None, uses default
                        (typically os.cpu_count()).
        """
        if max_workers is None:
            # Default: use CPU count but ensure at least 1, cap at 16 to avoid excessive memory usage
            # Plotting can be memory intensive with large DataFrames
            max_workers = min(16, (os.cpu_count() or 1))
        self.max_workers = max_workers
        # No need to set backend here, it will be set in each process

    def _ensure_thread_safe_backend(self):
        """Deprecated: No longer needed with ProcessPoolExecutor."""
        pass

    def execute_plots(
        self,
        plot_tasks: list[tuple[Callable, tuple, dict]],
        task_descriptions: list[str] | None = None,
    ):
        """Execute multiple plot generation tasks in parallel.

        Args:
            plot_tasks: List of (function, args_tuple, kwargs_dict) tuples.
            task_descriptions: Optional list of task descriptions for logging.
                              If None, uses function names.

        Returns:
            List of results (or exceptions) in completion order.
        """
        if not plot_tasks:
            return []

        if task_descriptions is None:
            task_descriptions = [f"{func.__name__}" for func, _, _ in plot_tasks]

        results = []
        completed_count = 0
        total_tasks = len(plot_tasks)

        # Use ProcessPoolExecutor for isolation
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {}
            for (func, args, kwargs), desc in zip(plot_tasks, task_descriptions):
                # Submit the top-level wrapper function with the actual function as the first arg
                future = executor.submit(_execute_plot_task, func, *args, **kwargs)
                future_to_task[future] = desc

            # Process completed tasks
            for future in as_completed(future_to_task):
                task_desc = future_to_task[future]
                completed_count += 1
                try:
                    result = future.result()
                    results.append((task_desc, result, None))
                    logging.getLogger("progress").info(
                        f"  - Completed plot ({completed_count}/{total_tasks}): {task_desc}",
                        extra={"log_type": "success"},
                    )
                except Exception as e:
                    results.append((task_desc, None, e))
                    logging.getLogger("progress").error(
                        f"  - ERROR in plot '{task_desc}': {str(e)}",
                        extra={"log_type": "error"},
                    )

        return results

    @staticmethod
    def _wrap_plot_function(func: Callable) -> Callable:
        """Deprecated: Use _execute_plot_task instead. Kept for compatibility if needed."""
        return func
