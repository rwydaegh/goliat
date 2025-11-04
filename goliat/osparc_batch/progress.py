import os
import re
import time
from collections import defaultdict
from pathlib import Path

import colorama

from goliat.osparc_batch.logging_utils import STATUS_COLORS


def get_progress_report(input_files: list[Path], job_statuses: dict, file_to_job_id: dict) -> str:
    """Generates a status summary and a colored file tree string."""
    report_lines = []

    status_counts = defaultdict(int)
    for status_tuple in job_statuses.values():
        status_str = status_tuple if isinstance(status_tuple, tuple) else status_tuple
        state = status_str.split(" ")  # type: ignore
        status_counts[state] += 1
    summary = " | ".join(f"{state}: {count}" for state, count in sorted(status_counts.items()))
    report_lines.append(f"\n{colorama.Fore.BLUE}--- Progress Summary ---\n{summary}\n{colorama.Style.RESET_ALL}")

    tree = {}
    if not input_files:
        return "\n".join(report_lines)

    # --- Optimized Path Handling ---
    try:
        first_path_parts = input_files.parts  # type: ignore
        results_index = first_path_parts.index("results")
        base_path = Path(*first_path_parts[: results_index + 1])
    except (ValueError, IndexError):
        # Fallback for safety, though not expected with the current structure
        common_path_str = os.path.commonpath([str(p.parent) for p in input_files])
        base_path = Path(common_path_str)

    for file_path in input_files:
        try:
            relative_path = file_path.relative_to(base_path)
            parts = list(relative_path.parts)
            if not parts:
                continue

            current_level = tree
            for part in parts[:-1]:
                current_level = current_level.setdefault(part, {})

            filename = parts[-1]
            current_level[filename] = file_to_job_id.get(file_path)

        except (IndexError, ValueError) as e:
            report_lines.append(f"{colorama.Fore.RED}Could not process path {file_path}: {e}{colorama.Style.RESET_ALL}")

    def build_tree_recursive(node, prefix=""):
        def sort_key(item):
            match = re.match(r"(\d+)", item)
            if match:
                return (1, int(match.group(1)))
            return (0, item)

        items = sorted(node.keys(), key=sort_key)
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "

            if isinstance(node[item], dict):
                report_lines.append(f"{prefix}{connector}{colorama.Fore.WHITE}{item}")
                new_prefix = prefix + ("    " if is_last else "│   ")
                build_tree_recursive(node[item], new_prefix)
            else:
                job_id = node[item]
                status_tuple = job_statuses.get(job_id, ("UNKNOWN", time.time()))
                status_str, start_time = status_tuple if isinstance(status_tuple, tuple) else (status_tuple, time.time())

                elapsed_time = time.time() - start_time
                timer_str = f" ({elapsed_time:.0f}s)"

                status = status_str.split(" ")
                color = STATUS_COLORS.get(status, colorama.Fore.WHITE)
                colored_text = f"{color}{item} (oSPARC Job: {job_id}, Status: {status_str}{timer_str}){colorama.Style.RESET_ALL}"
                report_lines.append(f"{prefix}{connector}{colored_text}")

    report_lines.append(f"{colorama.Fore.BLUE}--- File Status Tree ---{colorama.Style.RESET_ALL}")
    build_tree_recursive(tree)
    report_lines.append(f"{colorama.Fore.BLUE}------------------------{colorama.Style.RESET_ALL}\n")

    return "\n".join(report_lines)
