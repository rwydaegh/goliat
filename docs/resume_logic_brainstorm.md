# Brainstorming a "Verify and Resume" Workflow: A Dialogue

This document reconstructs the conversation about implementing a more robust and intelligent setup workflow for GOLIAT. The goal is to move beyond the simple `do_setup` flag to a system that can safely resume interrupted simulation sweeps and avoid re-running work unnecessarily.

---

### **Part 1: The Initial Question**

**You:** *"Explain me though, because I still dont understand, why there is so much code in the repo here that is like searching for things (e.g. bounding boxes) being present before making them, as if he were to want to reuse them. When what where how?"*

**Roo:** The code defensively checks for existing entities primarily for **idempotency and robustness within a single, complex `setup` phase**, not for reuse *between* separate runs.

1.  **The Far-Field Use Case:** A single `.smash` project for a far-field study contains multiple simulations (one for each direction/polarization). The first setup creates shared entities (like a bounding box), and subsequent setups *within the same run* find and reuse them to avoid errors.

2.  **Robustness:** If a setup script fails midway, these checks prevent crashes on a re-run by not attempting to re-create entities that were already made.

This clarified that the existing checks are for intra-run efficiency. The primary control remains the all-or-nothing `do_setup` flag.

---

### **Part 2: Brainstorming a More Flexible System**

**You:** *"Say hypothetically we want to introduce some type of flag... Im not even sure what I want, brainstorm with me!"*

**Roo:** This is a great line of thought. The current system is rigid. Let's brainstorm:

-   **Idea A: The "Repair/Verify" Flag (`verify_and_repair: true`)**
    -   **Concept:** Open an existing `.smash` file and intelligently check its contents, repairing or adding only what is missing.
    -   **Verdict:** Very complex to implement and maintain.

-   **Idea B: Granular Setup Flags (`setup_phases: { ... }`)**
    -   **Concept:** Break down `do_setup` into smaller, controllable phases.
    -   **Verdict:** Simpler to implement, but puts the burden of understanding dependencies on the user.

-   **Idea C: "Cache-Aware" Setup (`use_setup_cache: true`)**
    -   **Concept:** A "smart" setup that automatically skips steps that are already valid.
    -   **Verdict:** Shares the same complexity as the "repair" idea.

**Initial Recommendation:** Idea B, "Granular Setup Flags," seemed like the most practical starting point.

---

### **Part 3: The "Hash" and the Problem of Identification**

**You:** *"The coolest thing would be to be able to pick off from where it failed... I had the vague idea of using a hash key... take ALL possible defining input parameters... and bundle them into a hash file... Is the hash even needed or is overengineered ?"*

**Roo (Initial thought):** The hash is probably over-engineered. The existing file path (`near_field_{phantom}_{freq}MHz_{placement}.smash`) is already a human-readable hash. We can just use that path as the key.

**You (Crucial Counterpoint):** *"hmh idk if I agree... a user could have those same parameters... but do some runs with some more subtle parameter like a different gridding step... for do_setup = false, it would just blindly take those files with wrong gridding..."*

**Roo (Correction):** You are absolutely right. My analysis was incomplete. The file path **is not enough**. Subtle changes in the configuration are not reflected in the filename. Your hashing concept is the correct and necessary solution to create a reliable fingerprint.

---

### **Part 4: Refining the Hashing Strategy**

The conversation then focused on the critical detail: **what, exactly, do we hash?**

**Roo (Proposal 1 - Manual Picking):** We could create a function that manually picks every single relevant parameter from the config and hashes them.

**You (Critique):** *"Aye there's the rub. Not easy to write or maintain... Concretize this idea and see how feasible it is."*

**Roo (Analysis of Proposal 1):** You've pinpointed the exact challenge. This approach is extremely fragile. A developer adding a new feature must remember to update the hashing function in a separate file. If they forget, the hash is silently wrong. This is not a robust solution.

**Roo (Proposal 2 - The "Filtered View"):** Instead of picking parameters, what if we hash the **entire configuration object** that is used for a single simulation? We could create a function that builds a simulation-specific config object by copying entire relevant blocks (e.g., `simulation_parameters`, `solver_settings`, `antenna_config`).

**You (Critique):** *"But... you're still hashing entire blocks, no? So a specific simulation, say at one frequency, would still be influenced by changes in a block where another freq parameter is changed?"*

**Roo (Correction):** Another incredibly sharp observation. You are correct. My proposal was still too coarse. Hashing the entire `antenna_config` block would cause a change at 900 MHz to invalidate the hash for a 700 MHz simulation. We need to be more surgical.

---

### **Part 5: The Final Plan - A "Surgical" Configuration Snapshot**

This led to the final, most robust proposal, which directly addresses all the previous critiques.

**The Concrete Plan:**

1.  **Create a `build_simulation_config` Method:** This new method in the `Config` class will be responsible for constructing a minimal, simulation-specific configuration dictionary.

2.  **Surgically Extract Data:** Instead of copying whole blocks, this method will:
    -   Copy truly global blocks (`simulation_parameters`, `solver_settings`).
    -   **Precisely select** only the configuration for the *specific* `frequency_mhz` from the `antenna_config`.
    -   **Precisely select** only the definition for the *specific* `phantom_name`.
    -   **Reconstruct** the `placement_scenarios` block to contain only the *specific* `scenario_name`, `position_name`, and `orientation_name` being used.

3.  **Persist the Snapshot:**
    -   After a simulation's setup is successfully completed, this surgical config dictionary is generated.
    -   It is then serialized into a human-readable JSON file (e.g., `my_sim.smash.meta.json`) and stored alongside the `.smash` file.
    -   For quick comparisons, a SHA256 hash of this canonical JSON string is also stored within the metadata file.

**The "Verify and Resume" Workflow Using This Plan:**

-   On a new run, the system calculates the expected path and generates the surgical config for a given simulation.
-   It checks for the existence of the `.smash` and `.smash.meta.json` files.
-   It compares the hash of the newly generated config with the hash stored in the metadata file.
    -   **If Hashes Match:** The existing file is a perfect match. The setup is skipped.
    -   **If Hashes Do Not Match:** The configuration has changed. The old files are deleted, and the setup is re-run.
    -   **If Files are Missing/Corrupt:** The setup is run from scratch.

This final approach was deemed the most robust, as it is:
-   **Accurate:** It correctly isolates changes and avoids unnecessary rebuilds.
-   **Maintainable:** The logic is structured and tied to the config's architecture, making it less prone to human error than manual parameter picking.
-   **Debuggable:** The stored JSON metadata provides a clear, human-readable record of the exact configuration used to generate the corresponding `.smash` file.

---

## Relevant Source Files

The following files in `src/` were identified as relevant context for this discussion:

-   `src/config.py`
-   `src/project_manager.py`
-   `src/simulation_runner.py`
-   `src/studies/base_study.py`
-   `src/studies/near_field_study.py`
-   `src/studies/far_field_study.py`
-   `src/setups/base_setup.py`
-   `src/setups/near_field_setup.py`
-   `src/setups/far_field_setup.py`
-   `src/extraction/cleaner.py`
-   `src/utils.py`