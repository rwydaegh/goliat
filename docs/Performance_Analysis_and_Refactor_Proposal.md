# Performance Analysis and Refactoring Proposal for Far-Field Studies

## 1. Summary of Findings

A detailed analysis of the far-field simulation logs and source code has identified a critical performance bottleneck that causes exponential increases in simulation setup time as frequency increases. The issue is particularly severe at frequencies above 2GHz, leading to unacceptably long runtimes and, in some cases, outright failure.

The root cause is **not** disk I/O or project file size, but rather the **repeated and computationally expensive generation of the simulation grid and voxelization of the phantom model.**

### The Core Problem

The current architecture, as seen in `src/studies/far_field_study.py`, iterates through all 12 direction/polarization configurations for a given frequency. For each of these 12 simulations, it regenerates the entire computational grid and re-voxelizes the model by calling `simulation.UpdateGrid()` and `simulation.CreateVoxels()` via `_finalize_setup` in `src/setups/base_setup.py`.

The computational cost of these operations scales exponentially with grid resolution. As higher frequencies require much finer grids, this leads to the observed performance degradation.

### Cumulative Performance Degradation

Further testing has revealed a more critical issue: the Sim4Life environment itself appears to suffer from cumulative performance degradation. Each full setup pass seems to leave behind residual state or consume resources that are not fully released, causing subsequent setups to become progressively slower.

This is evidenced by comparing two runs:
- **Full Study (`06-08_01-38-33.progress.log`):** The setup for 2450MHz, running after all lower frequencies, took **~14 minutes**.
- **Isolated Study (`06-08_17-40-10.progress.log`):** The same 2450MHz setup, when run in a fresh, clean process, took only **~34 seconds**.

This confirms the bottleneck is not just the inherent complexity of a single setup, but a compounding issue caused by the repeated execution of the setup routine within the same process.

## 2. Proposed Solution: "Setup Once, Clone Many"

To resolve this, the architecture must be refactored to eliminate redundant computations. The grid and voxelization are identical for all 12 simulations at a given frequency; only the plane wave source direction changes.

The proposed workflow is as follows:

1.  **Create a Single Base Simulation:** For each frequency, perform the full setup for only the *first* simulation configuration (e.g., `x_pos_theta`). This includes the expensive `UpdateGrid()` and `CreateVoxels()` calls. This should be done only **once per frequency**.

2.  **Clone the Base Simulation:** Use the Sim4Life API's cloning capabilities to create 11 copies of the fully prepared base simulation. This is a fast, memory-only operation that duplicates the simulation state, including the expensive grid and voxel data.

3.  **Modify Clones:** For each of the 11 clones, modify *only* the `PlaneWaveSourceSettings` to apply the correct incident direction (`phi`, `theta`) and polarization (`psi`). These are simple parameter changes and do not trigger a grid re-computation.

4.  **Run All Simulations:** Proceed with running the 12 fully-prepared simulations.

### Benefits

*   **Dramatic Performance Improvement:** Reduces the most time-consuming part of the setup phase from being executed 12 times to just once per frequency.
*   **Mitigates Degradation:** By minimizing full setup calls, this approach avoids the cumulative performance degradation observed in the Sim4Life environment, ensuring consistent and predictable setup times.
*   **Increased Stability:** Avoids the API failure at high frequencies by performing the complex discretization step only once on a clean base model.
*   **Efficiency:** Aligns the workflow with best practices for this type of parametric sweep in simulation software.

This architectural change is critical for the scalability and success of the far-field study.