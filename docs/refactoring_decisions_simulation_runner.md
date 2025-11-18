# Refactoring Decisions: simulation_runner.py

## Answers to Questions

### Q19: When is project_manager provided vs not?

**Answer:**
- **Production code**: `project_manager` IS ALWAYS provided via `BaseStudy._execute_run_phase()` (line 187)
- **Tests**: Will need to provide mock ProjectManager
- **Decision**: **REQUIRE project_manager always** - remove Optional, remove fallback code

### Critical Memory Issue

**User reported:** iSolve memory grows over time (50-100GB+) and eventually fails with bad memory allocation after many simulations. Even increasing pagefile didn't help.

**User observation:** Memory growth seems to be between simulations, not between retry attempts. But not 100% certain - could be accumulation or just one sim needing more memory.

**Implications for refactoring:**
- **MUST ensure thorough cleanup** - process termination must release all memory
- **MUST cleanup on retry attempts** - each failed attempt must fully clean up before retry
- **MUST ensure global registry cleanup works** - atexit handler must properly terminate processes
- **ADD delay after cleanup** - 0.5s sleep after cleanup before retry to ensure memory release (we're dealing with 50-100GB+)
- **ADD retry warning** - Log error every 50 retries (brief message) to alert if user isn't watching

## Key Decisions Summary

| Question | Decision | Notes |
|----------|----------|-------|
| Q1: Reader thread errors | Keep current (no special handling) | User doesn't see issue, pipe is simple |
| Q2: Queue size | Keep unbounded | Only text, not huge |
| Q3: Thread join timeout | **Add `thread.is_alive()` check** | Defensive safety net |
| Q4-Q5: Process state/cleanup | Don't meddle | Keep current behavior |
| Q6: Stderr reading | Keep current (read after) | Stderr is small/empty |
| Q7: Max retries | **Keep infinite + error log every 50** | Brief error message to alert user |
| Q8-Q9: Retry logic | Keep current | No changes |
| Q10: Keep-awake | **Keep exact same, NO comments** | Licensing related, don't document |
| Q11-Q13: Error detection | Keep current | Prevent duplicates, stdout primary |
| Q14: Sim name | Never changes | Current behavior correct |
| Q15: Sim verification | **DELETE lines 708-711, NO comment** | User confirmed, no explanation needed |
| Q16: Parallel runs | **Critical** - ensure iSolve stops and releases memory | Especially on retry attempts |
| Q17: Cleanup idempotency | Keep current | Seems idempotent (just kills process) |
| Q18: Save logic | Keep current | Save() vs SaveAs() decision stays |
| Q19: project_manager | **REQUIRE always** | Remove Optional, remove fallback, tests provide mock |
| Q20: Profiler timing | Time retry attempts | Include retries in measurement |
| Q21-Q22: Stop signal | Keep current | 100ms polling is fine |
| Q23: Extraction strategy | **Follow planned phases** | Gradual extraction |
| Q24: API changes | **Allow minor, document precisely** | Tell user what/why/where |
| Q25: Tests | **Fix goliat/tests** | Ensure all tests pass |

## Refactoring Plan Adjustments

### Phase 1: Extract SaveHandler
- **Require project_manager**: Remove Optional, remove fallback code
- **Extract to SaveHandler** - just calls `project_manager.save()`
- **Breaking change**: Tests must provide mock ProjectManager

### Phase 2: Extract PostSimulationHandler
- **REMOVE simulation verification** (lines 708-711) as user confirmed
- **Simplify**: Just wait, reload, done
- **Use in both** `_run_isolve_manual()` and `_run_osparc_direct()`

### Phase 3-6: Extract Components
- **ISolveProcessManager**: Ensure thorough cleanup, especially memory release
- **ISolveOutputParser**: Keep exact error detection logic
- **RetryHandler**: Keep infinite retries, track attempts
- **KeepAwakeHandler**: Keep exact same behavior, NO comments about licensing

### Critical: Memory Cleanup
- **Process termination**: Ensure `terminate()` → `wait()` → `kill()` if needed
- **Cleanup on retry**: Must fully clean up failed process before retry
- **ADD delay after cleanup**: 0.5s sleep after cleanup before retry (50-100GB+ memory)
- **Global registry**: Ensure atexit handler properly terminates all processes
- **Thread cleanup**: Ensure reader thread is properly joined/cleaned up
- **ADD retry warning**: Log error every 50 retries (brief message)

## API Changes (Minor Breaking Change, Documented)

### Breaking Changes:
1. **`project_manager` parameter**: Now REQUIRED (was Optional) in `SimulationRunner.__init__()`
   - **Why**: Simplifies code, production always provides it anyway
   - **Impact**: Tests must provide mock ProjectManager
   - **Location**: `goliat/goliat/simulation_runner.py` line 55

### Internal Changes (Non-Breaking):
1. **Internal method extraction**: `_execute_isolve_attempt()` - new private method
2. **Helper classes**: New classes in `runners/` subdirectory (internal)
3. **PostSimulationHandler**: Removes simulation verification (user confirmed)

### Behavior Preserved:
- All execution behavior preserved exactly
- Memory cleanup enhanced (0.5s delay, retry warnings)
- Tests need minimal updates (provide mock ProjectManager)

## Test Updates Required

### Files to Update:
1. `goliat/tests/test_simulation_runner_core.py`
2. `goliat/tests/test_simulation_runner.py`

### Changes Needed:
- **Provide mock ProjectManager** in all tests (required parameter now)
- Mock new helper classes if they're tested indirectly
- Update mocks for `_run_isolve_manual()` if internal structure changes

## Implementation Notes

### Memory Cleanup Priority
Given the memory growth issue, prioritize:
1. **Thorough process cleanup** in ISolveProcessManager
2. **Cleanup on every retry** - don't skip cleanup
3. **Global registry cleanup** - ensure atexit works
4. **Thread cleanup** - ensure reader thread doesn't leak

### Keep-Awake Handling
- **NO comments** about licensing
- **Keep exact same behavior**: Two triggers (before retry, on progress)
- **Keep exception handling**: Print warning, continue

### Error Detection
- **Keep three-place detection**: During execution, after execution, stderr fallback
- **Prevent duplicates**: Use `detected_errors` list to avoid duplicate stderr logging
- **Log immediately**: Errors logged as soon as detected (for web interface)

### Retry Logic
- **Infinite retries**: `while True` loop, no maximum
- **Track attempts**: Start at 0, increment after each failure
- **Log retries**: "retry attempt N" message
- **Reset milestones**: Clear logged milestones on retry

## Next Steps

1. **Start Phase 1**: Extract SaveHandler (lowest risk)
2. **Test thoroughly**: Ensure memory cleanup works
3. **Gradual extraction**: One component at a time
4. **Update tests**: As components are extracted
5. **Document changes**: Precisely what/why/where for each change

