# Project Overview: Near-Field Dosimetric Assessment for Child Phantoms

This document provides a high-level overview of the near-field Specific Absorption Rate (SAR) analysis project for the GOLIAT initiative.

## 1. Core Objective

The central goal is to perform a comprehensive near-field SAR assessment for the **Thelonius** and **Eartha** child voxel phantoms. This work replicates and expands upon the methodologies and results presented in the `Near-field_GOLIAT.pdf` reference study.

The project aims to deliver a robust, automated, and reproducible simulation framework capable of handling a large matrix of parameters.

## 2. Key Deliverables

The primary outputs for each simulation run include:

*   Whole-body SAR
*   Head SAR
*   Trunk SAR
*   Peak spatial-average SAR (psSAR10g) in the skin, eyes, and brain.

All results will be normalized to an applied power that induces a psSAR10g of 1 W/kg.

## 3. Simulation Scope

The simulation campaign is defined by the following parameters:

*   **Phantoms:** Thelonius, Eartha
*   **Frequencies:** 700, 835, 1450, 2140, 2450, 3500, 5200, 5800 (MHz)
*   **Antenna Models:** PIFA and IFA models, selected based on the operating frequency.
*   **Antenna Placements:** 22 distinct positions and orientations per phantom, covering the eyes, belly, and ear regions.

## 4. Framework Architecture

The project is built on a modular, class-based Python framework that interfaces with the Sim4Life API. The key components are:

*   **`src/config.py`**: Manages all simulation and phantom configurations through JSON files, ensuring a clean separation of parameters from code.
*   **`src/antenna.py`**: A helper class that abstracts antenna-specific details, such as model selection and source configuration based on frequency.
*   **`src/project.py`**: The core `NearFieldProject` class, which encapsulates the entire workflow for a single simulation—from setup and antenna placement to execution and result extraction.
*   **`src/study.py`**: The `NearFieldStudy` class, designed to orchestrate the full simulation campaign by iterating through all defined parameters.
*   **`run_study.py`**: The main entry point for launching simulations.

This structure is designed to be scalable, maintainable, and easily adaptable for future research needs. For more detailed information on the project structure, setup, and future roadmap, please refer to the `near_field/README.md` and `near_field/docs/ROADMAP.md`.