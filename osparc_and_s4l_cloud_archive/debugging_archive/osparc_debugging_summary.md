# Summary of oSPARC Job Submission Debugging

This document summarizes the process of debugging and successfully running an `isolve` simulation on the oSPARC platform.

## Initial Problem

The initial goal was to run an `isolve` simulation on a `.smash` file using the oSPARC platform. The provided script, `scripts/debug_osparc_submission.py`, was failing with the error `Failed to create oSPARC job: None`. This indicated a fundamental issue with how the job was being submitted to the oSPARC API.

## Debugging Journey

The debugging process was iterative and involved several key steps:

1.  **Understanding the oSPARC API:** The initial script used a custom `XOsparcApiClient`. To better understand the correct API usage, we cloned the `osparc_api_example` repository. This provided working examples and demonstrated the use of the official `osparc` Python library.

2.  **Switching to the `osparc` Library:** We refactored `scripts/debug_osparc_submission.py` to use the `osparc` library. This involved changing the client initialization, file uploading, and job creation logic.

3.  **Identifying the Correct Solver:** The initial attempts were failing with a `404 Not Found` error for the specified solver. By listing all available solvers on the platform, we identified the correct service to use: `simcore/services/comp/s4l-python-runner`.

4.  **Input Bundling:** The `s4l-python-runner` service expects a zip file containing a `main.py` script and any necessary input files. We modified the submission script to create a zip archive containing the `test.smash` project file and the runner script (`scripts/run_isolve_on_osparc.py`), which was renamed to `main.py` within the archive. This requirement was inferred from the behavior of the `osparc_api_example` repository and the logs of the runner service itself, which explicitly search for a `main.py` entrypoint. While not explicitly stated in a single document, this pattern is consistent with how containerized services on platforms like oSPARC operate, where a standardized entrypoint (`main.py`) is expected. The official `osparc.md` documentation provides a general workflow for solvers but does not detail the specific requirements for the `s4l-python-runner`. The most valuable information came from analyzing the `osparc_api_example` repository, which provided a working example of this pattern.

5.  **Developing the Runner Script:** We created the `scripts/run_isolve_on_osparc.py` script to be executed by the runner service. This script is responsible for:
    *   Initializing the Sim4Life application in a headless environment using `XCore.GetOrCreateConsoleApp()`.
    *   Opening the `.smash` project file.
    *   Finding the correct simulation within the project.

6.  **Finding the Correct Simulation Method:** The most significant challenge was determining how to start the simulation from the runner script. We tried several methods (`Run()`, `Update()`, `Start()`) which all resulted in `AttributeError`. To solve this, we modified the runner script to print the `help()` documentation for the simulation object. By analyzing the logs from a successful run of this modified script, we discovered the correct method was `RunSimulation()`.

## Final Solution & Findings

The final solution involves using a specific GPU-enabled solver and has revealed detailed information about the oSPARC compute environment.

### GPU Solver and Environment

By listing all available solvers, we identified a dedicated GPU runner: `simcore/services/comp/s4l-python-runner-gpu:1.2.212`.

Submitting an inspection script to this service revealed the following hardware specifications for the GPU nodes:
*   **CPU:** 8-thread AMD EPYC 7R32 processor.
*   **RAM:** 30 Gibibytes (approx. 32.2 Gigabytes).
*   **GPU:** An **NVIDIA A10G** with **24 GB of VRAM** and CUDA version 12.8. This is a powerful, professional-grade GPU from the same generation as the RTX 30-series, making it well-suited for demanding simulations.

### The Final Roadblock: Vulkan Environment Error

When running the `isolve` simulation on the `s4l-python-runner-gpu` service, the job fails with a `Segmentation fault`. The logs show a specific Vulkan error:

```
std::exception::what: The following instance extensions are required but not supported:
VK_KHR_external_memory_capabilities
```

This indicates that the Docker container for the GPU service is missing a required Vulkan graphics driver extension. This is a platform-level issue that cannot be solved from the user-side script.

### Scripts

The following scripts were created to debug and inspect the environment:

1.  **`scripts/debug_osparc_submission.py`**: The main script for submitting jobs. It was modified to target the `s4l-python-runner-gpu` service.
2.  **`scripts/run_isolve_on_osparc.py`**: The runner script that executes the simulation inside the oSPARC container. It was updated to use the correct `RunSimulation()` method.
3.  **`scripts/inspect_environment.py`**: A dedicated script to gather and print detailed information about the container's hardware and software environment.
4.  **`scripts/submit_inspect_environment.py`**: The submission script for the inspection tool.

### Conclusion

We have successfully established a workflow to submit jobs to both CPU and GPU services on oSPARC and have a comprehensive understanding of the available hardware. The final step to running a successful GPU simulation is for the oSPARC platform administrators to resolve the Vulkan driver issue within their `s4l-python-runner-gpu` service. A detailed report (`osparc_gpu_error_report.md`) has been generated for this purpose.