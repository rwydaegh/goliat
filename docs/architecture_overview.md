# Architecture Overview

This document provides a high-level overview of the GOLIAT project's architecture.

## Workflow

The application follows a clear, modular workflow from configuration to results. The core logic is orchestrated by **Study** classes, which manage the entire simulation lifecycle.

```mermaid
graph TD
    A[Start] --> B{Load Config}
    B --> C{Select Study Type}
    C --> D[Near-Field Study]
    C --> E[Far-Field Study]
    D --> F{Run Simulation}
    E --> F
    F --> G[Extract Results]
    G --> H[End]
    
    style A fill:#4CAF50
    style H fill:#4CAF50
    style D fill:#2196F3
    style E fill:#2196F3
    style F fill:#FF9800
    style G fill:#9C27B0
```

## System Architecture

```mermaid
graph TB
    subgraph "User Interface Layer"
        GUI[GUI Manager<br/>PySide6]
        CLI[Command Line]
    end
    
    subgraph "Orchestration Layer"
        Study[Study Classes<br/>NearFieldStudy / FarFieldStudy]
        Config[Configuration Manager]
        Profiler[Profiler & Progress Tracking]
    end
    
    subgraph "Core Processing Layer"
        PM[Project Manager]
        Setup[Setup Classes<br/>Scene Building]
        Runner[Simulation Runner]
        Extractor[Results Extractor]
    end
    
    subgraph "External Services"
        S4L[Sim4Life Engine]
        oSPARC[oSPARC Cloud]
    end
    
    GUI --> Study
    CLI --> Study
    Study --> Config
    Study --> Profiler
    Study --> PM
    Study --> Setup
    Study --> Runner
    Study --> Extractor
    Runner --> S4L
    Runner --> oSPARC
    Setup --> S4L
    Extractor --> S4L
    
    style GUI fill:#E1BEE7
    style Study fill:#BBDEFB
    style Setup fill:#C5E1A5
    style Runner fill:#FFE082
    style Extractor fill:#FFCCBC
```

## Key Components

### Entry Points

**`run_study.py`**
:   The main entry point of the application. It handles the GUI and launches the study in a separate process to maintain UI responsiveness.

**`run_study_no_gui.py`**
:   Command-line interface for headless execution, ideal for batch processing and automation.

### Core Classes

**`Config`**
:   Handles loading and validation of configuration files with hierarchical inheritance. Supports extending base configurations for easy customization.

**`NearFieldStudy` / `FarFieldStudy`**
:   Orchestrate the entire simulation workflow for their respective study types. These classes coordinate all phases: setup, execution, and post-processing.

**`ProjectManager`**
:   Manages the Sim4Life project file (`.smash`). Includes validation checks to prevent corruption and handles file locking on Windows.

### Setup Components

**`NearFieldSetup` / `FarFieldSetup`**
:   Build the simulation scene by:
    
    - Importing and positioning phantoms
    - Placing antennas or configuring plane waves
    - Setting up materials and boundary conditions
    - Configuring solver parameters

**`PhantomSetup`**
:   Handles phantom model loading and validation.

**`PlacementSetup`**
:   Manages antenna positioning relative to phantom models with precise distance and orientation control.

**`MaterialSetup`**
:   Assigns material properties to all entities in the simulation.

**`GriddingSetup`**
:   Configures spatial discretization with main grids and subgrids for accurate field computation.

**`BoundarySetup`**
:   Defines boundary conditions for the simulation domain.

**`SourceSetup`**
:   Configures electromagnetic sources (antennas or plane waves).

### Execution Components

**`SimulationRunner`**
:   Executes simulations with support for:
    
    - Local manual execution (generates input files)
    - Local automated execution (runs iSolve directly)
    - Cloud execution (submits to oSPARC)

**`ResultsExtractor`**
:   Performs post-processing and data extraction:
    
    - SAR field extraction and statistics
    - Power balance analysis
    - Tissue-specific metrics
    - Report generation

### Analysis Components

**`Analyzer`**
:   Processes extracted results and generates comprehensive reports.

**`Plotter`**
:   Creates visualizations including heatmaps, bar charts, and distribution plots.

### UI Components

**`GuiManager`**
:   Provides a real-time progress window using PySide6 with:
    
    - Live progress bars
    - Status updates
    - ETA calculations
    - System tray integration

**`Profiler`**
:   Tracks execution time and provides increasingly accurate time estimates based on historical data.

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant GUI
    participant Study
    participant Setup
    participant Runner
    participant Extractor
    participant Files
    
    User->>GUI: Start Study
    GUI->>Study: Initialize
    Study->>Setup: Configure Scene
    Setup->>Files: Create .smash
    Study->>Runner: Execute Simulation
    Runner->>Files: Generate Input (.h5)
    Runner->>Runner: Run Solver
    Runner->>Files: Write Results
    Study->>Extractor: Process Results
    Extractor->>Files: Read Output
    Extractor->>Files: Save Reports
    Study->>GUI: Update Progress
    GUI->>User: Show Completion
```

## Configuration Hierarchy

GOLIAT uses a hierarchical JSON configuration system that prevents duplication:

```mermaid
graph TD
    base[base_config.json<br/>Common Settings]
    nf[near_field_config.json<br/>Overrides & Specifics]
    ff[far_field_config.json<br/>Overrides & Specifics]
    
    base --> nf
    base --> ff
    
    style base fill:#4CAF50
    style nf fill:#2196F3
    style ff fill:#2196F3
```

This allows you to:

- Define common settings once in `base_config.json`
- Override specific parameters in study-specific configs
- Maintain multiple configurations easily

For more detailed information, please refer to the [API Reference](api.md).