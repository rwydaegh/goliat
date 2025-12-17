# Web Monitoring Dashboard Debugging Summary

**Date:** November 29, 2025  
**Status:** Issue Not Resolved  
**Problem:** Web dashboard shows messages in large bursts with significant lag, and local GUI freezes on exit.

---

## Problem Description

### Initial Symptoms
1. **Message Ordering Issues:**
   - "Done in" and "Assign materials" messages appeared swapped on the web dashboard
   - Missing "Done in" messages for "Voxelize simulation" and "Write input file" steps

2. **Severe Lag:**
   - Web dashboard showed nothing initially
   - After a long delay, messages appeared in one large burst
   - Dashboard remained far behind the local GUI state
   - Example: Local GUI showed simulation complete, web dashboard still showing "Voxelize simulation..."

3. **Application Freeze:**
   - Clicking X on local GUI window caused it to freeze
   - Windows showed "Python does not appear to be responding"
   - Required force quit to terminate
   - When force quit, all pending messages appeared on web dashboard immediately

### Network Characteristics
- Screenshot bandwidth: **10-15 MB/min** (later reduced to **2-4 MB/min**)
- Messages were being sent successfully (confirmed via verbose logs)
- Server (Railway) logs showed batches being received and processed

---

## Investigation Findings

### 1. Message Ordering Issues

**Root Cause Identified:**
- Messages were being sent in separate batches due to rapid succession
- Race conditions on server-side when multiple batches arrived concurrently
- Timestamps could be identical for messages sent milliseconds apart

**Evidence from Logs:**
```
[DEBUG] Enqueued status:       - Done in 0.80s
[DEBUG] Enqueued status:     - Assign materials...
[DEBUG] Added to batch (size=1):       - Done in 0.80s
[DEBUG] Sending batch of 1 messages (timeout (1s))
[DEBUG] Added to batch (size=1):     - Assign materials...
```

Messages were being split into separate batches, causing potential reordering on the server.

### 2. Missing Messages

**Finding:**
- Verbose logs confirmed messages **were being sent** successfully:
  - `[DEBUG] Batch seq=8 sent successfully` (contained "Done in 8.77s" for voxelize)
  - `[DEBUG] Batch seq=13 sent successfully` (contained "Done in 4.27s" for write input file)
- Server-side logs showed batches being received
- **Conclusion:** Messages were lost or not displayed on the server side, not a client-side issue

### 3. Lag and Burst Behavior

**Root Cause:**
- Single-threaded executor (`max_workers=1`) for log requests
- When network was slow, requests would take 10+ seconds to timeout
- During this time, new messages accumulated in `log_batch` but couldn't be sent
- Once the request completed/timed out, all accumulated messages were sent in one burst
- This created a "burst" pattern: nothing → everything at once

**Evidence:**
- User reported: "At the beginning it showed nothing. After a good bit (too long) it eventually showed... in one big burst"
- When clicking X, all pending messages appeared immediately (queue was flushed)

### 4. Application Freeze

**Root Cause:**
- `stop()` method called `log_executor.shutdown(wait=True)`
- If there were pending HTTP requests in the executor queue, shutdown would wait for them
- With 10-second timeouts and retries, this could take 30+ seconds
- GUI appeared frozen during this wait

---

## Fixes Attempted

### Fix 1: Timestamp Precision Improvement
**File:** `goliat/gui/queue_gui.py`

**Change:**
- Added monotonic timestamp counter to ensure unique, always-increasing timestamps
- Prevents timestamp collisions for rapid messages

**Status:** ✅ Implemented (helps with ordering but doesn't solve lag)

---

### Fix 2: Serialized Log Requests (Race Condition Prevention)
**File:** `goliat/utils/gui_bridge.py`

**Change:**
- Split executors: `log_executor` (1 worker) for logs, `request_executor` (4 workers) for screenshots/heartbeats
- Ensures log messages are sent sequentially, preventing server-side race conditions

**Status:** ✅ Implemented (fixes ordering but doesn't solve lag)

---

### Fix 3: Sequence Numbers and Batch Indexing
**File:** `goliat/utils/gui_bridge.py`

**Change:**
- Added sequence numbers to batches for proper ordering
- Added `batch_index` to each message within a batch
- Server can sort by: sequence → timestamp → batch_index

**Status:** ✅ Already implemented (from previous commits)

---

### Fix 4: Screenshot Bandwidth Reduction
**Files:** 
- `goliat/gui/components/web_bridge_manager.py`
- `goliat/gui/components/screenshot_capture.py`

**Changes:**
- Reduced screenshot capture frequency: **1 FPS → 0.2 FPS** (every 5 seconds)
- Reduced JPEG quality: **95% → 70%**
- Bandwidth reduced from **10-15 MB/min → 2-4 MB/min**

**Status:** ✅ Implemented (reduced bandwidth but lag persists)

---

### Fix 5: Smart Batching (Adaptive to Network Latency)
**File:** `goliat/utils/gui_bridge.py`

**Change:**
- Added `last_log_future` tracking to monitor if previous request is still running
- Only sends new batch if executor is free OR backlog is critical (≥100 messages)
- Automatically adapts batch size to network speed

**Logic:**
```python
is_executor_free = self.last_log_future is None or self.last_log_future.done()
if log_batch:
    if is_backlog_critical:
        can_send = True  # Force send
    elif is_executor_free:
        # Check time/size limits
        can_send = True if conditions met
```

**Status:** ✅ Implemented (should help but issue persists)

---

### Fix 6: Adaptive Timeouts
**Files:**
- `goliat/utils/http_client.py`
- `goliat/utils/gui_bridge.py`

**Changes:**
- Reduced default timeout: **10s → 3s** for log updates
- Reduced shutdown timeout: **10s → 2s** with **1 retry** (down from 3)
- Progress updates also use 3s timeout

**Status:** ✅ Implemented (should prevent freeze, but lag issue persists)

---

## Current State

### What Works
- ✅ Messages are being sent successfully (confirmed via logs)
- ✅ Message ordering is correct (sequence numbers, timestamps, batch_index)
- ✅ No race conditions (serialized executor)
- ✅ Bandwidth reduced significantly
- ✅ Application should not freeze on exit (shorter timeout)

### What Doesn't Work
- ❌ **Lag persists:** Messages still appear in bursts with significant delay
- ❌ **Dashboard remains behind:** Web dashboard shows old state while local GUI is current
- ❌ **Burst behavior:** Long periods of no updates, then everything at once

### Current Behavior
1. Dashboard shows nothing initially
2. After delay, messages appear in one large burst
3. Dashboard remains far behind local GUI
4. When GUI is closed, all pending messages appear immediately

---

## Root Cause Analysis

### Primary Issue: Network Latency + Single-Threaded Executor

The fundamental problem is:
1. **Network is slow/unreliable** (requests taking 3-10+ seconds)
2. **Single-threaded executor** means only one request at a time
3. **Messages accumulate** while waiting for previous request
4. **Burst delivery** when request finally completes

### Why Smart Batching Didn't Solve It

Smart Batching helps by:
- Not sending new requests while one is pending
- Accumulating messages into larger batches

But it doesn't solve:
- The underlying network slowness
- The fact that we still wait for slow requests to complete
- The burst behavior when requests finally succeed

### Why Adaptive Timeouts Didn't Solve It

Shorter timeouts help by:
- Failing faster when network is down
- Preventing freeze on exit

But they don't solve:
- The fact that successful requests still take a long time
- The accumulation of messages during slow requests
- The burst delivery pattern

---

## Potential Solutions (Not Yet Implemented)

### Option 1: Parallel Executor with Backpressure
- Use multiple workers (e.g., 3-5) for log requests
- Track queue depth and throttle if too many pending
- Could improve throughput but might cause ordering issues

**Risk:** May reintroduce race conditions on server side

---

### Option 2: Client-Side Message Aggregation
- Accumulate messages for longer periods (e.g., 5-10 seconds)
- Send larger batches less frequently
- Reduces number of HTTP requests

**Risk:** Increases latency even more, messages appear even later

---

### Option 3: Server-Side Optimization
- Investigate server-side processing delays
- Check if database writes are slow
- Optimize API endpoint performance

**Note:** This requires access to `goliat-monitoring` repository/server logs

---

### Option 4: WebSocket Instead of HTTP POST
- Replace HTTP POST with WebSocket connection
- Persistent connection, lower overhead
- Real-time bidirectional communication

**Risk:** Requires significant refactoring of both client and server

---

### Option 5: Message Prioritization
- Send critical messages (progress, errors) immediately
- Batch only verbose log messages
- Use different endpoints for different priorities

**Risk:** May not solve the fundamental network latency issue

---

## Debugging Information Needed

To further diagnose, we need:

1. **Server-Side Logs (Railway):**
   - Average request processing time
   - Database write latency
   - Queue depth on server
   - Any errors or timeouts

2. **Network Diagnostics:**
   - Latency to server (ping times)
   - Packet loss
   - Bandwidth during operation
   - Connection stability

3. **Client-Side Metrics:**
   - Time between message enqueue and send
   - Time between send and success
   - Batch sizes being sent
   - Executor queue depth over time

---

## Files Modified

1. `goliat/gui/queue_gui.py` - Timestamp precision
2. `goliat/utils/gui_bridge.py` - Smart batching, serialized executor, adaptive timeouts
3. `goliat/utils/http_client.py` - Configurable timeouts
4. `goliat/gui/components/web_bridge_manager.py` - Screenshot frequency
5. `goliat/gui/components/screenshot_capture.py` - JPEG quality

---

## Commits Made

1. `fix(web): Serialize log requests to prevent race conditions and improve timestamp precision`
2. `fix(web): Reduce screenshot bandwidth usage (5s interval, 70% quality)`
3. `fix(web): Implement smart batching to adapt to network latency and prevent lag/freezes`
4. `fix(web): Adaptive timeouts to prevent freeze on exit and improve responsiveness`

---

## Next Steps

1. **Investigate server-side performance** - Check Railway logs for processing delays
2. **Monitor network conditions** - Check latency and stability to server
3. **Consider architectural changes** - WebSocket or parallel executors
4. **Add metrics/logging** - Track request times, queue depths, batch sizes
5. **Test with different network conditions** - Verify if issue is network-specific

---

## Conclusion

The issue appears to be fundamentally related to **network latency combined with a single-threaded request model**. While we've implemented several optimizations (smart batching, shorter timeouts, reduced bandwidth), the core problem persists: **slow network requests cause message accumulation and burst delivery**.

The fixes have improved:
- Message ordering (no more race conditions)
- Application stability (no freeze on exit)
- Bandwidth usage (reduced screenshot overhead)

But have not solved:
- Lag between local GUI and web dashboard
- Burst delivery pattern
- Dashboard being far behind current state

Further investigation is needed, particularly on the server-side performance and network conditions.

