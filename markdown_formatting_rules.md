# Python-Markdown Formatting Rules for GOLIAT Documentation

This document outlines the essential markdown formatting rules that must be followed when writing or editing GOLIAT documentation. These rules are specific to how **Python-Markdown** (used by MkDocs) parses nested lists and code blocks.

## Table of Contents

- [Nested Numbered Lists](#1-nested-numbered-lists-within-bullet-points)
- [Code Blocks in Lists](#2-code-blocks-within-list-items)
- [Blank Lines Between List Items](#3-blank-lines-between-distinct-list-items)
- [Consistent Bullet Style](#4-consistent-bullet-style)
- [Top-Level Lists After Paragraphs](#5-top-level-list-items-after-paragraphs)
- [API Reference Entries](#6-api-reference-entries-and-similar)
- [Quick Reference Checklist](#quick-reference-checklist)

---

## 1. Nested Numbered Lists Within Bullet Points

**Rule**: When a bullet point ends with text (like `- **Solution**:`), the nested numbered list must be **directly indented 4 spaces** from the bullet marker, with **NO blank line** between the parent text and the nested list.

**✅ Correct:**
```markdown
- **Solution**:
  1. First step
  2. Second step
  3. Two steps later
```

**❌ Incorrect:**
```markdown
- **Solution**:

  1. First step  ← Blank line causes rendering issues
  2. Second step
```

**Why**: Python-Markdown requires direct indentation without an intervening blank line. A blank line breaks the list nesting and can cause numbered lists to render as alphabetical lists (a, b, c instead of 1, 2, 3).

---

## 2. Code Blocks Within List Items

**Rule**: Code blocks within list items (whether bullet or numbered) must be indented **8 spaces total** (4 spaces for the list item + 4 spaces for the code block).

**✅ For numbered lists:**
```markdown
1. **Some step**:

        ```json
        {
          "setting": "value"
        }
        ```

2. Next step...
```

**✅ For bullet lists:**
```markdown
- **Solution**:
  1. First step
  2. Edit file:

        ```bash
        export PATH="/path/to/tool:$PATH"
        ```

  3. Next step
```

**❌ Incorrect:**
```markdown
- **Solution**:
  1. First step
  2. Edit file:

   ```bash  ← Only 3 spaces, will be incorrectly embedded in list
   export PATH="/path/to/tool:$PATH"
   ```
```

**Why**: The code block is nested two levels deep (list item → code block), so it needs 8 spaces of indentation.

---

## 3. Blank Lines Between Distinct List Items

**Rule**: Add blank lines between **separate top-level list items** to prevent them from merging.

**✅ Correct:**
```markdown
- **First item**:
  1. Step one
  2. Step two

- **Second item**:
  1. Step one
  2. Step two
```

**❌ Incorrect:**
```markdown
- **First item**:
  1. Step one
  2. Step two
- **Second item**:  ← Missing blank line can cause merging
  1. Step one
```

**Why**: Blank lines signal the end of one list item and the start of another.

---

## 4. Consistent Bullet Style

**Rule**: Use `-` (hyphen) for **all** bullet points, not `*` (asterisk).

**✅ Correct:**
```markdown
- First item
- Second item
- Third item
```

**❌ Incorrect:**
```markdown
* First item
- Second item  ← Mixed styles cause inconsistency
* Third item
```

**Why**: Consistency improves readability and prevents parsing ambiguity.

---

## 5. Top-Level List Items After Paragraphs

**Rule**: When a paragraph is followed by list items that should be top-level (not nested), ensure there's a blank line before the list.

**✅ Correct:**
```markdown
This is a paragraph explaining something.

- First item
- Second item
```

**❌ Incorrect:**
```markdown
This is a paragraph explaining something.
- First item  ← Missing blank line can cause formatting issues
- Second item
```

**Why**: Without a blank line, Python-Markdown may interpret the list as part of the paragraph.

---

## 6. API Reference Entries and Similar

**Rule**: For entries like "API Reference:" that should be top-level bullets, ensure there's a blank line before them to prevent them from being interpreted as nested content.

**✅ Correct:**
```markdown
- **Some interesting methods**:
  - `method1()`: Description
  - `method2()`: Description

- **API Reference**: [link](url)
```

**❌ Incorrect:**
```markdown
- **Some interesting methods**:
  - `method1()`: Description
  - `method2()`: Description
- **API Reference**: [link](url)  ← Missing blank line causes incorrect indentation
```

**Why**: Without a blank line, Python-Markdown may interpret "API Reference" as a nested item rather than a top-level list item.

---

## Quick Reference Checklist

When writing or editing markdown documentation, check:

- [ ] Nested numbered lists have **4-space indentation** and **NO blank line** before them
- [ ] Code blocks within lists are indented **8 spaces** (not 3 or 4)
- [ ] Separate list items have **blank lines** between them
- [ ] All bullets use `-` (not `*`)
- [ ] Top-level lists after paragraphs have a **blank line before** them
- [ ] "API Reference:" and similar entries have **blank lines before** them

---

## Why These Rules Matter

GOLIAT uses **MkDocs with Python-Markdown**, which has strict parsing rules. Not following these guidelines can cause:

- ✅ Numbered lists rendering as alphabetical lists (a, b, c instead of 1, 2, 3)
- ✅ Code blocks being embedded incorrectly within lists
- ✅ List items merging when they shouldn't
- ✅ Incorrect indentation for reference entries

Following these rules ensures consistent, correct rendering across the entire documentation site.

---

## Testing Your Changes

After making documentation changes:

1. Build the docs locally: `mkdocs serve`
2. Check rendered output in your browser
3. Verify nested lists render correctly (numbers, not letters)
4. Verify code blocks are properly formatted
5. Check indentation is correct throughout

## Examples from GOLIAT Documentation

### Example 1: Troubleshooting Entry

```markdown
- **Solution**:
  1. Locate Sim4Life installation (default: C:\Program Files\Sim4Life_8.2.0).
  2. Edit `.bashrc` in project root with your path:

        ```
        export PATH="/path/to/Sim4Life/Python:$PATH"
        ```

  3. Source: `source .bashrc`.
  4. Verify: `python -c "import s4l_v1; print('OK')"` - should print "OK".
```

### Example 2: User Guide Workflow Steps

```markdown
-   **Key Steps**:
    1.  **Configuration**: Set `"study_type": "near_field"` and define specific `placement_scenarios`.
    2.  **Scene Setup**: Involves importing a detailed CAD model of the device antenna.
    3.  **Simulation Run**: Typically uses a harmonic excitation (single frequency).
    4.  **Results Analysis**: Concentrates on localized SAR values and peak spatial-average SAR.

-   **Duration**: This workflow typically takes 15-30 minutes per simulation.
```

Notice: The numbered list is indented 4 spaces with no blank line after `-   **Key Steps**:`, and a blank line separates it from the next bullet point.

---

## Additional Resources

- [Python-Markdown Documentation](https://python-markdown.github.io/)
- [MkDocs Material Documentation](https://squidfunk.github.io/mkdocs-material/)
- [CommonMark Spec](https://commonmark.org/) (for general markdown reference)
