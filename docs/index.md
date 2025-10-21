# Welcome to GOLIAT

GOLIAT is an automated Python framework for near-field and far-field dosimetric assessments using the Sim4Life simulation platform. It streamlines EMF exposure simulations for research and compliance.

<div class="grid cards" markdown>

-   :material-rocket-launch-outline:{ .lg .middle } **Quick Start**

    ---

    Get running in minutes with installation and your first simulation.

    [:octicons-arrow-right-24: Get Started](quick_start.md)

-   :material-book-open-page-variant-outline:{ .lg .middle } **User Guide**

    ---

    Understand workflows for near-field and far-field studies.

    [:octicons-arrow-right-24: Read Guide](user_guide.md)

-   :material-school-outline:{ .lg .middle } **Tutorials**

    ---

    Hands-on examples from basic runs to advanced batching.

    [:octicons-arrow-right-24: View Tutorials](tutorials/basic.md)

-   :material-cog-outline:{ .lg .middle } **Configuration**

    ---

    Customize simulations with JSON configs.

    [:octicons-arrow-right-24: Configure](configuration.md)

-   :material-api:{ .lg .middle } **API Reference**

    ---

    Detailed docs for classes and functions.

    [:octicons-arrow-right-24: API Docs](api_reference.md)

-   :material-sitemap-outline:{ .lg .middle } **Technical Guide**

    ---

    Overview of the system design.

    [:octicons-arrow-right-24: Technical Guide](technical_guide.md)

</div>

## Overview

GOLIAT automates dosimetric assessments for the GOLIAT project, calculating SAR in digital human phantoms from device or environmental EMF exposure. Key features:

- Modular scene building (phantoms, antennas, plane waves).
- Local or cloud execution (iSolve/oSPARC).
- Results extraction and analysis (SAR metrics, plots).
- GUI for progress tracking.
- Automatic disk space management for serial workflows.

Start with the [Quick Start](quick_start.md) to run your first simulation.

## Why GOLIAT?

- **Efficiency**: Handles setup, runs, and analysis in one tool.
- **Reproducible**: Config-driven for consistent results.
- **Scalable**: Local parallel or cloud batching for large studies.
- **Accessible**: Plain-language docs for newcomers.

For issues, see [Troubleshooting](troubleshooting.md). Contribute via [Developer Guide](developer_guide.md).

---