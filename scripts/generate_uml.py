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
    """Generates a UML class diagram using pyreverse."""
    print("Generating UML class diagram...")
    source_dir = "src"
    output_dir = "docs"
    output_file = os.path.join(output_dir, "classes")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Construct the full path to the pyreverse executable
    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    pyreverse_executable = os.path.join(scripts_dir, "pyreverse.exe")

    # Run pyreverse
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

    # Rename the output file
    os.rename(os.path.join(output_dir, "classes_GOLIAT.puml"), f"{output_file}.puml")

    print(f"UML diagram generated at {output_file}.puml")


def main():
    """Main function to generate the UML diagram."""
    # Ensure we are in the project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(project_root)

    check_and_install_packages()
    generate_uml_diagram()


if __name__ == "__main__":
    main()
