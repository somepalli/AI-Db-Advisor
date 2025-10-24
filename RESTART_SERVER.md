# How to Restart the Backend Server

## Problem
You're getting error: `DuckDBAgent.create_table_from_schema() got an unexpected keyword argument 'engine'`

## Root Cause
The FastAPI server is still running with **old cached code in memory**. Even though the file has been updated, Python has already imported the old version.

## Solution: Restart the Server

### Method 1: Stop and Restart (Recommended)

#### Step 1: Stop the Running Server
If you started with `python run.py` or `start_backend.bat`:

**Windows**:
1. Find the terminal window running the server
2. Press `Ctrl + C` to stop it
3. Wait for "Shutting down AI DB Advisor..." message

**Or kill the process**:
```bash
# Find the process
tasklist | findstr python

# Kill it (replace PID with actual process ID)
taskkill /PID <process_id> /F
```

#### Step 2: Start the Server Again
```bash
# Using batch file (recommended)
start_backend.bat

# Or directly
myenv\Scripts\python.exe run.py
```

### Method 2: Auto-Reload (If Enabled)

If you're running with `reload=True` (which is default in `run.py`), the server should automatically reload when files change. However, sometimes it doesn't pick up all changes.

**To force reload**:
1. Open `run.py` in an editor
2. Add a space somewhere and save it
3. The server should auto-reload and show:
   ```
   WARNING: WatchFiles detected changes in 'run.py'. Reloading...
   ```

### Method 3: Clear Python Cache and Restart

Sometimes Python's `.pyc` cache files need to be cleared:

```bash
# Delete all .pyc files
powershell -Command "Get-ChildItem -Path '.venv' -Filter '*.pyc' -Recurse | Remove-Item -Force"

# Delete __pycache__ directories
powershell -Command "Get-ChildItem -Path '.venv' -Directory -Filter '__pycache__' -Recurse | Remove-Item -Recurse -Force"

# Now restart the server
myenv\Scripts\python.exe run.py
```

## Verify the Fix

After restarting, you should see in the logs:
```
INFO: Started server process
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8000
```

Test with curl:
```bash
curl -X POST http://127.0.0.1:8000/analytics/sync/all \
  -H "Content-Type: application/json" \
  -d "{\"pg_ds_id\": \"Demo-DB-Post\", \"ch_ds_id\": \"duckdb-analytics\"}"
```

You should now see detailed sync logs instead of the error!

## Why This Happens

Python caches imported modules in memory for performance. When you update a file while the server is running:

1. ✅ File on disk is updated
2. ❌ But Python's `sys.modules` cache still has the old version
3. ❌ FastAPI continues using the cached version

### Auto-Reload Limitations

FastAPI's auto-reload (via uvicorn) **should** detect changes, but:
- It may miss changes if file is edited too quickly
- Some IDEs save files in a way that bypasses file watchers
- Changes in nested modules may not trigger reload

**Best Practice**: Always do a manual restart after significant code changes to ensure clean state.

## Troubleshooting

### Issue: Server won't stop with Ctrl+C
```bash
# Force kill on Windows
taskkill /IM python.exe /F

# Or kill specific port
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Issue: Port 8000 already in use
```bash
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill it
taskkill /PID <PID> /F
```

### Issue: Still getting the same error after restart
1. Check you're killing the right process:
   ```bash
   tasklist | findstr python
   ```

2. Verify the file has the correct signature:
   ```bash
   powershell -Command "Get-Content '.venv\app\services\duckdb_agent.py' | Select-String -Pattern 'def create_table_from_schema' -Context 0,2"
   ```

   Should show:
   ```python
   def create_table_from_schema(self, table_name: str, schema: List[Dict[str, str]],
                                 engine: Optional[str] = None, order_by: Optional[str] = None) -> Dict[str, Any]:
   ```

3. Clear Python cache and restart again:
   ```bash
   # Clear cache
   powershell -Command "Get-ChildItem -Path '.venv' -Filter '*.pyc' -Recurse | Remove-Item -Force"

   # Restart
   myenv\Scripts\python.exe run.py
   ```

## Expected Behavior After Fix

Once the server restarts with the correct code, your sync API call should work and you'll see:

```
2025-10-14 15:30:00 - app.services.data_sync - INFO - ================================================================================
2025-10-14 15:30:00 - app.services.data_sync - INFO - Starting sync_all_tables operation
2025-10-14 15:30:00 - app.services.data_sync - INFO - ================================================================================
2025-10-14 15:30:00 - app.services.data_sync - INFO - Found 10 tables in PostgreSQL
2025-10-14 15:30:00 - app.services.data_sync - INFO - [1/10] Syncing table: public.students
...
```

Instead of:
```
ERROR: DuckDBAgent.create_table_from_schema() got an unexpected keyword argument 'engine'
```

---

**TL;DR**: Stop the server (Ctrl+C), then restart with `myenv\Scripts\python.exe run.py` or `start_backend.bat`
