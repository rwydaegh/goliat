#!/usr/bin/env python
"""Generate organized API reference markdown from goliat directory structure."""

import ast
import os
from pathlib import Path
from typing import Dict, List, Tuple

# Mapping of directory paths to category names and descriptions
CATEGORY_MAPPING = {
    "core": {
        "name": "Core Modules",
        "description": "Core functionality for configuration, logging, and utilities.",
        "modules": {
            "config.py": {"name": "Configuration", "description": None},
            "utils.py": {"name": "Utilities", "description": None},
            "profiler.py": {"name": "Profiling", "description": None},
            "logging_manager.py": {"name": "Logging", "description": None},
            "colors.py": {"name": "Colors", "description": None},
            "data_extractor.py": {"name": "Data Management", "description": None},
            "project_manager.py": {"name": "Project Management", "description": None},
            "antenna.py": {"name": "Antenna", "description": None},
        },
    },
    "studies": {
        "name": "Study Orchestration",
        "description": "Study classes that orchestrate simulation workflows.",
        "subcategories": {
            "base_study.py": {"name": "Base Study", "description": None},
            "near_field_study.py": {"name": "Near-Field Study", "description": None},
            "far_field_study.py": {"name": "Far-Field Study", "description": None},
        },
    },
    "setups": {
        "name": "Setup Modules",
        "description": "Classes responsible for building the Sim4Life simulation scene.",
        "subcategories": {
            "base_setup.py": {"name": "Base Setup", "description": None},
            "near_field_setup.py": {"name": "Near-Field Setup", "description": None},
            "far_field_setup.py": {"name": "Far-Field Setup", "description": None},
            "phantom_setup.py": {"name": "Phantom Setup", "description": None},
            "placement_setup.py": {"name": "Placement Setup", "description": None},
            "material_setup.py": {"name": "Material Setup", "description": None},
            "gridding_setup.py": {"name": "Gridding Setup", "description": None},
            "boundary_setup.py": {"name": "Boundary Setup", "description": None},
            "source_setup.py": {"name": "Source Setup", "description": None},
        },
    },
    "simulation_runner.py": {
        "name": "Simulation Execution",
        "description": None,
        "modules": {},
    },
    "runners": {
        "name": "Execution Strategies",
        "description": "Strategy pattern implementations for different simulation execution methods.",
        "subcategories": {
            "execution_strategy.py": {"name": "Base Strategy", "description": None},
            "isolve_manual_strategy.py": {"name": "iSolve Manual Strategy", "description": None},
            "sim4life_api_strategy.py": {"name": "Sim4Life API Strategy", "description": None},
            "osparc_direct_strategy.py": {"name": "oSPARC Direct Strategy", "description": None},
        },
    },
    "extraction": {
        "name": "Results Extraction",
        "description": "Classes for extracting and processing simulation results.",
        "subcategories": {
            "cleaner.py": {"name": "Cleanup", "description": None},
            "reporter.py": {"name": "Reporting", "description": None},
            "json_encoder.py": {"name": "JSON Encoding", "description": None},
            "sar_extractor.py": {"name": "SAR Extraction", "description": None},
            "power_extractor.py": {"name": "Power Extraction", "description": None},
            "sensor_extractor.py": {"name": "Sensor Extraction", "description": None},
        },
        "base_module": "results_extractor.py",
        "base_name": "Base Extraction",
    },
    "analysis": {
        "name": "Analysis",
        "description": "Classes for analyzing and visualizing simulation results.",
        "subcategories": {
            "analyzer.py": {"name": "Analyzer", "description": None},
            "base_strategy.py": {"name": "Analysis Strategies", "description": None},
            "near_field_strategy.py": {"name": "Near-Field Strategy", "description": None},
            "far_field_strategy.py": {"name": "Far-Field Strategy", "description": None},
            "plotter.py": {"name": "Plotting", "description": None},
        },
    },
    "gui": {
        "name": "GUI Components",
        "description": "Graphical user interface for monitoring simulation progress.",
        "subcategories": {
            "progress_gui.py": {"name": "Main GUI", "description": None},
            "queue_gui.py": {"name": "GUI Communication", "description": None},
            "components": {
                "name": "GUI Components",
                "description": None,
                "modules": [
                    "queue_handler.py",
                    "status_manager.py",
                    "timings_table.py",
                    "data_manager.py",
                    "ui_builder.py",
                    "progress_animation.py",
                    "tray_manager.py",
                ],
            },
            "plots": {
                "name": "Plot Components",
                "description": None,
                "modules": [
                    "overall_progress_plot.py",
                    "pie_charts_manager.py",
                    "system_utilization_plot.py",
                    "time_remaining_plot.py",
                ],
            },
        },
    },
}


def get_main_class_from_file(file_path: Path) -> str:
    """Extract the main class name from a Python file.

    Returns the first public (non-underscore) class, or the first class if no public ones exist.
    For modules without classes, returns None.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
        # Prefer public classes (not starting with _)
        public_classes = [c for c in classes if not c.startswith("_")]
        if public_classes:
            return public_classes[0]
        elif classes:
            return classes[0]
    except Exception:
        pass
    return None


def get_module_path(file_path: Path, src_root: Path) -> str:
    """Convert file path to module path."""
    relative = file_path.relative_to(src_root.parent)
    parts = relative.parts[:-1] + (relative.stem,)
    return ".".join(parts)


def get_class_path(file_path: Path, src_root: Path) -> str:
    """Get full class path including class name."""
    module_path = get_module_path(file_path, src_root)
    class_name = get_main_class_from_file(file_path)
    if class_name:
        return f"{module_path}.{class_name}"
    return module_path


def scan_goliat_directory(src_root: Path) -> Dict[str, List[Tuple[Path, str]]]:
    """Scan goliat directory and organize files by category."""
    categories = {}
    src_root = Path(src_root)

    # Collect all Python files
    all_files = []
    for py_file in src_root.rglob("*.py"):
        if "__pycache__" not in str(py_file) and py_file.name != "__init__.py":
            relative_path = py_file.relative_to(src_root)
            all_files.append((py_file, relative_path))

    # Organize by category
    for file_path, relative_path in all_files:
        parts = relative_path.parts
        if len(parts) == 1:
            # Top-level module
            if parts[0] == "simulation_runner.py":
                categories.setdefault("simulation_runner.py", []).append((file_path, str(relative_path)))
            else:
                categories.setdefault("core", []).append((file_path, str(relative_path)))
        elif len(parts) == 2:
            # Package module
            package = parts[0]
            if package in ["studies", "setups", "extraction", "analysis", "gui", "runners"]:
                categories.setdefault(package, []).append((file_path, str(relative_path)))
            else:
                # Unknown package, add to core
                categories.setdefault("core", []).append((file_path, str(relative_path)))
        elif len(parts) == 3:
            # Nested package (e.g., gui/components, gui/components/plots)
            package = parts[0]
            if package == "gui" and parts[1] == "components":
                categories.setdefault("gui", []).append((file_path, str(relative_path)))
            else:
                categories.setdefault(package, []).append((file_path, str(relative_path)))
        elif len(parts) == 4:
            # Deeply nested (e.g., gui/components/plots)
            package = parts[0]
            if package == "gui" and parts[1] == "components" and parts[2] == "plots":
                categories.setdefault("gui", []).append((file_path, str(relative_path)))
            else:
                categories.setdefault(package, []).append((file_path, str(relative_path)))

    return categories


def generate_mkdocstrings_directive(module_path: str, options: Dict = None) -> str:
    """Generate mkdocstrings directive."""
    if options is None:
        options = {}
    default_options = {
        "show_root_heading": "true",
        "show_source": "true",
    }
    default_options.update(options)
    options_str = "\n".join(f"      {k}: {v}" for k, v in default_options.items())
    return f"::: {module_path}\n    options:\n{options_str}"


def generate_section(category_key: str, files: List[Tuple[Path, str]], src_root: Path, output_lines: List[str]):
    """Generate markdown section for a category."""
    if category_key not in CATEGORY_MAPPING:
        return

    category = CATEGORY_MAPPING[category_key]
    output_lines.append(f"## {category['name']}")
    output_lines.append("")

    if category.get("description"):
        output_lines.append(category["description"])
        output_lines.append("")

    if category_key == "core":
        # Group core modules by subcategory
        current_subcat = None
        for file_path, relative_path in sorted(files):
            filename = os.path.basename(relative_path)
            if filename in category.get("modules", {}):
                subcat_info = category["modules"][filename]
                if subcat_info["name"] != current_subcat:
                    if current_subcat is not None:
                        output_lines.append("")
                    output_lines.append(f"### {subcat_info['name']}")
                    output_lines.append("")
                    current_subcat = subcat_info["name"]
                module_path = get_module_path(file_path, src_root)
                class_name = get_main_class_from_file(file_path)
                # Use module path directly for modules without clear single class
                # or when class name doesn't match module purpose
                if class_name and filename.replace(".py", "").lower() in class_name.lower():
                    output_lines.append(generate_mkdocstrings_directive(f"{module_path}.{class_name}"))
                else:
                    # Use module path - mkdocstrings will show all public classes
                    output_lines.append(generate_mkdocstrings_directive(module_path))
                output_lines.append("")

    elif category_key == "extraction":
        # Handle base module first
        base_file = None
        other_files = []
        for file_path, relative_path in files:
            if os.path.basename(relative_path) == category.get("base_module"):
                base_file = (file_path, relative_path)
            else:
                other_files.append((file_path, relative_path))

        if base_file:
            output_lines.append("### " + category.get("base_name", "Base"))
            output_lines.append("")
            module_path = get_module_path(base_file[0], src_root)
            class_name = get_main_class_from_file(base_file[0])
            if class_name:
                output_lines.append(generate_mkdocstrings_directive(f"{module_path}.{class_name}"))
            else:
                output_lines.append(generate_mkdocstrings_directive(module_path))
            output_lines.append("")

        # Group other files by subcategory
        current_subcat = None
        for file_path, relative_path in sorted(other_files):
            filename = os.path.basename(relative_path)
            if filename in category.get("subcategories", {}):
                subcat_info = category["subcategories"][filename]
                if subcat_info["name"] != current_subcat:
                    if current_subcat is not None:
                        output_lines.append("")
                    output_lines.append(f"### {subcat_info['name']}")
                    output_lines.append("")
                    current_subcat = subcat_info["name"]
                module_path = get_module_path(file_path, src_root)
                class_name = get_main_class_from_file(file_path)
                # Use module path directly for modules without clear single class
                # or when class name doesn't match module purpose
                if class_name and filename.replace(".py", "").lower() in class_name.lower():
                    output_lines.append(generate_mkdocstrings_directive(f"{module_path}.{class_name}"))
                else:
                    # Use module path - mkdocstrings will show all public classes
                    output_lines.append(generate_mkdocstrings_directive(module_path))
                output_lines.append("")

    elif category_key == "gui":
        # Special handling for GUI
        progress_gui = None
        queue_gui = None
        components = []
        plots = []
        for file_path, relative_path in files:
            filename = os.path.basename(relative_path)
            relative_str = str(relative_path)
            if filename == "progress_gui.py":
                progress_gui = (file_path, relative_path)
            elif filename == "queue_gui.py":
                queue_gui = (file_path, relative_path)
            elif "components/plots" in relative_str:
                plots.append((file_path, relative_path))
            elif "components" in relative_str:
                components.append((file_path, relative_path))

        if progress_gui:
            output_lines.append("### Main GUI")
            output_lines.append("")
            file_path, relative_path = progress_gui
            filename = os.path.basename(relative_path)
            module_path = get_module_path(file_path, src_root)
            class_name = get_main_class_from_file(file_path)
            if class_name and filename.replace(".py", "").lower() in class_name.lower():
                output_lines.append(generate_mkdocstrings_directive(f"{module_path}.{class_name}"))
            else:
                output_lines.append(generate_mkdocstrings_directive(module_path))
            output_lines.append("")

        if queue_gui:
            output_lines.append("### GUI Communication")
            output_lines.append("")
            file_path, relative_path = queue_gui
            filename = os.path.basename(relative_path)
            module_path = get_module_path(file_path, src_root)
            class_name = get_main_class_from_file(file_path)
            if class_name and filename.replace(".py", "").lower() in class_name.lower():
                output_lines.append(generate_mkdocstrings_directive(f"{module_path}.{class_name}"))
            else:
                output_lines.append(generate_mkdocstrings_directive(module_path))
            output_lines.append("")

        if components:
            output_lines.append("### GUI Components")
            output_lines.append("")
            for file_path, relative_path in sorted(components):
                filename = os.path.basename(relative_path)
                module_path = get_module_path(file_path, src_root)
                class_name = get_main_class_from_file(file_path)
                if class_name and filename.replace(".py", "").lower() in class_name.lower():
                    output_lines.append(generate_mkdocstrings_directive(f"{module_path}.{class_name}"))
                else:
                    output_lines.append(generate_mkdocstrings_directive(module_path))
                output_lines.append("")

        if plots:
            output_lines.append("### Plot Components")
            output_lines.append("")
            # Use module paths (document entire module) - matches pattern for other GUI components
            for file_path, relative_path in sorted(plots):
                filename = os.path.basename(relative_path)
                # Skip __init__.py and private modules
                if filename.startswith("_") or filename == "__init__.py":
                    continue
                # Use module path only (most reliable for mkdocstrings)
                # Document the entire module instead of specific class
                # This matches the pattern used for other GUI components
                module_path = get_module_path(file_path, src_root)
                output_lines.append(generate_mkdocstrings_directive(module_path))
                output_lines.append("")

    elif category_key in ["studies", "setups", "analysis", "runners"]:
        # Group by subcategory
        current_subcat = None
        for file_path, relative_path in sorted(files):
            filename = os.path.basename(relative_path)
            if filename in category.get("subcategories", {}):
                subcat_info = category["subcategories"][filename]
                if subcat_info["name"] != current_subcat:
                    if current_subcat is not None:
                        output_lines.append("")
                    output_lines.append(f"### {subcat_info['name']}")
                    output_lines.append("")
                    current_subcat = subcat_info["name"]
                module_path = get_module_path(file_path, src_root)
                class_name = get_main_class_from_file(file_path)
                # Use module path directly for modules without clear single class
                # or when class name doesn't match module purpose
                if class_name and filename.replace(".py", "").lower() in class_name.lower():
                    output_lines.append(generate_mkdocstrings_directive(f"{module_path}.{class_name}"))
                else:
                    # Use module path - mkdocstrings will show all public classes
                    output_lines.append(generate_mkdocstrings_directive(module_path))
                output_lines.append("")

    elif category_key == "simulation_runner.py":
        # Single module
        file_path, _ = files[0]
        module_path = get_module_path(file_path, src_root)
        class_name = get_main_class_from_file(file_path)
        if class_name:
            output_lines.append(generate_mkdocstrings_directive(f"{module_path}.{class_name}"))
        else:
            output_lines.append(generate_mkdocstrings_directive(module_path))
        output_lines.append("")

    output_lines.append("---")
    output_lines.append("")


def generate_api_reference(src_root: Path = Path("goliat"), output_path: Path = Path("docs/reference/api_reference.md")):
    """Generate organized API reference markdown."""
    src_root = Path(src_root)
    output_path = Path(output_path)

    output_lines = [
        "# API Reference",
        "",
        "Complete API documentation for GOLIAT, organized by module category.",
        "",
    ]

    # Scan directory
    categories = scan_goliat_directory(src_root)

    # Generate sections in order
    category_order = ["core", "studies", "setups", "simulation_runner.py", "runners", "extraction", "analysis", "gui"]
    for category_key in category_order:
        if category_key in categories:
            generate_section(category_key, categories[category_key], src_root, output_lines)

    # Add scripts section
    output_lines.extend(
        [
            "## Scripts",
            "",
            "Entry point scripts for running studies and analysis.",
            "",
            '!!! note "Scripts"',
            "    These are top-level scripts for running studies. They are not part of the core API but are included for reference.",
            "",
            "- `goliat study` - Main entry point for running studies",
            "- `goliat analyze` - Entry point for post-processing analysis",
            "- `goliat parallel` - Script for running parallel study batches",
            "- `goliat free-space` - Script for free-space validation runs",
            "- `goliat init` - Initialize GOLIAT environment (install dependencies, setup)",
            "- `goliat status` - Show setup status and environment information",
            "- `goliat validate` - Validate configuration files",
            "- `goliat version` - Show GOLIAT version information",
        ]
    )

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    print(f"✅ Generated API reference at {output_path}")
    print(f"   Found {len(categories)} categories with {sum(len(files) for files in categories.values())} modules")


if __name__ == "__main__":
    generate_api_reference()
