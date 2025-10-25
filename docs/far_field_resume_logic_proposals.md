# Design Proposals: Enabling "Verify and Resume" for Far-Field Studies

## 1. The Problem: A Mismatch of Granularity

The current "Verify and Resume" feature, which uses a `.smash.meta.json` file to store a configuration hash, is fundamentally incompatible with the structure of Far-Field studies.

-   **Near-Field (Works):** One `.smash` project file corresponds to exactly one simulation. The metadata file's hash accurately represents the project's contents.
-   **Far-Field (Fails):** One `.smash` project file contains *multiple* distinct simulations (e.g., 12 simulations for different incident directions and polarizations). A single metadata file cannot represent the state of all simulations within the project, making the hash-based verification unreliable.

As an immediate fix, this feature has been disabled for Far-Field studies. This document proposes several long-term solutions to enable intelligent resume capabilities for these multi-simulation projects.

---

## 2. Proposed Solutions

### Solution A: The "Manifest" Metadata File (Recommended)

This approach adapts the metadata file to acknowledge the one-to-many relationship in Far-Field projects.

-   **Concept:** Instead of a single hash, the `.smash.meta.json` file would act as a "manifest," containing a dictionary of hashes. Each key would be a unique identifier for a simulation within the project, and the value would be its corresponding surgical configuration hash.

-   **Implementation:**
    1.  **Unique Simulation ID:** Create a consistent, unique identifier for each Far-Field simulation (e.g., `x_pos_theta`).
    2.  **Modify `ProjectManager`:**
        -   `_write_metadata` would be updated to accept a simulation ID and its config hash, adding or updating it in the manifest.
        -   `_verify_project` would take a simulation ID and its config, checking only that specific entry in the manifest.
    3.  **Modify `FarFieldStudy`:** The study loop would be responsible for generating the simulation ID and passing it to the `ProjectManager`. The study would decide whether to run a specific simulation based on the verification result. The project setup (`create_new`) would only be triggered if *no* valid simulations exist in the manifest.

-   **Pros:**
    -   **Robust and Accurate:** Correctly tracks the state of each individual simulation.
    -   **Efficient:** Allows re-running only the specific directions/polarizations that have changed.
    -   **Clean Architecture:** Keeps the project management logic contained.

-   **Cons:**
    -   **Moderate Complexity:** Requires significant changes to `ProjectManager` and `FarFieldStudy`.

### Solution B: One Project File Per Simulation

This approach refactors the Far-Field study to conform to the one-to-one mapping that the "Verify and Resume" feature was designed for.

-   **Concept:** Instead of one large `.smash` file containing 12 simulations, the `FarFieldStudy` would create 12 separate `.smash` files, one for each direction/polarization combination.

-   **Implementation:**
    1.  **Modify `FarFieldStudy`:** The main loop would change its project creation logic to generate a unique project path for each simulation (e.g., `.../700MHz/x_pos_theta/far_field_..._x_pos_theta.smash`).
    2.  **No Change to `ProjectManager`:** The existing verification logic would work perfectly out-of-the-box, as each project would now have its own dedicated metadata file.

-   **Pros:**
    -   **Simple to Implement:** Requires minimal changes, mostly localized to the `FarFieldStudy` class.
    -   **Leverages Existing Logic:** No need to modify the already-working verification system.

-   **Cons:**
    -   **File System Clutter:** Greatly increases the number of project files and directories, which could be cumbersome for users to navigate.
    -   **Potential Performance Overhead:** May introduce a slight overhead due to repeated opening/closing of files, although this is likely negligible.

### Solution C: In-Project Metadata Storage

This is a more advanced solution that embeds the configuration metadata directly into the `.smash` (HDF5) file itself.

-   **Concept:** Use the `h5py` library to store the surgical configuration snapshots as attributes or datasets within the `.smash` file. The metadata would live alongside the simulation data it describes.

-   **Implementation:**
    1.  **Modify `ProjectManager`:**
        -   `_write_metadata` would open the `.smash` file and write the config snapshot and hash to a specific path inside it (e.g., `/metadata/simulations/x_pos_theta`).
        -   `_verify_project` would read from the same internal path.
    2.  **Robust File Handling:** Requires careful management of HDF5 file handles to avoid corruption.

-   **Pros:**
    -   **Self-Contained:** The project file and its metadata are a single, portable unit. No separate `.json` files.
    -   **Elegant:** A technically clean solution that avoids cluttering the file system.

-   **Cons:**
    -   **High Complexity and Risk:** Interacting with the HDF5 file at this level is complex and could risk corrupting the project file if not handled perfectly.
    -   **Opaque to Users:** The metadata is no longer easily human-readable in a text editor.

---

## 3. Recommendation

**Solution A (The "Manifest" Metadata File)** is the recommended path forward. It provides the best balance of accuracy, efficiency, and maintainable architecture. While more complex to implement than Solution B, it avoids cluttering the file system and provides a robust, scalable framework for handling complex, multi-simulation projects within the "Verify and Resume" system.