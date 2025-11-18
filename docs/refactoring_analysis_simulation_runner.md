# Detailed Refactoring Analysis: simulation_runner.py

## Executive Summary

After deep analysis of `simulation_runner.py` (894 lines), I've identified **7 levels of nesting** in `_run_isolve_manual()` and multiple mixed concerns. This document provides a concrete, behavior-preserving refactoring plan that follows existing codebase patterns.

## Detailed Nesting Analysis

### `_run_isolve_manual()` - Current Structure (345 lines)

**Nesting Levels Identified:**

```
Level 1: try (line 467) - Outer exception handling
  Level 2: with profiler.subtask (line 469) - Profiling context
    Level 3: while True (line 472) - Retry loop (max 30 retries)
      Level 4: if keep_awake (line 477) - Conditional keep_awake trigger
        Level 5: try (line 478) - Keep_awake exception handling
      Level 4: try (line 492) - Subprocess execution
        Level 5: while process.poll() is None (line 517) - Process monitoring loop
          Level 6: if gui.is_stopped() (line 519) - Stop signal check
            Level 7: try/except (line 524) - Process termination with timeout
          Level 6: try (line 531) - Queue reading
            Level 7: while True (line 534) - Drain queue loop
          Level 6: except Empty (line 554) - Queue empty handler
        Level 5: if return_code == 0 (line 593) - Success check
          Level 6: break - Exit retry loop
        Level 5: else (line 596) - Failure handling
          Level 6: if stderr_output (line 603) - Error logging
          Level 6: if detected_errors (line 612) - Error tracking
          Level 6: if process.poll() (line 618) - Cleanup check
      Level 4: except StudyCancelledError (line 631) - Re-raise cancellation
      Level 4: except Exception (line 634) - General exception handling
        Level 5: if current_isolve_process (line 637) - Cleanup on exception
  Level 2: Post-simulation steps (line 684) - Wait, reload, verify
Level 1: except StudyCancelledError (line 717) - Outer cancellation handler
Level 1: except Exception (line 721) - Outer exception handler
Level 1: finally (line 731) - Always cleanup
```

**Key Observations:**
- **7 levels deep** at maximum (queue draining inside process monitoring)
- **Retry logic** embedded in execution logic (no clear separation)
- **Error detection** happens in multiple places (stdout parsing, stderr reading, return codes)
- **Cleanup logic** scattered (3 different places: success, exception, finally)
- **Stop signal checks** in 2 places (before retry, during execution)

## Mixed Concerns Identified

### 1. Process Lifecycle Management
- **Lines 493-500**: Subprocess creation
- **Lines 502-505**: Thread setup for non-blocking I/O
- **Lines 517-556**: Process monitoring loop
- **Lines 558-591**: Process completion handling
- **Lines 302-332**: Cleanup method (separate but related)

**Issues:**
- Process state tracked via `self.current_isolve_process` (shared state)
- Thread management mixed with process monitoring
- Cleanup logic duplicated in multiple places

### 2. Output Parsing & Error Detection
- **Lines 223-251**: `_is_isolve_error_line()` - Error pattern detection
- **Lines 253-296**: `_check_and_log_progress_milestones()` - Progress parsing
- **Lines 190-221**: `_format_time_remaining()` - Time formatting
- **Lines 538-553**: Real-time error detection in monitoring loop
- **Lines 567-578**: Error detection in remaining output

**Issues:**
- Parsing logic scattered across multiple methods
- Error detection happens in 3 different places
- Progress milestone tracking uses mutable set (`logged_milestones`)

### 3. Retry Logic
- **Lines 470-678**: Retry loop with `retry_attempt` counter
- **Lines 593-630**: Success/failure determination
- **Lines 625-630**: Retry attempt logging
- **Lines 673-678**: Retry attempt increment on exception

**Issues:**
- No maximum retry limit enforced (infinite loop with `while True`)
- Retry decision logic mixed with execution logic
- Retry state (`retry_attempt`) managed manually

### 4. Keep-Awake Integration
- **Lines 334-338**: `_launch_keep_awake_script()` - Launch subprocess
- **Lines 477-486**: Keep-awake trigger before each retry
- **Lines 548-550**: Keep-awake trigger on first progress update

**Issues:**
- Triggered in 2 different places (before retry, during execution)
- Exception handling for keep_awake mixed with main logic
- `keep_awake_triggered` flag used to prevent duplicate triggers

### 5. Post-Simulation Steps
- **Lines 684-715**: Wait for results, reload project, verify simulation
- **Lines 862-893**: Duplicated in `_run_osparc_direct()`

**Issues:**
- Exact same code in 2 methods (28 lines duplicated)
- Profiling subtasks embedded in post-processing
- Error handling for reload/verification mixed with main flow

### 6. Save Logic
- **Lines 112-147**: Save with retry logic in `run()` method
- **Lines 638-687**: Similar logic in `ProjectManager.save()`

**Issues:**
- Save logic duplicated (though ProjectManager has cleaner version)
- Save decision (Save vs SaveAs) logic embedded in retry loop
- 40+ lines of save logic in `run()` method

## Behavior Preservation Requirements

### Critical Behaviors to Maintain

1. **Process Cleanup:**
   - Must cleanup on cancellation (`StudyCancelledError`)
   - Must cleanup on exceptions
   - Must cleanup in `finally` block
   - Must cleanup on process exit (atexit handler)
   - Must track process in `self.current_isolve_process` for global cleanup

2. **Stop Signal Handling:**
   - Must check before starting new retry attempt (line 474)
   - Must check during process execution (line 519)
   - Must terminate process immediately when stop detected
   - Must raise `StudyCancelledError` (not return silently)

3. **Error Detection:**
   - Must detect errors in stdout (iSolve writes errors to stdout, not stderr)
   - Must log errors immediately at progress level (for web interface)
   - Must track detected errors for retry decision
   - Must read stderr as fallback (though most errors are in stdout)

4. **Retry Behavior:**
   - Must retry on non-zero return code
   - Must retry on exceptions during execution
   - Must increment retry attempt counter
   - Must log retry attempts
   - **No maximum retry limit** (current code uses `while True`)

5. **Output Processing:**
   - Must process output in real-time (non-blocking)
   - Must drain remaining output after process completes
   - Must log progress milestones (0%, 33%, 66%)
   - Must format time remaining as HH:MM:SS

6. **Keep-Awake:**
   - Must trigger before first retry attempt
   - Must trigger on first "Time Update" line
   - Must not trigger multiple times (use flag)
   - Must handle keep_awake exceptions gracefully (print warning, continue)

7. **Post-Simulation:**
   - Must wait 5 seconds for results
   - Must close and reload project
   - Must verify simulation exists after reload
   - Must raise RuntimeError if simulation not found

## Refactoring Strategy: Component Extraction

Following patterns from `ResultsExtractor` (uses `ExtractionContext`), `ProjectManager` (focused methods), and extraction classes (inherit `LoggingMixin`), we'll extract components that:

1. **Encapsulate single responsibilities**
2. **Use context objects to reduce parameter passing**
3. **Inherit LoggingMixin for consistent logging**
4. **Maintain exact behavior through careful interface design**

## Proposed Component Interfaces

### 1. ISolveProcessManager

**Purpose:** Encapsulate subprocess lifecycle and non-blocking I/O

**Key Responsibilities:**
- Create and manage subprocess
- Background thread for stdout reading
- Process state monitoring
- Cleanup and termination

**Interface:**
```python
class ISolveProcessManager(LoggingMixin):
    def __init__(self, command: List[str], gui: Optional[QueueGUI], verbose_logger: Logger):
        """Initialize process manager.
        
        Args:
            command: Command to execute (e.g., [isolve_path, "-i", input_file])
            gui: GUI proxy for stop signal checks
            verbose_logger: Logger for verbose output
        """
        self.command = command
        self.gui = gui
        self.verbose_logger = verbose_logger
        self.process: Optional[subprocess.Popen] = None
        self.output_queue: Queue = Queue()
        self.reader_thread: Optional[threading.Thread] = None
        self._is_running = False
    
    def start(self) -> None:
        """Start the subprocess and begin reading output."""
        # Create subprocess with pipes
        # Start background thread for stdout reading
        # Set _is_running = True
    
    def is_running(self) -> bool:
        """Check if process is still running."""
        return self._is_running and self.process is not None and self.process.poll() is None
    
    def read_available_lines(self) -> List[str]:
        """Read all available lines from output queue (non-blocking).
        
        Returns:
            List of lines read (may be empty if no output available)
        """
        # Drain queue non-blockingly
        # Return list of lines
    
    def read_all_remaining_lines(self) -> List[str]:
        """Read all remaining lines after process completes.
        
        Should be called after is_running() returns False.
        Ensures reader thread has finished and queue is drained.
        """
        # Join reader thread
        # Drain queue completely
        # Return all lines
    
    def get_return_code(self) -> Optional[int]:
        """Get process return code (None if still running)."""
        return self.process.returncode if self.process else None
    
    def read_stderr(self) -> str:
        """Read stderr output (fallback - most errors are in stdout)."""
        # Read from process.stderr
        # Return stripped string or empty
    
    def terminate(self, timeout: float = 2.0) -> None:
        """Terminate process gracefully, force kill if needed.
        
        Args:
            timeout: Seconds to wait for graceful termination
        """
        # Try terminate()
        # Wait with timeout
        # Force kill if needed
    
    def cleanup(self) -> None:
        """Clean up process and threads."""
        # Terminate if running
        # Join reader thread
        # Close pipes
        # Set _is_running = False
```

**Behavior Preservation:**
- Maintains non-blocking I/O via background thread + queue
- Handles process termination with timeout
- Cleans up threads properly
- Preserves exact subprocess creation flags (`CREATE_NO_WINDOW`)

### 2. ISolveOutputParser

**Purpose:** Parse iSolve stdout output for errors and progress

**Key Responsibilities:**
- Detect error patterns in lines
- Extract progress information
- Format time strings
- Track logged milestones

**Interface:**
```python
@dataclass
class ParsedLine:
    """Result of parsing a single output line."""
    raw_line: str
    is_error: bool
    error_message: Optional[str]
    has_progress: bool
    progress_info: Optional["ProgressInfo"] = None

@dataclass
class ProgressInfo:
    """Extracted progress information."""
    percentage: int
    time_remaining: str  # Formatted as HH:MM:SS
    mcells_per_sec: str

class ISolveOutputParser(LoggingMixin):
    def __init__(self, verbose_logger: Logger):
        """Initialize parser.
        
        Args:
            verbose_logger: Logger for verbose output
        """
        self.verbose_logger = verbose_logger
        self.logged_milestones: Set[int] = set()
        self.progress_pattern = re.compile(
            r"\[PROGRESS\]:\s*(\d+)%\s*\[.*?\]\s*Time Update[^@]*estimated remaining time\s+([^@]+?)\s+@\s+([\d.]+)\s+MCells/s"
        )
    
    def parse_line(self, line: str) -> ParsedLine:
        """Parse a single output line.
        
        Args:
            line: Raw output line (may include newline)
            
        Returns:
            ParsedLine with detected information
        """
        stripped = line.strip()
        
        # Check for errors
        is_error = self._is_error_line(stripped)
        error_msg = stripped if is_error else None
        
        # Check for progress
        progress_info = self._extract_progress(stripped)
        
        return ParsedLine(
            raw_line=line,
            is_error=is_error,
            error_message=error_msg,
            has_progress=progress_info is not None,
            progress_info=progress_info
        )
    
    def should_log_milestone(self, percentage: int) -> bool:
        """Check if milestone should be logged (0%, 33%, 66%).
        
        Uses 1% data for 0% milestone (more accurate).
        Tracks logged milestones to prevent duplicates.
        
        Args:
            percentage: Progress percentage from line
            
        Returns:
            True if milestone should be logged
        """
        # Check if 0% (using 1% data), 33%, or 66%
        # Check if already logged
        # Return True if should log
    
    def log_milestone(self, progress_info: ProgressInfo) -> None:
        """Log a progress milestone.
        
        Args:
            progress_info: Progress information to log
        """
        # Determine which milestone (0%, 33%, 66%)
        # Add to logged_milestones
        # Log with formatted message
    
    def _is_error_line(self, line: str) -> bool:
        """Check if line contains error pattern."""
        # Same logic as current _is_isolve_error_line()
    
    def _extract_progress(self, line: str) -> Optional[ProgressInfo]:
        """Extract progress information from line."""
        # Match progress pattern
        # Format time remaining
        # Return ProgressInfo or None
    
    def _format_time_remaining(self, time_str: str) -> str:
        """Format time string to HH:MM:SS."""
        # Same logic as current _format_time_remaining()
    
    def reset_milestones(self) -> None:
        """Reset logged milestones (for retry attempts)."""
        self.logged_milestones.clear()
```

**Behavior Preservation:**
- Maintains exact error pattern detection
- Preserves milestone logging logic (0% uses 1% data)
- Tracks milestones to prevent duplicates
- Formats time exactly as before

### 3. RetryHandler

**Purpose:** Manage retry logic and attempt tracking

**Key Responsibilities:**
- Track retry attempts
- Determine if retry should occur
- Log retry attempts
- No maximum limit (matches current behavior)

**Interface:**
```python
class RetryHandler(LoggingMixin):
    def __init__(self, progress_logger: Logger):
        """Initialize retry handler.
        
        Args:
            progress_logger: Logger for progress-level messages
        """
        self.progress_logger = progress_logger
        self.attempt_number = 0
    
    def should_retry(self, return_code: Optional[int], detected_errors: List[str]) -> bool:
        """Determine if retry should occur.
        
        Args:
            return_code: Process return code (None if exception)
            detected_errors: List of errors detected in output
            
        Returns:
            True if should retry (always True for non-zero return code)
        """
        # Current behavior: retry on any non-zero return code
        # No maximum limit (while True loop)
        return return_code != 0
    
    def record_attempt(self) -> None:
        """Record a retry attempt and log it."""
        self.attempt_number += 1
        if self.attempt_number > 0:
            self._log(
                f"    - iSolve failed, retry attempt {self.attempt_number}",
                level="progress",
                log_type="warning"
            )
    
    def get_attempt_number(self) -> int:
        """Get current attempt number (0 = first attempt)."""
        return self.attempt_number
    
    def reset(self) -> None:
        """Reset attempt counter (for new simulation)."""
        self.attempt_number = 0
```

**Behavior Preservation:**
- No maximum retry limit (matches `while True`)
- Logs retry attempts exactly as before
- Tracks attempt number for logging

### 4. PostSimulationHandler

**Purpose:** Handle common post-simulation tasks

**Key Responsibilities:**
- Wait for results
- Reload project
- Verify simulation exists

**Interface:**
```python
class PostSimulationHandler(LoggingMixin):
    def __init__(
        self,
        project_path: str,
        profiler: Profiler,
        verbose_logger: Logger,
        progress_logger: Logger
    ):
        """Initialize post-simulation handler.
        
        Args:
            project_path: Path to project file
            profiler: Profiler for timing subtasks
            verbose_logger: Logger for verbose output
            progress_logger: Logger for progress output
        """
        self.project_path = project_path
        self.profiler = profiler
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        import s4l_v1.document
        self.document = s4l_v1.document
    
    def wait_and_reload(self, simulation_name: str) -> "s4l_v1.simulation.emfdtd.Simulation":
        """Wait for results, reload project, and verify simulation.
        
        Args:
            simulation_name: Name of simulation to verify
            
        Returns:
            Simulation object after reload
            
        Raises:
            RuntimeError: If simulation not found after reload
        """
        # Wait 5 seconds
        # Close and reload project
        # Verify simulation exists
        # Return simulation object
```

**Behavior Preservation:**
- Exact same timing (5 seconds wait)
- Same reload logic (Close + open_project)
- Same verification logic
- Same error handling (RuntimeError if not found)

### 5. SaveHandler

**Purpose:** Handle project saving with retry logic

**Key Responsibilities:**
- Save project with retry
- Decide Save() vs SaveAs()
- Log save attempts

**Interface:**
```python
class SaveHandler(LoggingMixin):
    def __init__(
        self,
        document,
        project_path: str,
        config: Config,
        project_manager: Optional[ProjectManager],
        verbose_logger: Logger,
        progress_logger: Logger
    ):
        """Initialize save handler.
        
        Args:
            document: Sim4Life document object
            project_path: Path to save project to
            config: Configuration object
            project_manager: Optional ProjectManager (preferred)
            verbose_logger: Logger for verbose output
            progress_logger: Logger for progress output
        """
        self.document = document
        self.project_path = project_path
        self.config = config
        self.project_manager = project_manager
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
    
    def save_with_retry(self) -> None:
        """Save project with retry logic.
        
        Uses ProjectManager.save() if available, otherwise falls back
        to direct save with retry logic.
        
        Raises:
            Exception: If all retry attempts fail
        """
        if self.project_manager:
            # Use ProjectManager.save() (cleaner, already has retry logic)
            self.project_manager.save()
        else:
            # Fallback: direct save with retry (for backward compatibility)
            # Same logic as current lines 116-147
```

**Behavior Preservation:**
- Prefers ProjectManager.save() if available
- Falls back to direct save for backward compatibility
- Maintains exact retry logic and logging

### 6. KeepAwakeHandler

**Purpose:** Handle keep_awake script triggering

**Key Responsibilities:**
- Trigger keep_awake script
- Prevent duplicate triggers
- Handle exceptions gracefully

**Interface:**
```python
class KeepAwakeHandler:
    def __init__(self, config: Config):
        """Initialize keep_awake handler.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.triggered = False
    
    def trigger_if_needed(self, condition: bool = True) -> None:
        """Trigger keep_awake script if enabled and not already triggered.
        
        Args:
            condition: Additional condition to check (e.g., first progress update)
        """
        if not self.config.get("keep_awake", False):
            return
        
        if self.triggered:
            return
        
        if not condition:
            return
        
        # Trigger keep_awake script
        # Handle exceptions gracefully (print warning, continue)
        self.triggered = True
    
    def reset(self) -> None:
        """Reset triggered flag (for new simulation)."""
        self.triggered = False
```

**Behavior Preservation:**
- Triggers before first retry attempt
- Triggers on first "Time Update" line
- Prevents duplicate triggers
- Handles exceptions gracefully

## Refactored Method Structure

### `_run_isolve_manual()` - After Refactoring (~50 lines)

```python
def _run_isolve_manual(self, simulation: "s4l_v1.simulation.emfdtd.Simulation"):
    """Runs iSolve.exe directly with real-time output logging."""
    # Setup
    command = self._build_isolve_command(simulation)
    process_manager = ISolveProcessManager(command, self.gui, self.verbose_logger)
    output_parser = ISolveOutputParser(self.verbose_logger)
    retry_handler = RetryHandler(self.progress_logger)
    keep_awake_handler = KeepAwakeHandler(self.config)
    post_handler = PostSimulationHandler(
        self.project_path, self.profiler, self.verbose_logger, self.progress_logger
    )
    
    try:
        with self.profiler.subtask("run_isolve_execution"):
            # Retry loop
            while True:
                self._check_for_stop_signal()
                keep_awake_handler.trigger_if_needed()
                
                # Execute attempt
                result = self._execute_isolve_attempt(
                    process_manager, output_parser, retry_handler, keep_awake_handler
                )
                
                if result.success:
                    break
                
                retry_handler.record_attempt()
                output_parser.reset_milestones()  # Reset for retry
        
        # Post-simulation steps
        post_handler.wait_and_reload(simulation.Name)
        
    except StudyCancelledError:
        process_manager.cleanup()
        raise
    except Exception as e:
        process_manager.cleanup()
        self._log(
            f"An unexpected error occurred while running iSolve.exe: {e}",
            level="progress",
            log_type="error"
        )
        self.verbose_logger.error(traceback.format_exc())
        raise
    finally:
        process_manager.cleanup()

def _execute_isolve_attempt(
    self,
    process_manager: ISolveProcessManager,
    output_parser: ISolveOutputParser,
    retry_handler: RetryHandler,
    keep_awake_handler: KeepAwakeHandler
) -> ExecutionResult:
    """Execute a single iSolve attempt.
    
    Returns:
        ExecutionResult with success status and error information
    """
    process_manager.start()
    detected_errors = []
    
    # Monitor process
    while process_manager.is_running():
        self._check_for_stop_signal()
        
        # Read available output
        lines = process_manager.read_available_lines()
        
        for line in lines:
            parsed = output_parser.parse_line(line)
            
            # Log to verbose
            self.verbose_logger.info(parsed.raw_line.strip())
            
            # Handle errors
            if parsed.is_error:
                detected_errors.append(parsed.error_message)
                self._log(
                    f"iSolve: {parsed.error_message}",
                    level="progress",
                    log_type="error"
                )
            
            # Handle progress
            if parsed.has_progress:
                keep_awake_handler.trigger_if_needed(condition=True)
                if output_parser.should_log_milestone(parsed.progress_info.percentage):
                    output_parser.log_milestone(parsed.progress_info)
    
    # Read remaining output
    remaining_lines = process_manager.read_all_remaining_lines()
    for line in remaining_lines:
        parsed = output_parser.parse_line(line)
        self.verbose_logger.info(parsed.raw_line.strip())
        if parsed.is_error:
            detected_errors.append(parsed.error_message)
            self._log(
                f"iSolve: {parsed.error_message}",
                level="progress",
                log_type="error"
            )
    
    # Get results
    return_code = process_manager.get_return_code()
    stderr_output = process_manager.read_stderr()
    
    # Log stderr if no stdout errors detected
    if stderr_output and not detected_errors:
        self._log(
            f"iSolve: {stderr_output}",
            level="progress",
            log_type="error"
        )
    
    return ExecutionResult(
        success=(return_code == 0),
        return_code=return_code,
        detected_errors=detected_errors,
        stderr_output=stderr_output
    )
```

**Benefits:**
- Reduced from 345 lines to ~50 lines (main method)
- Reduced nesting from 7 levels to 3 levels
- Clear separation of concerns
- Each component testable independently
- Behavior preserved exactly

## Implementation Order

1. **Phase 1: Extract SaveHandler** (Lowest risk)
   - Extract save logic from `run()` method
   - Test with existing code

2. **Phase 2: Extract PostSimulationHandler** (Low risk)
   - Extract post-simulation steps
   - Use in both `_run_isolve_manual()` and `_run_osparc_direct()`
   - Test with existing code

3. **Phase 3: Extract ISolveOutputParser** (Medium risk)
   - Extract parsing logic
   - Test parsing independently
   - Integrate with existing code

4. **Phase 4: Extract KeepAwakeHandler** (Low risk)
   - Extract keep_awake logic
   - Test independently

5. **Phase 5: Extract RetryHandler** (Low risk)
   - Extract retry logic
   - Test independently

6. **Phase 6: Extract ISolveProcessManager** (Higher risk - core functionality)
   - Extract subprocess management
   - Thoroughly test process lifecycle
   - Test cleanup scenarios

7. **Phase 7: Refactor Main Methods** (Medium risk - integration)
   - Apply all extracted components
   - Test end-to-end
   - Verify behavior matches exactly

## Testing Strategy

### Unit Tests
- Each component tested independently
- Mock dependencies (subprocess, GUI, loggers)
- Test error scenarios

### Integration Tests
- Test components together
- Verify exact behavior matches original
- Test edge cases (cancellation, exceptions, retries)

### Regression Tests
- Run existing test suite
- Verify no behavior changes
- Test with real simulations (if possible)

## Risk Mitigation

1. **Behavior Changes:**
   - Maintain exact same error detection logic
   - Preserve exact same logging messages
   - Keep same exception handling flow

2. **Process Cleanup:**
   - Ensure cleanup in all scenarios
   - Test cancellation scenarios
   - Test exception scenarios

3. **Stop Signal Handling:**
   - Maintain exact same check points
   - Preserve immediate termination behavior
   - Test cancellation during execution

4. **Output Processing:**
   - Maintain non-blocking I/O
   - Preserve real-time logging
   - Test with various output patterns

## Conclusion

This refactoring plan:
- ✅ Reduces complexity significantly (7 levels → 3 levels)
- ✅ Separates concerns clearly
- ✅ Follows existing codebase patterns
- ✅ Preserves exact behavior
- ✅ Makes code testable and maintainable
- ✅ Reduces duplication (post-simulation steps)

The key is careful interface design that maintains exact behavior while improving structure.

