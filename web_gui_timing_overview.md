# Web GUI Update Timing Overview

This document provides a comprehensive overview of all periodic timers and intervals related to updating the GUI to the web dashboard.

## Python Side (GUI → Web)

### 1. Progress Sync Timer
- **Location**: `goliat/gui/progress_gui.py:193`
- **Interval**: **200ms** (5 times per second)
- **Purpose**: Reads actual GUI progress bar values and sends them to web dashboard
- **Function**: `web_bridge_manager.sync_progress()`
- **What it sends**: Overall progress and stage progress (if > 0)
- **Note**: This ensures web dashboard shows actual progress even if explicit progress messages aren't sent

### 2. Screenshot Capture Timer
- **Location**: `goliat/gui/components/web_bridge_manager.py:136`
- **Interval**: **5000ms** (5 seconds = 0.2 FPS)
- **Purpose**: Captures GUI tab screenshots and sends them to web
- **Function**: `_capture_and_send_screenshots()`
- **What it sends**: JPEG screenshots of all GUI tabs (Timings, Piecharts, Time Remaining, Overall Progress, System Utilization)
- **Note**: Reduced from 1 second to 5 seconds to save bandwidth

### 3. Heartbeat Timer
- **Location**: `goliat/utils/gui_bridge.py:190, 207`
- **Interval**: **30 seconds**
- **Purpose**: Registers/updates worker status on web dashboard
- **Function**: `_send_heartbeat_async()`
- **What it sends**: Worker status, system info (GPU, CPU, RAM, hostname)
- **Note**: Also sent on initial connection

### 4. Log Batch Interval
- **Location**: `goliat/utils/gui_bridge.py:195, 217`
- **Interval**: **50ms** (20 times per second)
- **Purpose**: Time-based trigger for sending batched log messages
- **Function**: `_send_log_batch()`
- **What it sends**: Batched log messages (up to 10 messages per batch)
- **Note**: Also triggers when batch reaches 10 messages

### 5. Progress Update Throttle
- **Location**: `goliat/utils/gui_bridge.py:191, 249`
- **Interval**: **20ms** (50 Hz = throttle_interval_fast)
- **Purpose**: Throttles progress/profiler updates to prevent overwhelming API
- **Function**: Applied to `overall_progress`, `stage_progress`, `profiler_update` messages
- **What it does**: Sleeps if less than 20ms since last throttled send
- **Note**: Ensures max 50 progress updates per second

### 6. Queue Processing Timer
- **Location**: `goliat/gui/progress_gui.py:168`
- **Interval**: **100ms** (10 times per second)
- **Purpose**: Processes messages from worker process queue
- **Function**: `queue_handler.process_queue()`
- **What it does**: Polls multiprocessing queue and forwards messages to web bridge
- **Note**: Not directly web-related, but affects when messages reach web bridge

### 7. Progress Animation Timer
- **Location**: `goliat/gui/components/progress_animation.py:78`
- **Interval**: **50ms** (20 times per second, when active)
- **Purpose**: Smoothly animates progress bar during long-running tasks
- **Function**: `progress_animation.update()`
- **What it does**: Updates progress bar value based on elapsed time
- **Note**: Only active when animation is running (not always on)

## Web Side (Frontend)

### 1. Screenshot Refresh Interval
- **Location**: `goliat-monitoring/src/app/workers/[id]/page.tsx:52`
- **Interval**: **60000ms** (60 seconds = 1 minute)
- **Purpose**: Auto-refreshes screenshot images to bust browser cache
- **Function**: Updates `imageTimestamps` state
- **What it does**: Triggers re-fetch of screenshot images
- **Note**: Only runs if worker is active (not IDLE/STALE)

### 2. SSE Connection Timeout
- **Location**: `goliat-monitoring/src/app/workers/[id]/page.tsx:447`
- **Interval**: **3000ms** (3 seconds)
- **Purpose**: Fallback timeout if SSE doesn't connect
- **Function**: Starts polling fallback if SSE fails
- **What it does**: Switches to polling if SSE connection fails
- **Note**: Cleared if SSE connects successfully

### 3. Polling Fallback Interval
- **Location**: `goliat-monitoring/src/app/workers/[id]/page.tsx:311`
- **Interval**: **1000ms** (1 second)
- **Purpose**: Fallback polling when SSE is unavailable
- **Function**: `fetchWorkerDetails()` - fetches worker state from API
- **What it does**: Polls `/api/workers/[id]` endpoint for updates
- **Note**: Only used if SSE fails to connect

### 4. Workers List Refresh
- **Location**: `goliat-monitoring/src/app/workers/page.tsx:66`
- **Interval**: **3000ms** (3 seconds)
- **Purpose**: Refreshes list of all workers
- **Function**: `fetchWorkers()` - fetches worker list from API
- **What it does**: Polls `/api/workers` endpoint
- **Note**: Used on workers list page, not detail page

## Summary Table

| Component | Location | Interval | Frequency | Purpose |
|-----------|----------|----------|-----------|---------|
| **Progress Sync** | Python GUI | 200ms | 5/sec | Sync progress bars to web |
| **Screenshots** | Python GUI | 5000ms | 0.2/sec | Capture/send GUI screenshots |
| **Heartbeat** | Python Bridge | 30000ms | 0.033/sec | Worker registration/status |
| **Log Batching** | Python Bridge | 50ms | 20/sec | Batch log messages |
| **Progress Throttle** | Python Bridge | 20ms | 50/sec max | Throttle progress updates |
| **Queue Processing** | Python GUI | 100ms | 10/sec | Process worker messages |
| **Animation** | Python GUI | 50ms | 20/sec (when active) | Animate progress bars |
| **Screenshot Refresh** | Web Frontend | 60000ms | 0.017/sec | Refresh screenshot images |
| **SSE Timeout** | Web Frontend | 3000ms | One-time | SSE connection timeout |
| **Polling Fallback** | Web Frontend | 1000ms | 1/sec | Fallback if SSE fails |
| **Workers List** | Web Frontend | 3000ms | 0.33/sec | Refresh workers list |

## Key Insights

1. **Most Frequent**: Progress throttle (50 Hz) and log batching (20 Hz) ensure real-time updates
2. **Least Frequent**: Screenshot refresh (1/min) and heartbeat (1/30s) minimize bandwidth
3. **Real-time Updates**: SSE provides instant updates, polling is fallback only
4. **Progress Sync**: 200ms interval ensures web dashboard stays in sync with GUI
5. **Animation**: 50ms updates provide smooth visual feedback but don't directly affect web

## Recent Changes

- **2025-12-XX**: Progress sync timer reduced from 2000ms to 200ms (10x faster) to catch explicit updates faster and reduce race conditions
