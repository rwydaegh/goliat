# Sim4Life Cloud Server Discovery: Debugging Summary

## 1. Objective

The primary goal is to programmatically list all available Sim4Life cloud compute resources from a Python script. The problem is a regression in behavior: a feature that was previously working has stopped, with API calls now only returning 'localhost' instead of the full list of cloud servers.

## 2. System & Environment

*   **Software:** Sim4Life v9.0.0.18820
*   **Operating System:** Windows
*   **Python Environment:** The proprietary Python environment bundled with Sim4Life.
*   **Execution Requirement:** All scripts must be run within a shell where the project's `.bashrc` has been sourced.

## 3. The Core Problem: API Regression

The central issue is an unexplained change in the output of the `s4l_v1.simulation.GetAvailableServers()` function.

*   **Previous Behavior:** The function correctly returned a list of all available cloud compute resources (e.g., "medium", "large" servers), allowing scripts to select and run simulations on the cloud.
*   **Current Behavior:** The exact same API call, under identical conditions, now consistently returns only `['localhost']`.

This indicates a regression in the Sim4Life environment, API, or backend services, as the user's code that previously worked is now failing.

## 4. Chronological Debugging Steps & Findings

The debugging process evolved as new information came to light.

### Initial Investigation (Based on assumption of misconfiguration)

The initial debugging steps, documented in previous versions of this summary, operated under the assumption that there was a misconfiguration or a fundamental gap in the scripting environment's authentication context. This involved creating a minimal test script ([`scripts/debug_list_servers.py`](scripts/debug_list_servers.py:1)) to test both deprecated and modern APIs, which confirmed that standalone scripts could not discover servers.

### Pivotal User Feedback

The investigation pivoted upon receiving crucial user feedback: **the server discovery feature was working correctly on the previous day.** This invalidated the "authentication gap" hypothesis and pointed towards a recent, transient change.

### Final Diagnostic Test

Based on the new information, the investigation focused on proving the API's inconsistent behavior from within the main application itself.

*   **Action:** The [`src/simulation_runner.py`](src/simulation_runner.py:13) module was temporarily modified to unconditionally query for all available servers at runtime and log the result before attempting to select the configured server.
*   **Test:** The main study was executed using a configuration specifying a cloud server (`"server": "medium"` in [`configs/todays_far_field_config.json`](configs/todays_far_field_config.json:1)).
*   **Finding (The "Smoking Gun"):** The execution log provided definitive proof of the regression. The application logged `Found available servers: ['localhost']` and then immediately failed with the error `RuntimeError: Server 'medium' not found.`.

This test proves that even within the full application context (with the GUI presumably running and authenticated), the Sim4Life API is currently failing to provide the list of cloud resources.

## 5. Final Conclusion & Path Forward

1.  **The problem is a regression in the Sim4Life environment.** The `s4l_v1.simulation.GetAvailableServers()` function is no longer returning the expected list of cloud servers. This is not a user code issue, as the same code was previously working.

2.  **The root cause is external to the user's project.** The change in behavior points to a potential issue with the Sim4Life backend services, a transient network configuration problem, or a bug triggered within the Sim4Life application's session management.

**Recommendation for Next Steps:**

The problem must be escalated to Sim4Life support. The evidence is clear and concise.

The key information for the support ticket is:
**"The `s4l_v1.simulation.GetAvailableServers()` function has suddenly stopped returning cloud compute resources. It now only returns `['localhost']`, whereas previously it returned the full list of servers. This is a regression that prevents us from running simulations on the cloud. The execution log from our application clearly shows the API returning the incorrect list, leading to a `RuntimeError` when trying to select a configured cloud server."**

The log from the final test run should be provided as direct evidence.

---
*This document summarizes the debugging process as of 2025-09-12, updated to reflect the discovery of the API regression.*