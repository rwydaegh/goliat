# Strategic Project Roadmap

This document outlines the strategic, theme-based development roadmap for the GOLIAT near-field simulation framework.

## Guiding Principles

*   **Modularity & Maintainability**: The codebase should be easy to understand, modify, and extend.
*   **Reproducibility & Accuracy**: The scientific results must be accurate and reproducible.
*   **Automation & Efficiency**: The workflow should be as automated and efficient as possible to handle large-scale simulation campaigns.

## Development Phases & Themes

```mermaid
gantt
    title Improved Project Roadmap
    dateFormat  YYYY-Q
    axisFormat %Y-Q%
    
    section "Phase 1: Foundational Robustness & Scalability"
    Codebase Refactoring          :done,    crit, des1, 2025-Q3, 2025-Q3
    Full Campaign Automation      :active,  crit, des2, 2025-Q3, 2025-Q4
    Full 'Eartha' Phantom Support :         crit, des3, 2025-Q4, 2025-Q4

    section "Phase 2: Data Integrity & Analysis"
    Comprehensive Results Extraction : crit, des4, 2025-Q4, 2026-Q1
    Power Normalization              : crit, des5, 2026-Q1, 2026-Q1
    Data Aggregation & Visualization :      des6, 2026-Q1, 2026-Q2

    section "Phase 3: Developer Experience & Automation"
    Version Control & CI/CD Setup : des7, 2026-Q2, 2026-Q2
    Enhanced Documentation        : des8, 2026-Q2, 2026-Q3
```

---

### **Phase 1: Foundational Robustness & Scalability**

*Goal: Solidify the core architecture to ensure it is robust, scalable, and ready for large-scale simulation campaigns.*

*   **Task 1: Codebase Refactoring (Completed)**
    *   **Description**: Refactor the `NearFieldProject` "God Class" into smaller, specialized components to improve modularity and maintainability, as detailed in `docs/REFACTORING_PLAN.md`.
    *   **Status**: Done.

*   **Task 2: Full Campaign Automation**
    *   **Description**: Fully implement and test the `NearFieldStudy` class to reliably iterate through all phantoms, frequencies, and placements defined in the configuration files. This includes adding robust progress tracking and error handling for individual simulation failures.
    *   **Status**: In Progress.

*   **Task 3: Full 'Eartha' Phantom Support**
    *   **Description**: Integrate the Eartha phantom into the simulation workflow. This involves adding its model file, creating a complete configuration profile in `phantoms_config.json`, and validating the end-to-end simulation process.
    *   **Status**: Not Started.

---

### **Phase 2: Data Integrity & Analysis**

*Goal: Ensure all required scientific outputs are generated accurately and provide tools for comprehensive analysis.*

*   **Task 4: Comprehensive Results Extraction**
    *   **Description**: Enhance the `ResultsExtractor` to parse all required SAR metrics as specified in `context/what we need.md`, including whole-body, head, and trunk SAR, plus psSAR10g for skin, eyes, and brain.
    *   **Status**: Not Started.

*   **Task 5: Power Normalization**
    *   **Description**: Implement the final power normalization calculation to report all SAR results for a normalized applied power that induces a peak spatial-average SAR (psSAR10g) of 1 W/kg.
    *   **Status**: Not Started.

*   **Task 6: Data Aggregation & Visualization**
    *   **Description**: Develop Python scripts (e.g., using Pandas and Matplotlib/Seaborn) to aggregate the results from all individual simulation JSON files into a single, master dataset. Create functions to generate plots for analysis and comparison.
    *   **Status**: Not Started.

---

### **Phase 3: Developer Experience & Automation**

*Goal: Streamline the development and deployment process using modern best practices.*

*   **Task 7: Version Control & CI/CD Setup**
    *   **Description**: Initialize a Git repository, push the project to a remote host (e.g., GitHub), and set up a basic Continuous Integration (CI) pipeline. The CI pipeline should run linters and code formatters automatically.
    *   **Status**: Not Started.

*   **Task 8: Enhanced Documentation**
    *   **Description**: Improve the project documentation by adding API-level docstrings to all classes and methods. Create a `CONTRIBUTING.md` file to guide future development.
    *   **Status**: Not Started.