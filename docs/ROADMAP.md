# Project Roadmap: Near-Field Simulation Framework

This document outlines the development roadmap for the GOLIAT near-field simulation framework.

## Phase 1: Core Framework and Validation (Complete)

-   [x] **Project Scaffolding:** Establish a robust, class-based directory structure separating configuration, source code, and data.
-   [x] **Configuration Management:** Implement a `Config` class to load and manage all simulation and phantom parameters from JSON files.
-   [x] **Antenna Abstraction:** Create an `Antenna` class to handle frequency-dependent model and source selection.
-   [x] **Single Project Workflow:** Develop the `NearFieldProject` class to handle the setup, execution, and result extraction for a single simulation case.
-   [x] **Initial Validation:** Debug and validate the end-to-end workflow for a single test case (`Thelonius`, 700MHz, `front_of_eyes`).
-   [x] **Logging Control:** Implement targeted suppression of verbose Sim4Life engine logs for a cleaner and more readable output.
-   [x] **Documentation:** Create a comprehensive `README.md` detailing the project setup and execution.

## Phase 2: Campaign Automation and Full Phantom Support

-   [ ] **Full Campaign Automation:**
    -   [ ] Implement the `NearFieldStudy` class to iterate through all phantoms, frequencies, and placements defined in the configuration files.
    -   [ ] Add robust progress tracking and logging for large-scale simulation campaigns.
-   [ ] **Eartha Phantom Integration:**
    -   [ ] Add `eartha.sab` to the `data/phantoms` directory.
    -   [ ] Create a complete configuration profile for Eartha in `phantoms_config.json`, including bounding box definitions and antenna placements.
    -   [ ] Validate the simulation workflow for the Eartha phantom.
-   [ ] **Advanced Result Extraction:**
    -   [ ] Implement logic to extract SAR values for all required organs and tissues.
    -   [ ] Add functionality to calculate and save whole-body, head, and trunk SAR.
    -   [ ] Implement the power normalization calculation to report results for a 1 W/kg reference.

## Phase 3: Version Control and CI/CD

-   [ ] **GitHub Integration:**
    -   [ ] Initialize a private Git repository for the `near_field` project.
    -   [ ] Create a remote repository on `github.ugent.be`.
    -   [ ] Push the initial project structure and source code.
-   [ ] **Continuous Integration:**
    -   [ ] Set up a CI pipeline (e.g., using GitHub Actions) to run automated checks on new commits.
    -   [ ] Implement basic linting and code style checks.
    -   [ ] (Optional) Develop a small-scale, non-graphical test suite that can run in a CI environment to verify core logic without a full Sim4Life license.

## Phase 4: Enhancements and Future Work

-   [ ] **Data Analysis and Visualization:**
    -   [ ] Develop scripts to aggregate results from all simulations into a single data structure (e.g., Pandas DataFrame).
    -   [ ] Create plotting functions to visualize key results and comparisons.
-   [ ] **Parameter Sweeping:** Enhance the `NearFieldStudy` class to support sweeping over additional parameters (e.g., antenna distance, orientation angles).
-   [ ] **Error Handling and Recovery:** Improve the framework's resilience to individual simulation failures within a large campaign.