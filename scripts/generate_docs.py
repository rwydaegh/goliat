import os
import subprocess
import sys
import yaml

def install_package(package):
    """Installs a package using pip."""
    print(f"Installing {package}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def check_and_install_packages():
    """Checks for and installs required packages."""
    packages = [
        "mkdocs",
        "mkdocs-material",
        "mkdocstrings",
        "mkdocstrings-python",
        "pymdown-extensions",
    ]
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            install_package(package)

def create_mkdocs_config():
    """Creates the mkdocs.yml configuration file (Material + mkdocstrings)."""
    print("Creating mkdocs.yml...")

    mkdocs_config = {
        'site_name': 'GOLIAT Documentation',
        'theme': {
            'name': 'material',
            'features': [
                'navigation.tabs',
                'navigation.sections',
                'toc.integrate',
                'navigation.top',
                'search.suggest',
                'search.highlight',
                'content.tabs.link',
            ],
            'palette': [
                {'scheme': 'default', 'toggle': {'icon': 'material/toggle-switch-off-outline', 'name': 'Switch to dark mode'}},
                {'scheme': 'slate', 'toggle': {'icon': 'material/toggle-switch', 'name': 'Switch to light mode'}},
            ],
        },
        'nav': [
            {'Home': 'index.md'},
            {'Architecture': 'architecture_overview.md'},
            {'Guides': [
                {'Coloring rules': 'COLORING_RULES.md'},
                {'Legacy GUI/Profiling/Logger': 'old_good_GUI-Profiling-Logger.md'},
            ]},
            {'API Reference': 'api.md'},
            {'UML Diagram': 'classes.puml'},
        ],
        'plugins': [
            'search',
            {
                'mkdocstrings': {
                    'handlers': {
                        'python': {
                            'options': {
                                'show_root_heading': True,
                                'show_source': False,
                                'members_order': 'source',
                                'docstring_style': 'google',
                                'filters': ['!^_', '^__init__$'],
                            }
                        }
                    }
                }
            },
        ],
        'markdown_extensions': [
            'admonition',
            {'toc': {'permalink': True}},
            'footnotes',
            'attr_list',
            'pymdownx.details',
            'pymdownx.snippets',
            'pymdownx.superfences',
            'pymdownx.highlight',
            'pymdownx.tabbed',
        ],
    }

    with open("mkdocs.yml", "w", encoding="utf-8") as f:
        yaml.dump(mkdocs_config, f, sort_keys=False, allow_unicode=True)

def ensure_docs_index():
    """Ensures docs/index.md exists."""
    index_path = os.path.join("docs", "index.md")
    if not os.path.exists(index_path):
        print("Creating main documentation page (docs/index.md)...")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("# GOLIAT Project Documentation\n\nWelcome to the documentation for the GOLIAT project.")

def write_api_page():
    """Creates docs/api.md with mkdocstrings directive for the whole src package."""
    api_path = os.path.join("docs", "api.md")
    content = """# API Reference

This API reference is auto-generated at build time using mkdocstrings and your code's docstrings.

::: src
options:
  show_root_heading: true
  show_source: false
  members_order: source
  filters:
    - "!^_"
    - "^__init__$"
"""
    with open(api_path, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    """Main function to set up the documentation site."""
    # Ensure we are in the project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    os.chdir(project_root)

    check_and_install_packages()

    os.makedirs("docs", exist_ok=True)

    ensure_docs_index()
    write_api_page()
    create_mkdocs_config()

    print("\nDocumentation setup complete.")
    print("To view the documentation, run 'python -m mkdocs serve' from the project root.")

if __name__ == "__main__":
    main()