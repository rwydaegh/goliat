#!/usr/bin/env python
"""Generate organized API reference markdown from goliat directory structure.

This script auto-discovers all Python modules in the goliat package and
generates an organized API reference markdown file for mkdocstrings.

Usage:
    python scripts/generate_api_reference.py

The script will:
1. Scan the goliat/ directory for all Python modules
2. Organize them by subdirectory/category
3. Generate docs/reference/api_reference.md with mkdocstrings directives
"""

import ast
from pathlib import Path
from typing import Optional

# Category display names and descriptions (order matters for output)
CATEGORY_CONFIG = {
    # Top-level modules (no subdirectory)
    "_root": {
        "name": "Core Modules",
        "description": "Core functionality for configuration, logging, and utilities.",
        "order": 0,
    },
    # Subdirectories
    "config": {
        "name": "Configuration",
        "description": "Configuration management and settings.",
        "order": 1,
    },
    "studies": {
        "name": "Study Orchestration",
        "description": "Study classes that orchestrate simulation workflows.",
        "order": 2,
    },
    "setups": {
        "name": "Setup Modules",
        "description": "Classes responsible for building the Sim4Life simulation scene.",
        "order": 3,
    },
    "runners": {
        "name": "Execution Strategies",
        "description": "Strategy pattern implementations for different simulation execution methods.",
        "order": 4,
    },
    "extraction": {
        "name": "Results Extraction",
        "description": "Classes for extracting and processing simulation results.",
        "order": 5,
    },
    "analysis": {
        "name": "Analysis",
        "description": "Classes for analyzing and visualizing simulation results.",
        "order": 6,
    },
    "gui": {
        "name": "GUI Components",
        "description": "Graphical user interface for monitoring simulation progress.",
        "order": 7,
    },
    "ai": {
        "name": "AI Assistant",
        "description": "AI-powered assistant for error diagnosis and code assistance.",
        "order": 8,
    },
    "osparc_batch": {
        "name": "oSPARC Batch Processing",
        "description": "Batch processing and worker management for oSPARC cloud execution.",
        "order": 9,
    },
    "dispersion": {
        "name": "Dispersion",
        "description": "Material dispersion fitting and caching.",
        "order": 10,
    },
    "utils": {
        "name": "Utilities",
        "description": "Utility functions and helper modules.",
        "order": 11,
    },
}

# Modules to exclude from documentation
EXCLUDE_MODULES = {
    "__init__",
    "__pycache__",
    "keep_awake",
}

# Subdirectories to exclude entirely
EXCLUDE_DIRS = {
    "__pycache__",
    "paper",  # Not part of the public API
}


def get_main_class_from_file(file_path: Path) -> Optional[str]:
    """Extract the main class name from a Python file.

    Returns the first public (non-underscore) class, or None if no classes exist.
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
    """Convert file path to module path (e.g., goliat.analysis.analyzer)."""
    relative = file_path.relative_to(src_root.parent)
    parts = relative.parts[:-1] + (relative.stem,)
    return ".".join(parts)


def get_module_display_name(filename: str) -> str:
    """Convert filename to a display name."""
    # Remove .py extension and convert to title case
    name = filename.replace(".py", "").replace("_", " ").title()
    return name


def scan_modules(src_root: Path) -> dict:
    """Scan goliat directory and organize modules by category."""
    src_root = Path(src_root)
    categories = {}

    for py_file in sorted(src_root.rglob("*.py")):
        # Skip excluded files
        if py_file.stem in EXCLUDE_MODULES:
            continue
        if any(excl in py_file.parts for excl in EXCLUDE_DIRS):
            continue

        relative_path = py_file.relative_to(src_root)
        parts = relative_path.parts

        # Determine category
        if len(parts) == 1:
            # Top-level module
            category = "_root"
        else:
            # Use first subdirectory as category
            category = parts[0]
            if category in EXCLUDE_DIRS:
                continue

        # Build module info
        module_path = get_module_path(py_file, src_root)
        class_name = get_main_class_from_file(py_file)

        # Determine the best path to document
        if class_name:
            # If there's a main class, document the class specifically
            doc_path = f"{module_path}.{class_name}"
        else:
            # Otherwise document the module
            doc_path = module_path

        # Add to category
        if category not in categories:
            categories[category] = []

        # Determine subcategory for nested modules (e.g., analysis/plots)
        subcategory = None
        if len(parts) > 2:
            subcategory = "/".join(parts[1:-1])

        categories[category].append(
            {
                "file": py_file,
                "filename": py_file.name,
                "module_path": module_path,
                "doc_path": doc_path,
                "class_name": class_name,
                "subcategory": subcategory,
                "display_name": get_module_display_name(py_file.name),
            }
        )

    return categories


def generate_mkdocstrings_directive(module_path: str) -> str:
    """Generate mkdocstrings directive for a module."""
    return f"""::: {module_path}
    options:
      show_root_heading: true
      show_source: true
"""


def generate_api_reference(
    src_root: Path = Path("goliat"),
    output_path: Path = Path("docs/reference/api_reference.md"),
):
    """Generate organized API reference markdown."""
    src_root = Path(src_root)
    output_path = Path(output_path)

    # Scan modules
    categories = scan_modules(src_root)

    # Start building output
    lines = [
        "# API Reference",
        "",
        "Complete API documentation for GOLIAT, organized by module category.",
        "",
    ]

    # Sort categories by configured order, then alphabetically for unknown categories
    def category_sort_key(cat):
        if cat in CATEGORY_CONFIG:
            return (CATEGORY_CONFIG[cat]["order"], cat)
        return (999, cat)

    sorted_categories = sorted(categories.keys(), key=category_sort_key)

    for category in sorted_categories:
        modules = categories[category]
        if not modules:
            continue

        # Get category config or create default
        config = CATEGORY_CONFIG.get(
            category,
            {
                "name": category.replace("_", " ").title(),
                "description": None,
            },
        )

        # Category header
        lines.append(f"## {config['name']}")
        lines.append("")

        if config.get("description"):
            lines.append(config["description"])
            lines.append("")

        # Group by subcategory if present
        subcategories = {}
        for mod in modules:
            subcat = mod["subcategory"] or "_main"
            if subcat not in subcategories:
                subcategories[subcat] = []
            subcategories[subcat].append(mod)

        # Output modules, handling subcategories
        for subcat in sorted(subcategories.keys()):
            subcat_modules = subcategories[subcat]

            if subcat != "_main":
                # Add subcategory header
                subcat_name = subcat.replace("_", " ").replace("/", " / ").title()
                lines.append(f"### {subcat_name}")
                lines.append("")

            for mod in sorted(subcat_modules, key=lambda m: m["filename"]):
                # Add section header for each module
                if subcat == "_main":
                    lines.append(f"### {mod['display_name']}")
                    lines.append("")

                lines.append(generate_mkdocstrings_directive(mod["doc_path"]))
                lines.append("")

        lines.append("---")
        lines.append("")

    # Add CLI scripts section
    lines.extend(
        [
            "## CLI Commands",
            "",
            "Entry point commands for running studies and analysis.",
            "",
            '!!! note "CLI Commands"',
            "    These are top-level CLI commands. Run `goliat --help` for full usage information.",
            "",
            "| Command | Description |",
            "|---------|-------------|",
            "| `goliat study` | Run a simulation study |",
            "| `goliat analyze` | Run post-processing analysis |",
            "| `goliat parallel` | Run parallel study batches |",
            "| `goliat worker` | Run as a cloud worker |",
            "| `goliat free-space` | Run free-space validation |",
            "| `goliat init` | Initialize GOLIAT environment |",
            "| `goliat status` | Show setup status |",
            "| `goliat validate` | Validate configuration files |",
            "| `goliat version` | Show version information |",
        ]
    )

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # Summary
    total_modules = sum(len(mods) for mods in categories.values())
    print(f"✅ Generated API reference at {output_path}")
    print(f"   Found {len(categories)} categories with {total_modules} modules")
    print(f"   Categories: {', '.join(sorted_categories)}")


if __name__ == "__main__":
    generate_api_reference()
