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

## Component Interactions

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

## Key Components

### Entry Points

**`run_study.py`**:
:   The main entry point. Launches GUI and study process.

**`run_study_no_gui.py`**:
:   Headless CLI for batch/automation.

### Core Classes

**`Config`**:
:   Loads JSON configs with inheritance.

**`NearFieldStudy` / `FarFieldStudy`**:
:   Orchestrate workflow: Loop over parameters, call setups/runner/extractor.

**`ProjectManager`**:
:   Manages .smash files (create/open/save/close, lock handling).

### Setup Components

**`NearFieldSetup` / `FarFieldSetup`**:
:   Build scene: Phantoms, antennas/sources, materials, gridding, boundaries.

**`PhantomSetup`**:
:   Loads voxel models.

**`PlacementSetup`**:
:   Positions antennas.

**`MaterialSetup`**:
:   Assigns tissue/material properties.

**`GriddingSetup`**:
:   Sets grid resolution.

**`BoundarySetup`**:
:   Configures PML boundaries.

**`SourceSetup`**:
:   Adds excitations/sensors.

### Execution Components

**`SimulationRunner`**:
:   Runs iSolve (local) or submits to oSPARC.

**`ResultsExtractor`**:
:   Extracts SAR, power balance, point sensors.

### Analysis Components

**`Analyzer`**:
:   Aggregates results using strategies (near/far-field).

**`Plotter`**:
:   Generates heatmaps, bars, boxplots.

### UI Components

**`GuiManager`**:
:   Progress window with multiprocessing queue.

**`Profiler`**:
:   Estimates ETA based on phase weights.

## Configuration Hierarchy

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

For detailed information, refer to the [API Reference](api.md).