# Welcome to GOLIAT

GOLIAT is an automated Python framework for near-field and far-field dosimetric assessments using the Sim4Life simulation platform. It streamlines EMF exposure simulations for research and compliance.

## Table of Contents

<div class="grid cards" markdown>

-   :material-rocket-launch-outline:{ .lg .middle } **Quick Start**

    ---

    Run your first simulation in minutes. No manual setup required.

    [:octicons-arrow-right-24: Get Started](user_guide/quick_start.md)

-   :material-book-open-page-variant-outline:{ .lg .middle } **User Guide**

    ---

    Understand near-field and far-field workflows. Step-by-step explanations with practical insights.

    [:octicons-arrow-right-24: Read Guide](user_guide/user_guide.md)

-   :material-school-outline:{ .lg .middle } **Tutorials**

    ---

    Interactive notebooks from basics to cloud execution. Learn by doing.

    [:octicons-arrow-right-24: View Tutorials](tutorials/overview.md)

-   :material-sitemap-outline:{ .lg .middle } **Technical Guide**

    ---

    Architecture, components, and system design. For developers extending or maintaining GOLIAT.

    [:octicons-arrow-right-24: Technical Guide](developer_guide/technical_guide.md)

-   :material-lightning-bolt-outline:{ .lg .middle } **Advanced Features**

    ---

    GUI architecture, profiling, caching, phantom rotation. Advanced capabilities explained.

    [:octicons-arrow-right-24: Advanced Features](developer_guide/advanced_features.md)

-   :material-cog-outline:{ .lg .middle } **Configuration**

    ---

    All JSON configuration parameters with examples. Flexible and powerful.

    [:octicons-arrow-right-24: Configure](developer_guide/configuration.md)

-   :material-cloud-upload-outline:{ .lg .middle } **oSPARC**

    ---

    Cloud batch execution via oSPARC platform. Scale to hundreds of simulations with true parallel GPU execution.

    [:octicons-arrow-right-24: oSPARC Guide](cloud/osparc.md)

-   :material-view-dashboard-outline:{ .lg .middle } **Monitoring Dashboard**

    ---

    Web-based interface for monitoring distributed studies across multiple workers. Track progress, view logs, coordinate super studies.

    [:octicons-arrow-right-24: Monitoring Guide](cloud/monitoring.md)

-   :material-cloud-outline:{ .lg .middle } **Cloud Setup**

    ---

    Deploy GPU instances and run simulations in the cloud. Automated setup included.

    [:octicons-arrow-right-24: Cloud Guide](cloud/cloud_setup.md)

-   :material-palette-outline:{ .lg .middle } **Coloring Rules**

    ---

    Terminal output coloring guidelines. Makes logs easier to scan and debug.

    [:octicons-arrow-right-24: Coloring Rules](developer_guide/coloring_rules.md)

-   :material-graph-outline:{ .lg .middle } **UML**

    ---

    Class relationships and package structure. Visual overview of the codebase.

    [:octicons-arrow-right-24: View UML](developer_guide/uml.md)

-   :material-help-circle-outline:{ .lg .middle } **Troubleshooting**

    ---

    Common issues and solutions. Sim4Life setup, execution, and configuration.

    [:octicons-arrow-right-24: Troubleshooting](troubleshooting.md)

-   :material-feature-search-outline:{ .lg .middle } **Full List of Features**

    ---

    Every feature organized by category. See what GOLIAT can do.

    [:octicons-arrow-right-24: View Features](reference/full_features_list.md)

-   :material-api:{ .lg .middle } **API Reference**

    ---

    All classes, methods, and functions. Generated from code documentation.

    [:octicons-arrow-right-24: API Docs](reference/api_reference.md)

-   :material-information-outline:{ .lg .middle } **Project Info**

    ---

    Research project background, funding, partners, and consortium information.

    [:octicons-arrow-right-24: Project Info](project_info.md)

</div>

## Overview

GOLIAT automates dosimetric assessments for the GOLIAT project, calculating SAR in digital human phantoms from device or environmental EMF exposure. Key features:

- Modular scene building (phantoms, antennas, plane waves).
- Local or cloud execution (iSolve/oSPARC).
- Results extraction and analysis (SAR metrics, plots).
- GUI for progress tracking.
- Automatic disk space management for serial workflows.

Start with the [Quick Start](user_guide/quick_start.md) to run your first simulation.

## Why GOLIAT?

- **Efficiency**: Handles setup, runs, and analysis in one tool.
- **Reproducible**: Config-driven for consistent results.
- **Scalable**: Local parallel or cloud batching for large studies.
- **Accessible**: Plain-language docs for newcomers.

For issues, see [Troubleshooting](troubleshooting.md). Contribute via [Technical Guide](developer_guide/technical_guide.md).

For a complete list of all available features, see the [Full List of Features](reference/full_features_list.md).

---