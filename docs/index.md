# GOLIAT Project Documentation

<div class="grid cards" markdown>

-   :material-clock-fast:{ .lg .middle } __Quick Start__

    ---

    Get up and running with GOLIAT in minutes

    [:octicons-arrow-right-24: Installation Guide](README.md)

-   :material-cog:{ .lg .middle } __Configuration__

    ---

    Learn how to configure your simulations

    [:octicons-arrow-right-24: Configuration Guide](configs/documentation.md)

-   :material-api:{ .lg .middle } __API Reference__

    ---

    Complete API documentation for all modules

    [:octicons-arrow-right-24: API Docs](api.md)

-   :material-chart-timeline:{ .lg .middle } __Architecture__

    ---

    Understand the system design and workflow

    [:octicons-arrow-right-24: Architecture Overview](architecture_overview.md)

</div>

## Overview

GOLIAT is a robust and automated Python framework for conducting both **near-field** and **far-field** dosimetric assessments using the Sim4Life simulation platform.

The framework is designed to be:

- **Modular** - Clean separation of concerns with well-defined components
- **Scalable** - Handle large simulation matrices efficiently
- **Reproducible** - Consistent results across different runs
- **User-friendly** - Real-time GUI with progress tracking

## Key Features

### 🎯 Near-Field Studies
Conduct SAR simulations with device antennas placed close to phantom models, supporting various:

- Device placements and orientations
- Multiple frequency bands
- Child and adult phantom models
- Automated antenna positioning

### 🌐 Far-Field Studies
Perform whole-body exposure simulations from incident plane waves:

- Multiple incident directions
- Various polarizations
- Environmental and auto-induced scenarios
- Comprehensive SAR analysis

### 🚀 Cloud Computing
Scale your simulations with integrated oSPARC support:

- Batch job submission
- Automated result downloading
- Real-time progress monitoring
- Parallel execution

### 📊 Advanced Analysis
Comprehensive post-processing capabilities:

- Tissue-specific SAR calculations
- Whole-body and organ-level metrics
- Automated report generation
- Statistical analysis and visualization

## Quick Links

- [Installation & Setup](README.md)
- [API Reference](api.md)
- [Architecture Overview](architecture_overview.md)
- [UML Diagrams](uml.md)
- [GitHub Repository](https://github.com/rwydaegh/goliat)

## Support

For questions, issues, or contributions, please visit the [GitHub repository](https://github.com/rwydaegh/goliat).