# AI DB Advisor - Quick Start Guide

## Server Operations

### Start Server (Always Use This)
```bash
myenv\Scripts\python.exe run.py
```

Or use the batch file:
```bash
start_backend.bat
```

**Verify startup logs show**:
```
[run.py] Using myenv Python: C:\Users\chowh\Desktop\ai-db-advisor\myenv\Scripts\python.exe
INFO: Uvicorn running on http://127.0.0.1:8000
```

### Check Server Health
```bash
curl http://127.0.0.1:8000/healthz
```

Expected response: `{"ok":true}`

## Testing Analytics Endpoints

### 1. Fee Collection Metrics
```bash
curl http://127.0.0.1:8000/analytics/duckdb-analytics/metrics/fee-collection
```

Shows: Fee status (Paid/Pending/Overdue/Partial), counts, total amounts, averages

### 2. Student Enrollment Metrics
```bash
curl http://127.0.0.1:8000/analytics/duckdb-analytics/metrics/student-enrollment
```

Shows: Enrollment by year and department, student counts, courses taken, GPA

### 3. Library Usage Metrics
```bash
curl http://127.0.0.1:8000/analytics/duckdb-analytics/metrics/library-usage
```

Shows: Total loans, unique borrowers, unique books, average loan days by department

### 4. Hostel Occupancy Metrics
```bash
curl http://127.0.0.1:8000/analytics/duckdb-analytics/metrics/hostel-occupancy
```

Shows: Hostel capacity, current occupancy, occupancy rate percentage

### 5. Course Popularity Metrics
```bash
curl http://127.0.0.1:8000/analytics/duckdb-analytics/metrics/course-popularity
```

Shows: Top 20 courses by enrollment, semesters offered, average grades

## Status

✅ **ALL SYSTEMS OPERATIONAL**

- Server: ✅ Running on http://127.0.0.1:8000
- Environment: ✅ Using myenv Python
- Logging: ✅ Comprehensive HTTP logging enabled
- Analytics: ✅ All 5 endpoints working
- Sync: ✅ Code ready

---

**Last Updated**: 2025-10-14
