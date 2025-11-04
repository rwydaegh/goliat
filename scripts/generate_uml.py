import os
import subprocess
import sys


def install_package(package):
    """Installs a package using pip."""
    print(f"Installing {package}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])


def check_and_install_packages():
    """Checks for and installs required packages."""
    packages = ["pylint"]
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            install_package(package)


def generate_uml_diagram():
    """Generates UML class and package diagrams using pyreverse."""
    print("Generating UML diagrams...")
    source_dir = "goliat"
    output_dir = "docs"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Construct the full path to the pyreverse executable
    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    pyreverse_executable = os.path.join(scripts_dir, "pyreverse.exe")

    # Run pyreverse to generate both class and package diagrams
    subprocess.check_call(
        [
            pyreverse_executable,
            "-o",
            "puml",
            "-f",
            "ALL",
            "-p",
            "GOLIAT",
            "--output-directory",
            output_dir,
            source_dir,
        ]
    )

    # Rename class diagram file
    classes_output = os.path.join(output_dir, "classes.puml")
    classes_generated = os.path.join(output_dir, "classes_GOLIAT.puml")
    if os.path.exists(classes_generated):
        if os.path.exists(classes_output):
            os.remove(classes_output)
        os.rename(classes_generated, classes_output)
        print(f"✅ Class diagram generated at {classes_output}")

    # Rename package diagram file (if generated)
    packages_output = os.path.join(output_dir, "packages_GOLIAT.puml")
    if os.path.exists(packages_output):
        print(f"✅ Package diagram generated at {packages_output}")
    else:
        print("⚠️  Package diagram not generated (this is normal if packages option is not used)")


def generate_uml_markdown():
    """Generates uml.md markdown file from the generated .puml files."""
    output_dir = "docs"
    uml_md_path = os.path.join(output_dir, "uml.md")

    # Read the PlantUML files
    classes_puml_path = os.path.join(output_dir, "classes.puml")
    packages_puml_path = os.path.join(output_dir, "packages_GOLIAT.puml")

    uml_content = [
        "# UML Diagrams",
        "",
        "These diagrams are generated from the Python sources under `goliat/` using Pyreverse (from Pylint). "
        "The generator script is [`scripts/generate_uml.py`](https://github.com/rwydaegh/goliat/blob/master/scripts/generate_uml.py).",
        "",
        "<details>",
        "<summary>Class Diagram</summary>",
        "",
        "```kroki-plantuml",
    ]

    # Read and add class diagram
    if os.path.exists(classes_puml_path):
        with open(classes_puml_path, "r", encoding="utf-8") as f:
            uml_content.extend(f.read().splitlines())
        uml_content.append("```")
        uml_content.append("")
        uml_content.append("</details>")
        uml_content.append("")
    else:
        uml_content.append("# Class diagram not yet generated")
        uml_content.append("```")
        uml_content.append("")
        uml_content.append("</details>")
        uml_content.append("")

    # Add package diagram
    uml_content.extend(
        [
            "<details>",
            "<summary>Packages Diagram</summary>",
            "",
            "```kroki-plantuml",
        ]
    )

    if os.path.exists(packages_puml_path):
        with open(packages_puml_path, "r", encoding="utf-8") as f:
            uml_content.extend(f.read().splitlines())
        uml_content.append("```")
        uml_content.append("")
        uml_content.append("</details>")
        uml_content.append("")
    else:
        uml_content.append("# Package diagram not yet generated")
        uml_content.append("```")
        uml_content.append("")
        uml_content.append("</details>")
        uml_content.append("")

    # Add viewing instructions
    uml_content.extend(
        [
            "How to view",
            "- Right click the above image and open in a new tab. Zoom in and pan around.",
            "- Alternatively, use any PlantUML viewer (e.g., VS Code PlantUML extension, IntelliJ PlantUML plugin, or https://www.plantuml.com/plantuml).",
        ]
    )

    # Write the markdown file
    with open(uml_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(uml_content))

    print(f"✅ Markdown file generated at {uml_md_path}")


def main():
    """Main function to generate the UML diagrams and markdown file."""
    # Ensure we are in the project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(project_root)

    check_and_install_packages()
    generate_uml_diagram()
    generate_uml_markdown()


if __name__ == "__main__":
    main()
