#!/usr/bin/env python3
"""Generate LaTeX file with all near-field plots organized by section."""

import re
import shutil
from pathlib import Path
from collections import defaultdict

from cli.utils import get_base_dir


def read_caption_file(txt_path):
    """Read Title and Caption from a .txt file."""
    title = ""
    caption = ""

    if not txt_path.exists():
        return title, caption

    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract Title
    title_match = re.search(r"Title:\s*(.+?)(?:\n|$)", content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()

    # Extract Caption
    caption_match = re.search(r"Caption:\s*(.+)", content, re.DOTALL)
    if caption_match:
        caption = caption_match.group(1).strip()

    return title, caption


def escape_latex(text):
    """Escape special LaTeX characters, but preserve math mode."""
    if not text:
        return ""

    # Preserve math mode delimiters by temporarily replacing them
    # Handle display math $$...$$
    import re

    math_blocks = []

    def replace_math_block(match):
        idx = len(math_blocks)
        math_blocks.append(match.group(0))
        return f"__MATH_BLOCK_{idx}__"

    # Replace $$...$$ (display math)
    text = re.sub(r"\$\$.*?\$\$", replace_math_block, text, flags=re.DOTALL)

    # Replace $...$ (inline math) - but be careful not to match single $ that's part of $$
    # This regex matches $...$ but not $$...$$
    text = re.sub(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)", replace_math_block, text)

    # Now escape special characters in the non-math parts
    text = text.replace("\\", "\\textbackslash{}")
    text = text.replace("&", "\\&")
    text = text.replace("%", "\\%")
    text = text.replace("#", "\\#")
    text = text.replace("^", "\\textasciicircum{}")
    text = text.replace("_", "\\_")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    text = text.replace("~", "\\textasciitilde{}")

    # Restore math blocks (they already contain $ so don't escape those)
    for idx, math_block in enumerate(math_blocks):
        text = text.replace(f"__MATH_BLOCK_{idx}__", math_block)

    return text


def escape_latex_preserve_commands(text):
    """Escape special LaTeX characters, but preserve math mode and LaTeX commands."""
    if not text:
        return ""

    import re

    # Preserve LaTeX commands and math mode by temporarily replacing them
    # Use a placeholder that won't be escaped (contains no special chars)
    preserved_blocks = []

    def get_placeholder(idx):
        return f"PRESERVEDBLOCK{idx}PLACEHOLDER"

    def replace_block(match):
        idx = len(preserved_blocks)
        preserved_blocks.append(match.group(0))
        return get_placeholder(idx)

    # Replace $$...$$ (display math) FIRST - most specific
    text = re.sub(r"\$\$.*?\$\$", replace_block, text, flags=re.DOTALL)

    # Replace $...$ (inline math) - but be careful not to match parts of $$
    text = re.sub(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)", replace_block, text)

    # Find all LaTeX commands and replace them
    # We need to do this manually to handle brace matching
    result = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and (i == 0 or text[i - 1] != "\\"):
            # Potential LaTeX command
            cmd_match = re.match(r"\\([a-zA-Z]+)", text[i:])
            if cmd_match:
                cmd_end = i + cmd_match.end()
                # Check for braces
                if cmd_end < len(text) and text[cmd_end] == "{":
                    # Find matching brace
                    brace_count = 0
                    j = cmd_end
                    while j < len(text):
                        if text[j] == "{":
                            brace_count += 1
                        elif text[j] == "}":
                            brace_count -= 1
                            if brace_count == 0:
                                # Complete command found
                                idx = len(preserved_blocks)
                                preserved_blocks.append(text[i : j + 1])
                                result.append(get_placeholder(idx))
                                i = j + 1
                                break
                        j += 1
                    else:
                        # No closing brace, just command name
                        idx = len(preserved_blocks)
                        preserved_blocks.append(text[i:cmd_end])
                        result.append(get_placeholder(idx))
                        i = cmd_end
                else:
                    # No braces, just command name
                    idx = len(preserved_blocks)
                    preserved_blocks.append(text[i:cmd_end])
                    result.append(get_placeholder(idx))
                    i = cmd_end
            else:
                result.append(text[i])
                i += 1
        else:
            result.append(text[i])
            i += 1

    text = "".join(result)

    # Now escape special characters in the non-preserved parts
    text = text.replace("\\", "\\textbackslash{}")
    text = text.replace("&", "\\&")
    text = text.replace("%", "\\%")
    text = text.replace("#", "\\#")
    text = text.replace("^", "\\textasciicircum{}")
    text = text.replace("_", "\\_")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    text = text.replace("~", "\\textasciitilde{}")

    # Restore preserved blocks in reverse order to avoid conflicts
    for idx in range(len(preserved_blocks) - 1, -1, -1):
        text = text.replace(get_placeholder(idx), preserved_blocks[idx])

    return text


def format_title_for_text(title_raw):
    """Format title for use in text: handle scenario suffixes, then escape, then lowercase first letter."""
    if not title_raw:
        return ""

    import re

    # Remove "for scenario (PhantomName)" pattern if present
    formatted_title = re.sub(r"\s+for scenario\s+\([^)]+\)", "", title_raw)

    # Remove trailing period if present
    formatted_title = formatted_title.rstrip(".")

    # Handle second word capitalization: if second word is capitalized but second letter is lowercase, uncapitalize first letter
    words = formatted_title.split()
    if len(words) >= 2:
        second_word = words[1]
        # Check if second word is capitalized (first letter uppercase)
        if second_word and second_word[0].isupper():
            # Check if second letter exists and is NOT capitalized (lowercase)
            if len(second_word) > 1 and second_word[1].islower():
                # Make first letter lowercase
                words[1] = second_word[0].lower() + second_word[1:]
                formatted_title = " ".join(words)

    # Lowercase first letter BEFORE adding LaTeX commands (simpler)
    # But preserve acronyms (if second char is also uppercase)
    # Skip if title starts with "The" (keep it capitalized)
    if formatted_title and formatted_title[0].isupper() and not formatted_title.startswith("The "):
        # Check if second character is also uppercase (acronym)
        if len(formatted_title) > 1 and formatted_title[1].isupper():
            # Keep both capitals - it's an acronym
            pass
        else:
            # Lowercase the first character
            formatted_title = formatted_title[0].lower() + formatted_title[1:]

    # Replace scenario suffixes in raw title (after lowercasing, before escaping)
    scenario_replacements = {
        " - By Belly": " for the \\textit{By Belly} scenario.",
        " - By Cheek": " for the \\textit{By Cheek} scenario.",
        " - Front Of Eyes": " for the \\textit{Front Of Eyes} scenario.",
    }

    for old_suffix, new_suffix in scenario_replacements.items():
        if formatted_title.endswith(old_suffix):
            formatted_title = formatted_title[: -len(old_suffix)] + new_suffix
            break

    # Remove trailing period if present (after scenario replacement)
    formatted_title = formatted_title.rstrip(".")

    # Now escape LaTeX special characters (but preserve math mode and LaTeX commands)
    formatted_title = escape_latex_preserve_commands(formatted_title)

    return formatted_title


def format_caption_scenarios(caption):
    """Format scenario names in captions with \\textit{}."""
    if not caption:
        return caption

    import re

    # Pattern to match "for the [Scenario Name] scenario"
    # This will match: "for the By Belly scenario", "for the Front Of Eyes scenario", etc.
    pattern = r"for the ([A-Z][a-zA-Z\s]+?) scenario"

    def replace_scenario(match):
        scenario_name = match.group(1).strip()
        return f"for the \\textit{{{scenario_name}}} scenario"

    formatted_caption = re.sub(pattern, replace_scenario, caption)

    return formatted_caption


def get_section_name(plot_type):
    """Get a nice section name from plot type."""
    section_names = {
        "bar": "Bar Charts",
        "boxplot": "Boxplots",
        "bubble": "Bubble Plots",
        "heatmap": "Heatmaps",
        "line": "Line Plots",
        "power": "Power Analysis",
        "spatial": "Spatial Analysis",
        "correlation": "Correlation Analysis",
        "ranking": "Ranking Plots",
        "penetration": "Penetration Depth",
        "tissue_analysis": "Tissue Analysis",
        "cdf": "Cumulative Distribution Functions",
        "outliers": "Outlier Analysis",
    }
    return section_names.get(plot_type, plot_type.replace("_", " ").title())


def get_subsection_name(filename):
    """Generate a subsection name from filename."""
    # Remove extension
    name = filename.replace(".pdf", "")

    # Remove common prefixes (boxplot_, average_, etc.)
    prefixes = ["boxplot_", "average_", "cdf_", "bubble_", "heatmap_", "sar_line_", "pssar10g_line_", "pssar_line_"]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break

    # Handle special cases like "sar_line_individual_brain_by_belly"
    if name.startswith("individual_"):
        name = name.replace("individual_", "Individual ")
    elif name.startswith("line_"):
        name = name.replace("line_", "")

    # Replace underscores with spaces
    name = name.replace("_", " ")

    # Split into words and capitalize appropriately
    words = name.split()
    capitalized = []
    for i, word in enumerate(words):
        word_lower = word.lower()

        # Handle frequency patterns like "1450mhz" -> "1450 MHz", "allmhz" -> "All MHz"
        if word_lower.endswith("mhz"):
            # Extract number if present
            if word_lower[:-3].isdigit():
                capitalized.append(word_lower[:-3] + " MHz")
            elif word_lower == "allmhz":
                capitalized.append("All MHz")
            else:
                # Split if there's a number before mhz
                import re

                match = re.match(r"(\d+)(mhz)", word_lower)
                if match:
                    capitalized.append(match.group(1) + " MHz")
                else:
                    capitalized.append(word.capitalize())
            continue

        # Handle "maxlocal" -> "Max Local"
        if word_lower == "maxlocal":
            capitalized.append("Max Local")
            continue

        # Handle "top20" -> "Top 20"
        if word_lower == "top20":
            capitalized.append("Top 20")
            continue

        # Handle "2d" -> "2D"
        if word_lower == "2d":
            capitalized.append("2D")
            continue

        # Handle units: "mw" -> "mW", "kg" -> "kg"
        if word_lower == "mw":
            capitalized.append("mW")
            continue
        if word_lower == "kg":
            capitalized.append("kg")
            continue

        # Handle common words
        if word_lower in ["by", "of", "for", "the", "vs", "and", "or", "to"]:
            capitalized.append(word_lower)
        elif word_lower == "sar":
            capitalized.append("SAR")
        elif word_lower.startswith("pssar"):
            # Handle psSAR10g variations
            if "10g" in word_lower or word_lower == "pssar10g":
                capitalized.append("psSAR10g")
            elif word_lower == "pssar":
                capitalized.append("psSAR")
            else:
                # Handle cases like "pssar bar" -> "psSAR Bar"
                capitalized.append("psSAR")
        elif word_lower in ["bar", "line"]:
            capitalized.append(word.capitalize())
        else:
            capitalized.append(word.capitalize())

    # Capitalize first word, but skip if it's already a special case (SAR, psSAR, etc.)
    if capitalized:
        first_word = capitalized[0]
        # Don't capitalize if it's already a special acronym/case
        special_cases = ["SAR", "psSAR", "psSAR10g", "mW", "kg", "MHz", "All MHz", "Max Local", "Top 20", "2D"]
        if first_word not in special_cases and not first_word.startswith(("psSAR", "SAR")):
            capitalized[0] = capitalized[0].capitalize()

    result = " ".join(capitalized)

    # Clean up any double spaces
    result = " ".join(result.split())

    return result


def organize_plots(plots_dir):
    """Scan plots directory and organize by section and subsection (plot type)."""
    # Structure: plots_by_section[section][subsection] = [list of plots for each phantom]
    plots_by_section = defaultdict(lambda: defaultdict(list))

    # Find all PDF files
    for pdf_path in plots_dir.rglob("*.pdf"):
        # Skip HTML files that might have .pdf extension
        if pdf_path.suffix != ".pdf":
            continue

        # Get relative path from plots directory
        rel_path = pdf_path.relative_to(plots_dir)

        # Get plot type from directory structure (e.g., thelonious/bar/...)
        parts = rel_path.parts
        if len(parts) < 3:
            continue

        phantom_name = parts[0]  # e.g., 'thelonious', 'eartha'
        section_type = parts[1]  # e.g., 'bar', 'boxplot', etc.
        filename = parts[-1]  # e.g., 'boxplot_SAR_genitals_by_belly.pdf'

        # Get subsection name from filename (same across phantoms)
        subsection_name = get_subsection_name(filename)

        # Read caption file
        txt_path = pdf_path.with_suffix(".txt")
        title, caption = read_caption_file(txt_path)

        # If no title, generate one from filename
        if not title:
            title = pdf_path.stem.replace("_", " ").title()

        # Store plot info
        plots_by_section[section_type][subsection_name].append(
            {
                "pdf_path": rel_path,
                "title": title,
                "caption": caption,
                "filename": filename,
                "phantom_name": phantom_name,
            }
        )

    return plots_by_section


def generate_latex(plots_by_section, study_type="near_field"):
    """Generate LaTeX document."""

    # Sort sections in a logical order
    section_order = [
        "bar",
        "boxplot",
        "line",
        "heatmap",
        "bubble",
        "spatial",
        "correlation",
        "ranking",
        "power",
        "penetration",
        "tissue_analysis",
        "cdf",
        "outliers",
    ]

    # Filter to only sections that have plots
    sections = [s for s in section_order if s in plots_by_section]
    # Add any remaining sections
    for section in sorted(plots_by_section.keys()):
        if section not in sections:
            sections.append(section)

    # Format study type for title
    study_type_formatted = study_type.replace("_", "-").title()

    latex_content = f"""\\documentclass{{IEEEtran}}
\\usepackage{{graphicx}}
\\usepackage{{booktabs}}
\\usepackage{{float}}
\\usepackage{{alphalph}}

% Fix subsection counter to use extended alphabetic (aa, ab, ... after z) instead of \\Alpha (limited to 26)
\\makeatletter
\\@addtoreset{{subsection}}{{section}}
\\def\\thesubsection{{\\alphalph{{\\value{{subsection}}}}}}
\\def\\thesubsectiondis{{\\thesection.\\alphalph{{\\value{{subsection}}}}}}
\\makeatother

\\usepackage{{hyperref}}

\\title{{{study_type_formatted} Analysis Results}}
\\author{{Robin Wydaeghe}}
\\date{{\\today}}

\\begin{{document}}

\\maketitle

\\tableofcontents
\\newpage

"""

    # Generate sections
    figure_counter = 1

    for section_idx, section in enumerate(sections):
        section_name = get_section_name(section)
        latex_content += f"\\section{{{section_name}}}\n\n"

        # Counter for figures within this section
        section_figure_counter = 0

        # Get subsections for this section
        subsections = plots_by_section[section]

        # Sort subsections by name
        for subsection_name in sorted(subsections.keys()):
            latex_content += f"\\subsection{{{subsection_name}}}\n\n"

            # Get all plots for this subsection (across all phantoms)
            plots = subsections[subsection_name]

            # Sort by phantom name for consistent ordering
            plots = sorted(plots, key=lambda x: x["phantom_name"])

            for plot in plots:
                # Path relative to LaTeX file - reference plots directly from goliat/plots/
                pdf_rel_path = plot["pdf_path"].as_posix()  # Use forward slashes for LaTeX
                # Use relative path from paper/{study_type}/pure_results/ to plots/{study_type}/
                # Need 3 levels up: pure_results -> {study_type} -> paper -> goliat/
                pdf_rel_path = f"../../../plots/{study_type}/{pdf_rel_path}"
                title_raw = plot["title"]
                title_formatted = format_title_for_text(title_raw)
                title_escaped = escape_latex(title_raw)  # For caption
                # Format scenario names in caption before escaping LaTeX
                # Use escape_latex_preserve_commands to preserve \\textit{} commands
                caption_raw = plot["caption"]
                caption_formatted = format_caption_scenarios(caption_raw)
                caption = escape_latex_preserve_commands(caption_formatted)

                # Use caption if available, otherwise use title
                if not caption:
                    caption = title_escaped if title_escaped else "Figure"

                # Use section-based label format: fig:section_idx_figure_counter
                section_figure_counter += 1
                label = f"fig:{section_idx}_{section_figure_counter}"

                # Write text with reference before figure
                if title_formatted:
                    latex_content += f"{title_formatted} can be found in Figure~\\ref{{{label}}}. \\\\\\\\\n\n"

                latex_content += "\\begin{figure}[H]\n"
                latex_content += "\\centering\n"
                latex_content += f"\\includegraphics[width=\\columnwidth]{{{pdf_rel_path}}}\n"
                latex_content += f"\\caption{{{caption}}}\n"
                latex_content += f"\\label{{{label}}}\n"
                latex_content += "\\end{figure}\n\n"

                figure_counter += 1

        latex_content += "\\newpage\n\n"

    latex_content += "\\end{document}\n"

    return latex_content


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate LaTeX paper from analysis plots.")
    parser.add_argument(
        "--study-type",
        type=str,
        default="near_field",
        choices=["near_field", "far_field"],
        help="Study type: near_field or far_field (default: near_field)",
    )
    args = parser.parse_args()

    study_type = args.study_type
    base_dir = Path(get_base_dir())

    # Paths relative to base_dir - use study_type for paths
    paper_dir = base_dir / "paper" / study_type / "pure_results"
    plots_source = base_dir / "plots" / study_type
    ieee_cls_source = base_dir / "paper" / "IEEEtran.cls"
    ieee_cls_dest = paper_dir / "IEEEtran.cls"
    output_tex = paper_dir / "results.tex"

    # Ensure paper directory exists
    paper_dir.mkdir(parents=True, exist_ok=True)

    # Check if plots directory exists
    if not plots_source.exists():
        print(f"Warning: Source plots directory not found: {plots_source}")
        return

    print(f"Scanning {study_type} plots directory...")
    plots_by_section = organize_plots(plots_source)

    total_plots = sum(sum(len(plots) for plots in subsections.values()) for subsections in plots_by_section.values())
    total_subsections = sum(len(subsections) for subsections in plots_by_section.values())
    print(f"Found {total_plots} plots in {len(plots_by_section)} sections with {total_subsections} subsections")

    # Copy IEEEtran.cls
    if ieee_cls_source.exists():
        print("Copying IEEEtran.cls...")
        shutil.copy2(ieee_cls_source, ieee_cls_dest)
    else:
        print(f"Warning: IEEEtran.cls source not found: {ieee_cls_source}")

    # Generate LaTeX
    print("Generating LaTeX file...")
    latex_content = generate_latex(plots_by_section, study_type)

    # Write to file
    with open(output_tex, "w", encoding="utf-8") as f:
        f.write(latex_content)

    print(f"Generated: {output_tex}")
    total_figures = sum(sum(len(plots) for plots in subsections.values()) for subsections in plots_by_section.values())
    print(f"Total figures: {total_figures}")


if __name__ == "__main__":
    main()
