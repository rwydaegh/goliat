# Testing Dashboard Locally

## Quick Test Setup

### Step 1: Run GOLIAT with Web Monitoring Enabled

From the `goliat/` directory, run:

```bash
# Set environment variables
set GOLIAT_MONITORING_URL=https://goliat-monitoring.vercel.app
set GOLIAT_WEBGUI_ENABLED=true

# Run the test study
goliat study test
```

**Note:** The `GOLIAT_MACHINE_ID` will be auto-detected (your local IP).

### Step 2: What You Should See

#### On Your Laptop (GOLIAT GUI):
- Normal GOLIAT GUI window opens
- Progress bars, logs, ETA all work normally
- Study runs with software kernel (slower but works without GPU)

#### On Dashboard (https://goliat-monitoring.vercel.app):

1. **Workers Page** (`/workers`):
   - Your machine should appear within 5 seconds
   - Status light: **Green** (running)
   - Shows your IP address as the worker name
   - Progress bar showing study progress
   - Last seen: updating every few seconds

2. **Worker Detail Page** (click on your worker):
   - Overall progress bar (0% → 100%)
   - Stage progress bar (Setup → Run → Extract)
   - Log viewer showing status messages:
     - "Starting study..."
     - "Loading phantom..."
     - "Running simulation..."
     - "Extracting results..."
   - ETA display (if available)

3. **Real-time Updates**:
   - Progress bars update every 2-3 seconds
   - Logs appear as they happen
   - Status changes from "idle" → "running" → "idle" when done

### Step 3: Verify It's Working

Check the browser console (F12) - you should see:
- API calls to `/api/workers` every 3 seconds
- API calls to `/api/gui-update` every few seconds
- No errors

### Troubleshooting

**Worker doesn't appear:**
- Check GOLIAT_MONITORING_URL is set correctly
- Check GOLIAT_WEBGUI_ENABLED=true
- Verify `requests` library is installed: `pip install requests`
- Check GOLIAT logs for WebGUIBridge errors

**No progress updates:**
- Check browser console for API errors
- Verify network connectivity to Vercel
- Check that GUI is actually running (not headless mode)

**Connection errors:**
- Make sure dashboard is deployed: https://goliat-monitoring.vercel.app
- Check environment variables are set correctly

## Expected Test Duration

With software kernel, this simple test should take:
- Setup: ~1-2 minutes
- Simulation: ~5-10 minutes (depends on CPU)
- Extract: ~30 seconds
- **Total: ~7-13 minutes**

You can watch the progress in real-time on the dashboard!

