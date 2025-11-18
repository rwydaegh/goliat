# Refactoring Plan: simulation_runner.py

## Current State Analysis

### File Statistics
- **Total lines**: 894
- **Main class**: `SimulationRunner` (894 lines)
- **Deepest nesting**: 5-6 levels (try/except/while/if/if/if)
- **Largest method**: `_run_isolve_manual()` (~345 lines)
- **Complexity hotspots**:
  - `run()` method: 106 lines with nested conditionals
  - `_run_isolve_manual()`: 345 lines with deeply nested retry logic
  - `_run_osparc_direct()`: 159 lines

### Issues Identified

1. **Excessive Nesting**: 
   - `_run_isolve_manual()` has 5-6 levels of nesting (try/while/try/if/while/if)
   - `run()` method has nested if/else chains
   - Exception handling creates additional nesting layers

2. **Method Length**:
   - `_run_isolve_manual()` is 345 lines - violates single responsibility
   - Contains multiple concerns: process management, output parsing, error handling, retry logic

3. **Code Duplication**:
   - Post-simulation steps duplicated between `_run_isolve_manual()` and `_run_osparc_direct()`
   - Error handling patterns repeated
   - Save retry logic embedded in `run()` method

4. **Mixed Concerns**:
   - Process lifecycle management mixed with output parsing
   - Error detection mixed with logging
   - Retry logic mixed with process execution

## Refactoring Strategy

Following patterns observed in the codebase (similar to `ResultsExtractor`, `ProjectManager`, and setup classes), we'll:

1. **Extract helper classes** for distinct responsibilities
2. **Break down large methods** into smaller, focused methods
3. **Use context objects** to reduce parameter passing
4. **Separate concerns** into logical modules
5. **Reduce nesting** through early returns and guard clauses

## Proposed Structure

### 1. Extract iSolve Process Manager (`isolve_process_manager.py`)

**Purpose**: Handle subprocess lifecycle, output reading, and process monitoring

**Responsibilities**:
- Create and manage subprocess
- Read stdout/stderr in background thread
- Monitor process state
- Handle process termination/cleanup

**Methods**:
```python
class ISolveProcessManager:
    def __init__(self, command, gui, logger)
    def start_process()
    def is_running()
    def wait_for_completion(timeout)
    def terminate()
    def get_return_code()
    def read_stderr()
```

**Benefits**:
- Reduces nesting in `_run_isolve_manual()`
- Encapsulates subprocess complexity
- Reusable for other process-based runners

### 2. Extract iSolve Output Parser (`isolve_output_parser.py`)

**Purpose**: Parse and process iSolve stdout output

**Responsibilities**:
- Detect error patterns in output lines
- Extract progress milestones
- Format time remaining strings
- Track logged milestones

**Methods**:
```python
class ISolveOutputParser:
    def __init__(self, logger)
    def parse_line(line: str) -> ParsedLine
    def is_error_line(line: str) -> bool
    def extract_progress(line: str) -> Optional[ProgressInfo]
    def format_time_remaining(time_str: str) -> str
```

**Data Classes**:
```python
@dataclass
class ParsedLine:
    is_error: bool
    error_message: Optional[str]
    progress_info: Optional[ProgressInfo]
    raw_line: str

@dataclass
class ProgressInfo:
    percentage: int
    time_remaining: str
    mcells_per_sec: str
```

**Benefits**:
- Separates parsing logic from execution logic
- Makes error detection testable
- Reduces cognitive load in main method

### 3. Extract Retry Handler (`retry_handler.py`)

**Purpose**: Manage retry logic and error recovery

**Responsibilities**:
- Track retry attempts
- Determine if retry should occur
- Handle retry delays/backoff
- Log retry attempts

**Methods**:
```python
class RetryHandler:
    def __init__(self, max_retries, logger)
    def should_retry(return_code, detected_errors) -> bool
    def record_attempt()
    def get_attempt_number() -> int
    def reset()
```

**Benefits**:
- Separates retry logic from execution
- Makes retry behavior configurable
- Reduces nesting in retry loops

### 4. Extract Post-Simulation Steps (`post_simulation_handler.py`)

**Purpose**: Handle common post-simulation tasks

**Responsibilities**:
- Wait for results
- Reload project
- Verify simulation availability
- Handle errors during post-processing

**Methods**:
```python
class PostSimulationHandler:
    def __init__(self, project_path, document, profiler, logger)
    def wait_for_results()
    def reload_project()
    def verify_simulation(sim_name) -> Simulation
```

**Benefits**:
- Eliminates duplication between `_run_isolve_manual()` and `_run_osparc_direct()`
- Makes post-processing testable
- Reduces method length

### 5. Extract Save Handler (`save_handler.py`)

**Purpose**: Handle project saving with retry logic

**Responsibilities**:
- Save project with retry logic
- Handle Save() vs SaveAs() decision
- Log save attempts

**Methods**:
```python
class SaveHandler:
    def __init__(self, document, project_path, config, logger)
    def save_with_retry()
    def _should_use_save() -> bool
    def _attempt_save(attempt_num) -> bool
```

**Benefits**:
- Removes 40+ lines of save logic from `run()` method
- Makes save behavior testable
- Reduces nesting in `run()`

### 6. Refactor Main Methods

#### `run()` Method Refactoring

**Current**: 106 lines with nested conditionals

**Proposed**:
```python
def run(self):
    """Runs the simulation using the configured execution method."""
    if not self.simulation:
        self._log_error("Simulation object not found")
        return
    
    try:
        self._write_input_file()
        if self.config.get_only_write_input_file():
            return
        
        self._execute_simulation()
    except Exception as e:
        self._handle_run_error(e)
    
    return self.simulation

def _write_input_file(self):
    """Writes input file and saves project."""
    # Extract save logic to SaveHandler
    # Reduce to ~20 lines

def _execute_simulation(self):
    """Routes to appropriate execution method."""
    # Simple routing logic, ~10 lines
    if self.config["manual_isolve"]:
        self._run_isolve_manual(self.simulation)
    elif self._is_osparc_server():
        self._run_osparc_direct(self.simulation, server_name)
    else:
        self._run_sim4life_api(server_name)
```

**Benefits**:
- Reduces nesting from 4-5 levels to 2-3 levels
- Each method has single responsibility
- Easier to test individual steps

#### `_run_isolve_manual()` Method Refactoring

**Current**: 345 lines with 5-6 levels of nesting

**Proposed**:
```python
def _run_isolve_manual(self, simulation):
    """Runs iSolve.exe directly with real-time output logging."""
    command = self._build_isolve_command(simulation)
    process_manager = ISolveProcessManager(command, self.gui, self.verbose_logger)
    output_parser = ISolveOutputParser(self.verbose_logger)
    retry_handler = RetryHandler(max_retries=30, logger=self)
    post_handler = PostSimulationHandler(...)
    
    try:
        with self.profiler.subtask("run_isolve_execution"):
            while retry_handler.should_continue():
                self._check_for_stop_signal()
                self._run_keep_awake_if_needed()
                
                result = self._execute_isolve_attempt(
                    process_manager, output_parser, retry_handler
                )
                
                if result.success:
                    break
                
                retry_handler.record_attempt()
        
        post_handler.wait_and_reload(simulation.Name)
    except StudyCancelledError:
        process_manager.cleanup()
        raise
    finally:
        process_manager.cleanup()

def _execute_isolve_attempt(self, process_manager, output_parser, retry_handler):
    """Execute a single iSolve attempt."""
    process_manager.start_process()
    detected_errors = []
    
    while process_manager.is_running():
        self._check_for_stop_signal()
        lines = process_manager.read_available_output()
        
        for line in lines:
            parsed = output_parser.parse_line(line)
            if parsed.is_error:
                detected_errors.append(parsed.error_message)
                self._log_error(parsed.error_message)
            if parsed.progress_info:
                self._log_progress_milestone(parsed.progress_info)
    
    return_code = process_manager.get_return_code()
    stderr_output = process_manager.read_stderr()
    
    return ExecutionResult(
        success=(return_code == 0),
        return_code=return_code,
        detected_errors=detected_errors,
        stderr_output=stderr_output
    )
```

**Benefits**:
- Reduces nesting from 5-6 levels to 2-3 levels
- Main method becomes orchestrator (~50 lines)
- Execution logic separated into focused methods
- Each component testable independently

## File Structure After Refactoring

```
goliat/goliat/
├── simulation_runner.py          (~200 lines, orchestrator)
├── runners/
│   ├── __init__.py
│   ├── isolve_process_manager.py    (~150 lines)
│   ├── isolve_output_parser.py      (~100 lines)
│   ├── retry_handler.py              (~80 lines)
│   ├── post_simulation_handler.py    (~100 lines)
│   └── save_handler.py               (~80 lines)
```

## Implementation Phases

### Phase 1: Extract Save Handler
- **Goal**: Remove save logic from `run()` method
- **Impact**: Reduces `run()` from 106 to ~60 lines
- **Risk**: Low - isolated functionality

### Phase 2: Extract Post-Simulation Handler
- **Goal**: Remove duplication between iSolve and oSPARC methods
- **Impact**: Reduces both methods by ~40 lines each
- **Risk**: Low - clear boundaries

### Phase 3: Extract Output Parser
- **Goal**: Separate parsing logic from execution
- **Impact**: Makes parsing testable, reduces cognitive load
- **Risk**: Medium - needs careful interface design

### Phase 4: Extract Process Manager
- **Goal**: Encapsulate subprocess management
- **Impact**: Reduces nesting significantly
- **Risk**: Medium - core functionality, needs thorough testing

### Phase 5: Extract Retry Handler
- **Goal**: Separate retry logic from execution
- **Impact**: Makes retry behavior configurable
- **Risk**: Low - isolated concern

### Phase 6: Refactor Main Methods
- **Goal**: Apply extracted components to main methods
- **Impact**: Reduces nesting and method length
- **Risk**: Medium - integration testing needed

## Metrics for Success

### Before Refactoring
- `simulation_runner.py`: 894 lines
- `_run_isolve_manual()`: 345 lines, 5-6 nesting levels
- `run()`: 106 lines, 4-5 nesting levels
- Cyclomatic complexity: High

### Target After Refactoring
- `simulation_runner.py`: ~200 lines
- `_run_isolve_manual()`: ~50 lines, 2-3 nesting levels
- `run()`: ~30 lines, 2 nesting levels
- Helper modules: 5 files, ~100-150 lines each
- Cyclomatic complexity: Low-Medium

## Testing Strategy

1. **Unit Tests**: Each extracted class tested independently
2. **Integration Tests**: Verify components work together
3. **Regression Tests**: Ensure existing functionality preserved
4. **Edge Cases**: Test error handling, cancellation, retries

## Migration Notes

- Maintain backward compatibility during refactoring
- Use feature flags if needed for gradual rollout
- Keep original methods temporarily with deprecation warnings
- Update documentation as components are extracted

## Risks and Mitigation

1. **Risk**: Breaking existing functionality
   - **Mitigation**: Comprehensive test coverage before refactoring

2. **Risk**: Over-engineering
   - **Mitigation**: Start with simplest extractions, iterate

3. **Risk**: Performance impact
   - **Mitigation**: Profile before/after, minimize object creation

4. **Risk**: Increased complexity from multiple files
   - **Mitigation**: Clear module organization, good documentation

## References

- Similar patterns used in:
  - `ResultsExtractor` - uses context objects and helper classes
  - `ProjectManager` - separates concerns into focused methods
  - Setup classes - break down large workflows into steps
  - `LoggingMixin` - provides shared functionality via mixin

