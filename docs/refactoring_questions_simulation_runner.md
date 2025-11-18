# Critical Questions for Refactoring simulation_runner.py

After deep analysis, I've identified several edge cases and design decisions that need clarification before refactoring. These questions will help ensure the refactored code maintains exact behavior and handles all scenarios correctly.

## Threading and Queue Concerns

### Q1: Reader Thread Failure Handling
**Current behavior:** The `reader_thread` is daemonized and has a try/finally that closes the pipe. If the thread crashes or raises an exception:
- The main thread won't know (no exception propagation from daemon threads)
- The queue might be incomplete
- The pipe might not be closed properly

**Question:** Should we:
- A) Add exception handling in reader_thread and log errors?
- B) Use a shared flag/queue to signal thread errors to main thread?
- C) Keep current behavior (thread dies silently, main thread continues)?

**Current code location:** Lines 446-465

### Q2: Queue Buffer Size
**Current behavior:** `Queue()` is created without `maxsize`, so it's unbounded. If the reader thread writes faster than the main thread reads:
- Queue could grow unbounded (memory issue)
- No backpressure mechanism

**Question:** Should we:
- A) Add a maxsize to Queue (e.g., `maxsize=1000`) to prevent unbounded growth?
- B) Keep unbounded (current behavior) - assume main thread reads fast enough?
- C) Add monitoring/logging if queue size exceeds threshold?

**Current code location:** Line 502

### Q3: Thread Join Timeout
**Current behavior:** `thread.join()` is called without timeout after `process.poll()` returns None. However:
- The thread might still be reading from a closed pipe
- If thread hangs, join() will hang forever

**Question:** Should we:
- A) Add timeout to `thread.join(timeout=5)` and handle timeout?
- B) Keep current behavior (assume thread finishes quickly)?
- C) Check thread.is_alive() before joining?

**Current code location:** Line 561

## Process Lifecycle Edge Cases

### Q4: Process State Race Conditions
**Current behavior:** Multiple checks of `process.poll()` throughout the code:
- Line 310: In cleanup (check if still running)
- Line 517: In monitoring loop (check if still running)
- Line 618: Before retry cleanup (check if still running)
- Line 666: In exception handler (check if still running)

**Question:** Are there race conditions where:
- Process terminates between `poll()` check and `terminate()` call?
- Process is already dead but `poll()` hasn't updated yet?
- Should we use `process.returncode is None` instead of `poll() is None` for consistency?

**Current code location:** Multiple locations

### Q5: Process Termination Timeout Values
**Current behavior:** Different timeout values used:
- Line 318: `wait(timeout=5)` in cleanup
- Line 525: `wait(timeout=2)` on stop signal
- Line 621: `wait(timeout=2)` before retry

**Question:** Why different timeouts?
- A) Intentional (cleanup gets more time, retries need to be faster)?
- B) Should be consistent (use same timeout everywhere)?
- C) Should be configurable?

### Q6: Stderr Reading Timing
**Current behavior:** Stderr is read AFTER process completes (line 580-588). However:
- Stderr buffer might be small and overflow if not read during execution
- Some errors might be lost if stderr buffer fills up

**Question:** Should we:
- A) Read stderr during execution (like stdout) in a separate thread?
- B) Keep current behavior (read after completion) - assume stderr is small?
- C) Read stderr periodically during execution?

**Note:** Comments say "most errors are in stdout" - is stderr reading just a fallback?

## Retry Logic Questions

### Q7: Maximum Retry Limit
**Current behavior:** `while True:` loop with no maximum retry limit. The code will retry forever if iSolve keeps failing.

**Question:** Should we:
- A) Add a configurable maximum retry limit (e.g., `max_retries=30` from config)?
- B) Keep infinite retries (current behavior) - assume user will cancel if needed?
- C) Add exponential backoff between retries?

**Current code location:** Line 472

### Q8: Retry Conditions
**Current behavior:** Retries on ANY non-zero return code (line 593). No distinction between:
- Transient errors (should retry)
- Permanent errors (shouldn't retry)
- User cancellation (shouldn't retry)

**Question:** Should we:
- A) Add logic to detect permanent errors and fail immediately?
- B) Keep current behavior (retry on all failures)?
- C) Add configurable retry conditions based on error patterns?

**Current code location:** Lines 593-595

### Q9: Retry Attempt Counter
**Current behavior:** `retry_attempt` starts at 0, increments after each failure. First failure logs "retry attempt 1", second logs "retry attempt 2", etc.

**Question:** Is this the intended behavior?
- A) First attempt should be "attempt 1", first retry should be "retry attempt 2"?
- B) Current behavior is correct (first failure = "retry attempt 1")?

**Current code location:** Lines 470, 625-630

## Keep-Awake Script Questions

### Q10: Keep-Awake Trigger Mechanisms
**Current behavior:** Keep-awake is triggered in TWO different ways:
1. Before each retry attempt (line 477-486) - imports and calls `keep_awake()` function
2. On first progress update (line 548-550) - calls `_launch_keep_awake_script()` which spawns subprocess

**Question:** Why two different mechanisms?
- A) Intentional (function call before retry, subprocess on progress)?
- B) Should be unified (use same mechanism)?
- C) Should only trigger once total (not per retry)?

**Current code location:** Lines 334-338, 477-486, 548-550

### Q11: Keep-Awake Failure Handling
**Current behavior:** If keep_awake fails:
- Before retry: Prints warning, continues (line 484-486)
- On progress: No exception handling (subprocess.Popen might fail silently)

**Question:** Should we:
- A) Add exception handling for `_launch_keep_awake_script()`?
- B) Keep current behavior (failures are non-critical)?
- C) Log keep_awake failures to verbose logger?

## Error Detection Questions

### Q12: Error Detection Timing
**Current behavior:** Errors are detected in THREE places:
1. During execution (line 539-546) - real-time from stdout
2. After execution in remaining output (line 568-575) - drain queue
3. From stderr (line 603-608) - fallback if no stdout errors

**Question:** Is this the correct order of precedence?
- A) Yes, stdout errors are primary, stderr is fallback
- B) Should stderr errors also be logged even if stdout errors exist?
- C) Should we combine all errors into a single list?

**Current code location:** Multiple locations

### Q13: Error Logging Duplication
**Current behavior:** Errors detected in stdout are logged immediately (line 542-546) AND tracked in `detected_errors` list. The list is checked later but errors are already logged.

**Question:** Is the `detected_errors` list used for anything other than:
- A) Preventing duplicate stderr logging (line 603)?
- B) Future retry decision logic?
- C) Just for tracking/completeness?

**Current code location:** Lines 490, 540, 569, 603, 612

## Project Reload Questions

### Q14: Simulation Name Persistence
**Current behavior:** Simulation name is captured before reload (line 708), then searched after reload (line 709). If simulation name changes during reload:
- Code will raise RuntimeError (line 711)
- User will see error message

**Question:** Can simulation names change during reload?
- A) No, names are stable - current behavior is correct
- B) Yes, but rare - should we handle gracefully?
- C) Should we search by ID instead of name?

**Current code location:** Lines 708-711

### Q15: Project Reload Failure
**Current behavior:** If `open_project()` fails during reload:
- Exception will propagate up
- No specific handling for reload failures

**Question:** Should we:
- A) Add retry logic for project reload?
- B) Keep current behavior (fail fast)?
- C) Add specific error messages for reload failures?

**Current code location:** Lines 702-703

## Global Registry Questions

### Q16: Multiple Runner Instances
**Current behavior:** Global `_active_runners` set tracks all SimulationRunner instances. Multiple instances can exist simultaneously (e.g., parallel execution).

**Question:** 
- A) Can multiple SimulationRunner instances run iSolve simultaneously?
- B) Should we prevent multiple iSolve processes from same runner instance?
- C) Is the global registry cleanup sufficient for parallel execution?

**Current code location:** Lines 16-30, 81, 332

### Q17: Cleanup Order
**Current behavior:** Cleanup happens in multiple places:
1. On cancellation (line 719)
2. On exception (line 723)
3. In finally block (line 733)
4. In `_cleanup_isolve_process()` which removes from registry (line 332)
5. At process exit via atexit (line 30)

**Question:** Is there a risk of double-cleanup?
- A) No, `_cleanup_isolve_process()` checks if process exists
- B) Yes, but harmless (idempotent cleanup)
- C) Should we add a flag to prevent double-cleanup?

**Current code location:** Multiple locations

## Save Logic Questions

### Q18: Save vs SaveAs Decision
**Current behavior:** Uses `Save()` if document path matches project path, otherwise `SaveAs()`. This avoids "ARES error about connection to running jobs" (comment line 124).

**Question:** 
- A) Is this ARES error still a concern in current Sim4Life versions?
- B) Should we always use SaveAs() for safety?
- C) Is the path comparison logic correct (normalized paths)?

**Current code location:** Lines 125-129

### Q19: Save Retry Logic Duplication
**Current behavior:** Save retry logic exists in TWO places:
1. `SimulationRunner.run()` - lines 116-147 (fallback)
2. `ProjectManager.save()` - lines 638-687 (preferred)

**Question:** Should we:
- A) Always use ProjectManager.save() and remove fallback?
- B) Keep fallback for backward compatibility (tests, etc.)?
- C) Extract to shared SaveHandler as planned?

**Current code location:** Lines 112-147, 638-687

## Profiling Questions

### Q20: Profiler Subtask Timing
**Current behavior:** Profiler subtask wraps entire retry loop (line 469). This means:
- Retry attempts are included in timing
- Failed attempts add to total time

**Question:** Should we:
- A) Keep current behavior (include retry time in measurement)?
- B) Only measure successful attempt time?
- C) Track retry attempts separately in profiler?

**Current code location:** Line 469

## Stop Signal Questions

### Q21: Stop Signal Check Frequency
**Current behavior:** Stop signal checked:
1. Before each retry attempt (line 474)
2. During process execution loop (line 519)

**Question:** Is the 0.1 second sleep (line 556) sufficient for responsiveness?
- A) Yes, 100ms is acceptable
- B) Should check more frequently?
- C) Should use event-driven approach instead of polling?

**Current code location:** Lines 474, 519, 556

### Q22: Stop Signal During Cleanup
**Current behavior:** Stop signal is NOT checked during:
- Process termination (lines 522-528)
- Queue draining (lines 562-578)
- Project reload (lines 684-715)

**Question:** Should we:
- A) Add stop signal checks during cleanup/reload?
- B) Keep current behavior (once stopped, finish cleanup)?
- C) Make cleanup interruptible?

## General Architecture Questions

### Q23: Component Extraction Strategy
**Question:** For the refactoring, should we:
- A) Extract components gradually (one at a time, test each)?
- B) Extract all components at once (big bang)?
- C) Extract in phases as planned (SaveHandler → PostSimulation → etc.)?

### Q24: Backward Compatibility
**Question:** Should the refactored code:
- A) Maintain exact same public API (no breaking changes)?
- B) Allow some API changes if they improve usability?
- C) Add deprecation warnings for old patterns?

### Q25: Testing Strategy
**Question:** What level of testing is available/needed?
- A) Unit tests for each component?
- B) Integration tests for full flow?
- C) Manual testing with real simulations?
- D) All of the above?

---

## Summary of Critical Decisions Needed

1. **Threading:** How to handle reader thread failures and queue overflow?
2. **Retries:** Should there be a maximum retry limit?
3. **Keep-Awake:** Why two different trigger mechanisms?
4. **Error Detection:** Is the current three-place detection correct?
5. **Process Cleanup:** Are timeouts and cleanup order correct?
6. **Project Reload:** Can simulation names change, and how to handle failures?

These answers will guide the refactoring to ensure exact behavior preservation while improving code structure.

