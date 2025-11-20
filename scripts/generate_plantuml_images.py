#!/usr/bin/env python
"""Generate PlantUML images and replace kroki code blocks with image references."""

import re
import requests
from pathlib import Path
from typing import List, Tuple

try:
    from plantuml import PlantUML

    PLANTUML_AVAILABLE = True
except ImportError:
    PLANTUML_AVAILABLE = False
    print("⚠️  plantuml package not available, will use online service")

# PlantUML online server (fallback)
PLANTUML_SERVER = "https://www.plantuml.com/plantuml"


def generate_image_using_library(plantuml_code: str, output_path: Path) -> bool:
    """Generate image using plantuml Python library."""
    if not PLANTUML_AVAILABLE:
        return False

    try:
        # Use online PlantUML server via library
        p = PlantUML(url=PLANTUML_SERVER + "/svg/")
        svg_data = p.processes(plantuml_code)

        if svg_data and len(svg_data) > 0:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(svg_data)
            return True
        return False
    except Exception as e:
        print(f"      Warning: Library method failed: {e}")
        return False


def generate_image_using_online(plantuml_code: str, output_path: Path) -> bool:
    """Generate image using PlantUML online server (direct POST)."""
    try:
        # Use POST method for large diagrams
        response = requests.post(
            f"{PLANTUML_SERVER}/svg/", data=plantuml_code.encode("utf-8"), headers={"Content-Type": "text/plain; charset=utf-8"}, timeout=60
        )

        if response.status_code == 200:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            print(f"      ERROR: HTTP {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"      ERROR: {e}")
        return False


def generate_image(plantuml_code: str, output_path: Path) -> bool:
    """Generate PlantUML image using best available method."""
    # Try library first, then online POST
    if PLANTUML_AVAILABLE:
        if generate_image_using_library(plantuml_code, output_path):
            return True

    # Fallback to direct POST
    return generate_image_using_online(plantuml_code, output_path)


def extract_plantuml_blocks(content: str) -> List[Tuple[str, str, int, int]]:
    """Extract PlantUML code blocks from markdown.

    Returns: List of (code, language, start_pos, end_pos)
    """
    blocks = []
    pattern = r"```kroki-plantuml\n(.*?)```"

    for match in re.finditer(pattern, content, re.DOTALL):
        code = match.group(1).strip()
        blocks.append((code, "kroki-plantuml", match.start(), match.end()))

    return blocks


def replace_with_image(content: str, block_info: Tuple[str, str, int, int], image_path: str) -> str:
    """Replace code block with image reference."""
    code, lang, start, end = block_info

    # Generate image markdown
    image_markdown = f"![UML Diagram]({image_path})"

    # Replace the code block
    new_content = content[:start] + image_markdown + content[end:]
    return new_content


def process_file(file_path: Path, output_dir: Path) -> bool:
    """Process a markdown file and generate images."""
    print(f"\nProcessing {file_path.name}...")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = extract_plantuml_blocks(content)
    if not blocks:
        print("   No PlantUML blocks found")
        return True

    print(f"   Found {len(blocks)} PlantUML block(s)")

    # Process each block
    new_content = content
    offset = 0  # Track offset from replacements

    for i, (code, lang, start, end) in enumerate(blocks):
        print(f"   Processing block {i + 1}/{len(blocks)}...")

        # Add @startuml/@enduml if missing
        full_code = code
        if not full_code.startswith("@startuml"):
            full_code = "@startuml\n" + full_code
        if not full_code.endswith("@enduml"):
            full_code = full_code + "\n@enduml"

        # Generate image filename
        # Try to extract diagram name from code
        diagram_name_match = re.search(r"@startuml\s+(\w+)", full_code)
        if diagram_name_match:
            diagram_name = diagram_name_match.group(1)
        else:
            diagram_name = f"diagram_{i + 1}"

        image_filename = f"{file_path.stem}_{diagram_name}.svg"
        image_path = f"img/uml/{image_filename}"
        image_output_path = output_dir / "img" / "uml" / image_filename

        # Generate image
        print(f"      Generating image: {image_filename}")

        if generate_image(full_code, image_output_path):
            print(f"      OK: Downloaded to {image_output_path}")

            # Replace code block with image
            # Adjust positions for previous replacements
            adj_start = start + offset
            adj_end = end + offset

            image_markdown = f"![UML Diagram]({image_path})"
            new_content = new_content[:adj_start] + image_markdown + new_content[adj_end:]
            offset += len(image_markdown) - (adj_end - adj_start)
        else:
            print("      ERROR: Failed to generate image")
            return False

    # Write updated content
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"   OK: Updated {file_path.name}")
    return True


def main():
    """Main function."""
    docs_dir = Path("docs")
    output_dir = Path("docs")

    files_to_process = [
        docs_dir / "uml.md",
        docs_dir / "developer_guide" / "uml.md",
    ]

    print("Generating PlantUML images...")
    print("=" * 60)

    success = True
    for file_path in files_to_process:
        if not file_path.exists():
            print(f"WARNING: File not found: {file_path}")
            continue

        if not process_file(file_path, output_dir):
            success = False

    print("\n" + "=" * 60)
    if success:
        print("SUCCESS: All images generated successfully!")
        print("\nNext steps:")
        print("1. Review the generated images in docs/img/uml/")
        print("2. Optionally disable kroki plugin in mkdocs.yml")
        print("3. Rebuild docs: mkdocs build")
    else:
        print("ERROR: Some images failed to generate")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
