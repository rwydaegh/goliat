# Proposal: Expanding the Framework for Far-Field Simulations

This document outlines a strategic plan to extend the existing near-field dosimetric assessment framework to incorporate far-field exposure simulations. The goal is to create a unified, modular, and scalable architecture that can handle both near-field and far-field studies efficiently, while preparing for future extensions.

## 1. Analysis & Motivation

The current framework is highly optimized for near-field scenarios, with classes like [`src/study.py:10`](src/study.py:10) and setups in [`src/simulation_setup.py:10`](src/simulation_setup.py:10) being tightly coupled to antenna placements near a phantom.

The requirements for far-field, as detailed in [`context/GOLIAT_PartB_20210920_3rdSubmission_final.pdf`](context/GOLIAT_PartB_20210920_3rdSubmission_final.pdf:1) and [`context/Far-field_GOLIAT.pdf`](context/Far-field_GOLIAT.pdf:1), are fundamentally different:
- **Source:** Instead of a near-field antenna, the exposure source is a set of incident plane waves.
- **Scenarios:** It involves two distinct scenarios:
    1.  **Environmental:** Simulating a set of 12 plane waves from cardinal directions.
    2.  **Auto-Induced:** Simulating a large set of plane waves from many angles to model 5G beamforming, which requires specific post-processing (MRT beamforming) to calculate the final exposure.

A simple adaptation of the existing code is not feasible. A more fundamental restructuring is needed to avoid code duplication and ensure maintainability.

## 2. Proposed Project Restructuring

I propose refactoring the project into a more generic structure that abstracts the common simulation steps and separates the domain-specific logic for near-field and far-field.

### 2.1. New Directory Structure

Here is the proposed high-level directory structure:

```
.
├── configs/
│   ├── near_field_config.json      # Configuration for near-field studies
│   └── far_field_config.json       # Configuration for far-field studies
├── data/
│   ├── antennas/
│   └── phantoms/
├── results/
│   ├── near_field/                 # Existing results will be moved here
│   └── far_field/                  # New directory for far-field results
├── plots/
│   ├── near_field/                 # Existing plots will be moved here
│   └── far_field/                  # New directory for far-field plots
├── src/
│   ├── studies/
│   │   ├── __init__.py
│   │   ├── base_study.py           # Abstract base class for studies
│   │   ├── near_field_study.py     # The logic from the current study.py
│   │   └── far_field_study.py      # New class for far-field campaigns
│   ├── setups/
│   │   ├── __init__.py
│   │   ├── base_setup.py           # Abstract base class for setups
│   │   ├── near_field_setup.py     # The logic from the current simulation_setup.py
│   │   └── far_field_setup.py      # New class for far-field plane wave setup
│   ├── analysis/
│   ├── __init__.py
│   ├── config.py                 # Will be adapted to load from the new configs/ dir
│   ├── project_manager.py        # Reusable
│   ├── results_extractor.py      # To be refactored for different result types
│   ├── simulation_runner.py      # Reusable
│   └── utils.py                  # Reusable
├── run_study.py                      # Main entry point, will select study type (near/far)
└── ... (other files)
```

### 2.2. Key Architectural Changes

- **Configuration:** The main [`config.json`](config.json:1) will be split. This separates the distinct parameters for each study type, making configuration cleaner and more explicit. The main `run_study.py` script would take an argument to specify which configuration to use.
- **Results & Plots:** The `results` and `plots` directories will be organized by study type. I will handle moving the existing near-field results into the `results/near-field/` subdirectory.
- **Core Logic (`src`):**
    - **`studies` directory:** A new `studies` directory will contain a `BaseStudy` class defining a common interface for running a simulation campaign. The existing `NearFieldStudy` logic will be moved into `near_field_study.py`, and a new `FarFieldStudy` class will be created.
    - **`setups` directory:** Similarly, a `BaseSetup` will define the interface for preparing a Sim4Life scene. The existing `SimulationSetup` will become `near_field_setup.py`, and a new `far_field_setup.py` will handle the plane wave source definitions.
- **Results Extractor:** The [`src/results_extractor.py`](src/results_extractor.py:1) will be refactored. It will need to handle different types of outputs (e.g., single antenna simulation vs. combining results from multiple plane wave simulations). We can use a factory pattern or strategy pattern here to select the correct extraction logic based on the study type.

## 3. Far-Field Simulation Strategy

The implementation of the far-field study will follow the new architecture and the requirements from the GOLIAT documents.

### 3.1. Configuration (`configs/far_field_config.json`)

This new file will define parameters specific to the far-field study, including:
- The list of frequencies (450 MHz to 26 GHz).
- Phantom names to be used.
- Plane wave simulation settings (e.g., angular step for auto-induced scenario).

### 3.2. Setup (`src/setups/far_field_setup.py`)

This new module will be responsible for:
- Loading the specified phantom.
- Creating the FDTD simulation entity in Sim4Life.
- **Crucially, instead of placing an antenna, it will define the plane wave sources.**
- For the **environmental** scenario, it will set up a simulation for each of the 12 specified incident waves.
- For the **auto-induced** scenario, it will set up simulations for a grid of incident plane waves (e.g., every 5 degrees in azimuth and elevation, for two polarizations), as described in [`context/Far-field_GOLIAT.pdf`](context/Far-field_GOLIAT.pdf:1).

### 3.3. Execution (`src/studies/far_field_study.py`)

The `FarFieldStudy` class will orchestrate the campaign:
- It will read the `far_field_config.json`.
- It will iterate through each phantom and frequency.
- For each combination, it will invoke the `FarFieldSetup` to prepare the necessary Sim4Life project(s).
- It will run all the required simulations using the reusable `SimulationRunner`.

### 3.4. Results Extraction

The `ResultsExtractor` will be enhanced to:
- For the **environmental** scenario, it will load the results from the 12 individual simulations and compute the average psSAR10g or S_ab.
- For the **auto-induced** scenario, it will perform the MRT beamforming post-processing step. This involves combining the fields from all simulated plane waves with complex weights to maximize the signal at the user's location, as described in the paper. This is a significant piece of new analysis logic.
- Save all processed results and reports into the `results/far-field/` directory.

## 4. Phased Implementation Plan

I suggest tackling this in a phased approach to ensure a smooth transition and minimize disruption.

- **Phase 1: Project Restructuring.**
    - Create the new directory structure (`configs`, `results/near-field`, `src/studies`, etc.).
    - Move the existing `config.json` to `configs/near_field_config.json`.
    - Move the existing near-field code into the new `near_field_study.py` and `near_field_setup.py` classes, adapting them to work within the new structure.
    - Update `run_study.py` to be able to run the (existing) near-field study from the new location.
    - Move existing data from `results` and `plots` to their new subdirectories.
    - **Goal:** The project should be fully functional for near-field simulations after this phase.

- **Phase 2: Implement Environmental Far-Field Simulation.**
    - Create the `far_field_config.json`.
    - Implement the `FarFieldStudy` and `FarFieldSetup` classes to handle the environmental scenario (12 plane waves).
    - Extend the `ResultsExtractor` to correctly process and average the results from these 12 simulations.
    - **Goal:** Be able to run a full environmental far-field study.

- **Phase 3: Implement Auto-Induced Far-Field Simulation.**
    - Extend the `FarFieldSetup` to generate the grid of plane waves needed for the auto-induced scenario.
    - Implement the complex MRT beamforming logic in the `ResultsExtractor`.
    - **Goal:** Be able to run a full auto-induced far-field study.

- **Phase 4: Finalize and Refine.**
    - Update analysis and plotting scripts to work with both near-field and far-field data.
    - Add comprehensive documentation for the new architecture.
    - Refactor any shared code for better reusability.

---

This plan provides a clear path forward. It respects the complexity of the task by proposing a robust, scalable architecture and a phased implementation to manage risk.

Please let me know if this plan aligns with your vision. I am ready to proceed with the first phase.