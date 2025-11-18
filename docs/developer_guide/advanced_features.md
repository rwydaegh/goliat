# Advanced features: a deeper dive

This section details the architecture and workflow of the key operational features of the codebase, focusing on the graphical user interface (GUI), logging, session management, and the profiling/timing system.

## 1. High-level workflow

The application is designed to run scientific studies which can be time-consuming. To provide user feedback and manage complexity, the system employs a multi-process architecture.

1.  **Main Process**: A lightweight PySide6 GUI (`ProgressGUI`) is launched. This GUI is responsible for displaying progress, logs, and timing information.
2.  **Study Process**: The actual study (`NearFieldStudy` or `FarFieldStudy`) is executed in a separate process using Python's `multiprocessing` module. This prevents the GUI from freezing during intensive calculations.
3.  **Communication**: The study process communicates with the GUI process through a `multiprocessing.Queue`. It sends messages containing status updates, progress information, and timing data.

The entry point for the study process is the `study_process_wrapper` function, which sets up a special `QueueGUI` object. This object mimics the real GUI's interface but directs all its output to the shared queue.

```mermaid
graph TD
    A[Main Process: ProgressGUI] -- Spawns --> B[Study Process: study_process_wrapper];
    B -- Instantiates --> Study[NearFieldStudy/FarFieldStudy];
    Study -- Uses --> QueueGUI[QueueGUI object];
    QueueGUI -- Puts messages --> C{multiprocessing.Queue};
    C -- Polled by QTimer<br/>every 100ms --> E[QueueHandler];
    E -- Updates GUI --> A;
    E -- Forwards messages --> F[WebGUIBridge];
    F -- HTTP POST<br/>throttled --> G[Monitoring Dashboard<br/>API];
    A -- Updates UI --> D[User];
    G -- Displays status --> H[Web Dashboard];
    
    style C fill:#FFE082
    style E fill:#C5E1A5
    style F fill:#BBDEFB
    style G fill:#E1BEE7
```

## 2. GUI and profiling system

The user interface, progress estimation, and timing systems are tightly integrated to provide a responsive and informative experience. The GUI architecture is modular, with specialized components handling different aspects of the interface. The core components are the `ProgressGUI` and the `Profiler`.

### The `ProgressGUI`

The GUI runs in the main process. It uses a `QTimer` to poll a `multiprocessing.Queue` for messages sent from the study process. This design keeps the UI responsive. The GUI is responsible for two primary progress indicators:

-   **Overall Progress**: Tracks the progress of the entire study (e.g., 5 out of 108 simulations complete).
-   **Stage Progress**: Tracks the progress of the current major phase (`setup`, `run`, or `extract`) for the *current* simulation.

The GUI is built using modular components located in `goliat/gui/components/`:

-   **`StatusManager`**: Manages status messages and log display with color-coding.
-   **`DataManager`**: Handles CSV data files for progress tracking and time series visualization.
-   **`TimingsTable`**: Displays execution statistics in a table format.
-   **`PieChartsManager`**: Generates pie charts showing time breakdown by phase and subtask.
-   **`ProgressAnimation`**: Manages smooth animations for progress bars during long-running phases.
-   **`TrayManager`**: Provides system tray integration for background operation.
-   **`QueueHandler`**: Processes messages from the study process queue and forwards them to the web bridge.
-   **`WebBridgeManager`**: Manages connection to the web monitoring dashboard and forwards GUI messages.
-   **`UIBuilder`**: Constructs the window layout and manages UI components.

### The `Profiler`

The `Profiler` class is the engine for all timing and estimation.

-   **Session-Based Timing**: The profiler maintains a session-specific timing configuration file in the `data/` folder (e.g., `profiling_config_31-10_14-15-30_a1b2c3d4.json`). The filename includes a timestamp prefix followed by a unique hash. This file stores average times for each major phase (`avg_setup_time`, `avg_run_time`, etc.) and for granular subtasks. The session-specific approach means each study run tracks its own timing data, allowing for cleaner session management and avoiding conflicts between concurrent runs.
-   **Dual Estimation System**: The profiler maintains two types of estimates:
    - **Simple averages** (`avg_{phase}_time`): Used for display purposes (pie charts, timings table, phase weights). These are straightforward arithmetic means of all real phase executions, excluding cached phases.
    - **Smart estimates**: Computed on-the-fly for ETA calculations using a weighted average that emphasizes the last 3 simulations (70% weight) while incorporating all historical data. Within the last 3, the most recent measurement gets the highest weight. This makes ETA calculations more responsive to recent trends while maintaining stability from older data.
-   **Cached Phase Handling**: Cached setup phases are excluded from statistics to prevent polluting real execution time estimates. When a setup phase is skipped due to caching, it doesn't affect the simple average stored in `avg_{phase}_time`, ensuring pie charts and statistics reflect actual execution times.
-   **Starting with Cached Simulations**: When a study begins with many cached simulations, ETA calculations use estimates from the previous session (or defaults) until real measurements are available. As real simulations complete, the smart estimate adapts quickly, emphasizing the most recent measurements. The ETA calculation uses actual elapsed time rather than estimated time, so cached simulations that complete quickly don't inflate the remaining time estimate.
-   **ETA Calculation**: The `get_time_remaining` method provides the core ETA logic. It calculates the total estimated time for all simulations based on the current session's smart phase estimates and subtracts the time that has already elapsed. This elapsed time is a combination of the total time for already completed simulations and the real-time duration of the current, in-progress simulation.
-   **Weighted Progress**: The `Profiler` calculates the progress within a single simulation by using phase weights. These weights are derived from the estimated time of each phase in the current session, normalized to sum to 1. This makes a longer phase, like `run`, contribute more to the intra-simulation progress than a shorter one, like `extract`.

### The animation system

For long-running phases where the underlying process provides no feedback (like `iSolve.exe`), the GUI employs a smooth animation for the **Stage Progress** bar.

**How it works:**

1.  **Initiation**: When a major phase (e.g., `setup`) begins, the `profile` context manager in the study process retrieves the estimated duration for that entire phase from the `Profiler` (stored as `avg_setup_time`, `avg_run_time`, etc.). It sends a `start_animation` message to the GUI with this duration.

2.  **Animation Execution**: The `ProgressGUI` receives the message. It resets the stage progress bar to 0% and starts a `QTimer` that fires every 50ms.

3.  **Frame-by-Frame Update**: With each tick of the timer, the `update_animation` method calculates the percentage of the estimated duration that has elapsed and updates the stage progress bar to that value. This creates a smooth animation from 0% to 100% over the expected duration of the phase.

4.  **Synchronization**: The `update_animation` method is also responsible for updating the **Overall Progress** bar. On each tick, it asks the `Profiler` for the current weighted progress of the entire study and updates the overall bar accordingly. This keeps both bars synchronized.

5.  **Termination**: When the actual phase completes in the study process, an `end_animation` message is sent. The GUI stops the timer and sets the stage progress bar to its final value of 100%, correcting for any deviation between the estimate and the actual time taken.

This system presents the user with a constantly updating and reasonably accurate view of the system's progress, even without direct feedback from the core simulation.

## 3. Logging (`logging_manager.py`)

The system uses Python's standard `logging` module, configured to provide two distinct streams of information.

### Loggers:

1.  **`progress` logger**: For high-level, user-facing messages. These are shown in the GUI and saved to `*.progress.log`.
2.  **`verbose` logger**: For detailed, internal messages. These are saved to the main `*.log` file.

### Implementation details:

-   **Log Rotation**: The `setup_loggers` function checks the number of log files in the `logs` directory. If it exceeds a limit (15 pairs), it deletes the oldest pair (`.log` and `.progress.log`) to prevent the directory from growing indefinitely.
-   **Data File Cleanup**: Similarly, the system automatically manages CSV and JSON files in the `data/` directory (progress tracking and profiling files). When more than 50 such files exist, the oldest files are automatically deleted to prevent excessive disk usage. These files follow the naming pattern `time_remaining_DD-MM_HH-MM-SS_hash.csv`, `overall_progress_DD-MM_HH-MM-SS_hash.csv`, and `profiling_config_DD-MM_HH-MM-SS_hash.json`, where the timestamp allows easy identification of when each session was run.
-   **Handler Configuration**: The function creates file handlers and stream (console) handlers for each logger, routing messages to the right places. `propagate = False` is used to prevent messages from being handled by parent loggers, avoiding duplicate output.

## 4. Configuration (`config.py`)

The `Config` class uses a powerful inheritance mechanism to avoid duplicating settings.

-   **Inheritance**: A config can "extend" a base config. The `_load_config_with_inheritance` method recursively loads the base config and merges it with the child config. The child's values override the parent's.

    For example, `near_field_config.json` might only specify the settings that differ from the main `base_config.json`.

## 5. Project management

-   **`project_manager.py`**: This class is critical for reliability. The underlying `.smash` project files can become corrupted or locked. The `_is_valid_smash_file` method is a key defensive measure. It first attempts to rename the file to itself (a trick to check for file locks on Windows) and then uses `h5py` to ensure the file is a valid HDF5 container before attempting to open it in the simulation software. This prevents the application from crashing on a corrupted file.

## 6. Phantom rotation for `by_cheek` placement

A specialized feature for the `by_cheek` placement scenario is the ability to rotate the phantom to meet the phone, rather than the other way around. This is controlled by a specific dictionary format in the configuration and uses an automatic angle detection algorithm to ensure precise placement.

### Configuration

To enable this feature, the orientation in `placement_scenarios` is defined as a dictionary:

```json
"orientations": {
  "cheek_base": {
    "rotate_phantom_to_cheek": true,
    "angle_offset_deg": 0
  }
}
```

-   `rotate_phantom_to_cheek`: A boolean that enables or disables the phantom rotation.
-   `angle_offset_deg`: An integer that specifies an additional rotation away from the cheek (0 being the default).

### Automatic angle detection

The system uses a binary search algorithm to find the exact angle at which the phantom's "Skin" entity touches the phone's ground plane. This is handled by the `_find_touching_angle` method in `goliat/setups/near_field_setup.py`. The search is performed between 0 and 30 degrees with a precision of 0.5 degrees.

### Workflow integration

The phantom rotation is handled in the `NearFieldSetup.run_full_setup` method, occurring after the antenna is placed but before the final scene alignment. This keeps the phone positioned correctly relative to the un-rotated phantom, after which the phantom is rotated into the final position. When phantom rotation is enabled, the rotation instruction is removed from the antenna's orientation list to prevent the antenna from being rotated along with the phantom.

## 6.5. Scene alignment for `by_cheek` placements

For `by_cheek` placements, GOLIAT automatically aligns the entire simulation scene with the phone's upright orientation. This optimization aligns the computational grid with the phone's orientation, which can reduce simulation time.

### How it works

The alignment process occurs after antenna placement and phantom rotation (if enabled). It identifies reference entities on the phone that define its orientation:

-   For PIFA antennas: Uses `component1:Substrate` and `component1:Battery` as reference points.
-   For IFA antennas: Uses `Ground` and `Battery` as reference points.

The system calculates a transformation matrix that makes the phone upright and applies this transformation to all scene entities:

-   Phantom group
-   Antenna group
-   Simulation bounding box
-   Antenna bounding box
-   Head and trunk bounding boxes
-   Point sensors

Only parent groups and bounding boxes are transformed, not individual tissue entities, to avoid double transformation. This keeps the entire scene's relative geometry correct while optimizing grid alignment.

### Configuration

No configuration is required. The alignment is automatically applied for `by_cheek` placements.

## 7. The `Verify and Resume` caching system

GOLIAT integrates a `Verify and Resume` feature to prevent redundant computations by caching simulation results. The system intelligently determines whether a simulation with an identical configuration has already been successfully completed, skipping re-runs and saving significant time.

### Verification workflow

The verification logic is multi-tiered, prioritizing the integrity of the final result files ("deliverables") over simple metadata flags. This maintains robustness against interrupted runs or manual file deletions.

1.  **Configuration hashing**: Before verification, a "surgical" configuration is created. This is a snapshot containing only the parameters relevant to a single, specific simulation run (e.g., one phantom, one frequency, one placement). This configuration is then serialized and hashed (SHA256), producing a unique fingerprint that represents the exact setup.

2.  **Metadata and deliverable validation**: The core logic resides in `ProjectManager.create_or_open_project`, which is called at the start of each simulation. It performs a sequence of checks:

    -   **Hash comparison**: The hash of the current surgical configuration is compared against the `config_hash` stored in the `config.json` metadata file within the simulation's results directory. A mismatch signifies that the configuration has changed, rendering the cached results invalid and triggering a full re-run.
    -   **`.smash` file integrity**: If the hashes match, the system validates the `.smash` project file itself. This is a critical step for stability, as these files can become locked or corrupted. The validation involves checking for `.s4l_lock` files and verifying the HDF5 structure with `h5py`. A missing or corrupt `.smash` file indicates that the setup phase is incomplete.
    -   **Deliverable verification**: This is the definitive check. The system looks for the actual output files generated by the `run` and `extract` phases. It verifies their existence and that their modification timestamps are newer than the `setup_timestamp` recorded in the metadata.
        -   **Run phase deliverables**: A valid `*_Output.h5` file.
        -   **Extract phase deliverables**: `sar_results.json`, `sar_stats_all_tissues.pkl`, and `sar_stats_all_tissues.html`.

3.  **Status reporting and phase skipping**: The verification process returns a detailed status dictionary, such as `{'setup_done': True, 'run_done': True, 'extract_done': False}`. The study orchestrator (`NearFieldStudy` or `FarFieldStudy`) uses this status to dynamically skip phases that are already complete. For instance, if `run_done` is `True`, the `do_run` flag for that specific simulation is internally set to `False`, and the run phase is skipped.

4.  **Metadata update**: Upon the successful completion of the `run` and `extract` phases, the `BaseStudy._verify_and_update_metadata` method is triggered. It re-confirms that the deliverables exist on the file system and then updates the `run_done` or `extract_done` flags in the `config.json` file to `true`. This keeps the metadata accurately reflecting the state of the deliverables for future runs.

This deliverable-first approach is a key design choice. It guarantees that the system is resilient; even if the metadata file claims a phase is complete, the absence of the actual result files will correctly force the system to re-run the necessary steps.

### Overriding the cache

The entire caching and verification mechanism can be bypassed using the `--no-cache` command-line flag.

```bash
goliat study my_study.json --no-cache
```

When this flag is active, GOLIAT will ignore any existing project files or metadata. It skips the verification process, deletes any existing `.smash` file for the target simulation, and executes all phases (setup, run, extract) from a clean state. This is useful for debugging configuration issues, validating code changes, or when a fresh run is explicitly required.

The `--no-cache` flag can also be used when you need to ensure that cached results from a previous configuration are not reused, even if the current configuration appears identical.

## 8. Web monitoring dashboard integration

GOLIAT supports remote monitoring through a web dashboard. Monitor multiple worker machines from one interface, track progress across distributed studies, and view real-time logs and system information.

### Architecture overview

The web monitoring system uses a bridge pattern to forward GUI messages to a remote dashboard API without interfering with local GUI operation. The architecture consists of four components:

- **`QueueHandler`**: Processes messages from the study process queue. After updating the local GUI, forwards a copy of each message to the web bridge (if enabled).

- **`WebBridgeManager`**: Manages the web bridge connection lifecycle. Initializes the bridge, collects system information (GPU, CPU, RAM, hostname), and handles connection status updates.

- **`WebGUIBridge`**: Core bridge component that forwards messages to the dashboard API. Uses an internal queue to decouple from the multiprocessing queue and implements message throttling to prevent API overload.

- **`HTTPClient`**: Handles HTTP requests to the dashboard API endpoints (`/api/gui-update` and `/api/heartbeat`).

### Message flow

Messages flow from the study process to the web dashboard through this path:

```mermaid
sequenceDiagram
    participant Study as Study Process
    participant Queue as multiprocessing.Queue
    participant Handler as QueueHandler
    participant GUI as ProgressGUI
    participant Bridge as WebGUIBridge
    participant API as Dashboard API
    participant Dashboard as Web Dashboard
    
    Study->>Queue: Put message (status, progress, etc.)
    Queue->>Handler: Poll (every 100ms)
    Handler->>GUI: Update local UI
    Handler->>Bridge: Enqueue message copy
    Bridge->>Bridge: Throttle & batch
    Bridge->>API: HTTP POST /api/gui-update
    API->>Dashboard: Update worker state
    Bridge->>Bridge: Send heartbeat (every 30s)
    Bridge->>API: HTTP POST /api/heartbeat
```

### Message types and handling

The `QueueHandler` processes several message types, each forwarded to the web bridge (with appropriate sanitization):

- `status`: Log messages with color coding. Batched together (up to 20 messages per batch, sent every 300ms) for efficiency.
- `overall_progress`: Overall study progress (e.g., 5 out of 108 simulations). Sent immediately with throttling (up to 50 Hz).
- `stage_progress`: Progress within the current phase (setup/run/extract). Sent immediately with throttling.
- `profiler_update`: ETA and timing information. The profiler object is sanitized to extract only serializable data (e.g., `eta_seconds`).
- `finished`: Study completion notification.
- `fatal_error`: Fatal error notification.

### Throttling and batching

The `WebGUIBridge` throttles messages to prevent API overload:

- Progress updates (`overall_progress`, `stage_progress`, `profiler_update`): Sent immediately but throttled to 50 Hz (20ms minimum interval).
- Log messages (`status`): Batched together and sent every 300ms, or immediately if the batch reaches 20 messages.
- Heartbeats: Sent every 30 seconds to maintain worker registration and update connection status.

### Connection management

The web bridge maintains connection state and provides feedback to the GUI:

- Connection callback: The bridge calls `ProgressGUI._update_web_status` whenever the connection status changes. Updates a visual indicator (green dot for connected, red dot for disconnected) in the GUI.
- Graceful degradation: If the dashboard is unavailable or the `requests` library is not installed, the GUI continues to function normally. Messages are silently dropped (not queued) to prevent memory buildup.
- System information: On initialization, the bridge collects and sends system information (GPU model, CPU cores, RAM capacity, hostname) with the initial heartbeat. This information is displayed on the web dashboard.

### Worker identification

Workers are identified by their IP address (or local IP if no public IP is available). The dashboard handles IP changes (e.g., VPN reconnections) by matching workers by hostname and transferring running assignments to the new worker session.

### API endpoints

The web bridge communicates with two API endpoints:

- `POST /api/gui-update`: Sends GUI state updates (progress, logs, status). Payload includes `machineId`, `message`, and `timestamp`.
- `POST /api/heartbeat`: Registers or updates worker status and sends system information. Called automatically every 30 seconds.

### Initialization

The web bridge initializes automatically when:

- `use_web` is set to `true` in the configuration (default).
- The `requests` library is installed (`pip install requests`).
- A machine ID can be detected (public IP or local IP).
- The dashboard URL is accessible (default: `https://goliat.waves-ugent.be`).

To disable web monitoring, set `use_web: false` in your configuration. The GUI shows a connection status indicator to inform users whether web monitoring is active.

### Error handling

The web bridge handles errors gracefully:

- Network errors: Connection timeouts and errors are logged but do not affect GUI operation.
- Message serialization: Non-serializable objects (like the `Profiler` instance) are sanitized before sending.
- Thread safety: HTTP requests are executed in a thread pool to avoid blocking the GUI thread.

For more information about using the monitoring dashboard, see the [Monitoring Dashboard documentation](../cloud/monitoring.md).

For a complete reference of all features mentioned here and more, see the [Full List of Features](../reference/full_features_list.md).