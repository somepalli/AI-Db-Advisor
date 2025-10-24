# ClickHouse Analytics Setup Guide

This guide explains how to set up and use the ClickHouse analytics feature with PostgreSQL data.

## Overview

The analytics feature enables real-time analytics on your PostgreSQL data using ClickHouse, a columnar OLAP database optimized for analytical queries. The system automatically syncs data from PostgreSQL to ClickHouse and provides pre-built analytics dashboards.

## Architecture

```
PostgreSQL (OLTP)  →  Data Sync Service  →  ClickHouse (OLAP)
    UniversityDB                                  Analytics DB
      12,000 rows                                  Real-time Analytics
```

## Prerequisites

### 1. PostgreSQL Setup (Already Done)

Your existing PostgreSQL UniversityDB connection:
- **Connection String**: `postgresql://postgres:postgres@localhost:5432/UniversityDB`
- **Tables**: students, courses, enrollments, fees, hostel, librarybooks, etc.

### 2. Install ClickHouse on Windows

#### Option 1: Download Pre-built Binary (Recommended)

1. Download ClickHouse from official releases:
   ```
   https://github.com/ClickHouse/ClickHouse/releases
   ```
   - Look for: `clickhouse-windows-amd64.zip` or `clickhouse.exe`

2. Extract to a directory (e.g., `C:\clickhouse\`)

3. Start ClickHouse server:
   ```cmd
   cd C:\clickhouse
   clickhouse.exe server
   ```

4. Verify it's running:
   ```cmd
   curl http://localhost:8123
   ```
   Should return: `Ok.`

#### Option 2: Use Cloud ClickHouse

If local installation doesn't work, use ClickHouse Cloud (free tier):
- https://clickhouse.cloud
- Create a free account
- Get connection details (host, port, username, password)

### 3. Create ClickHouse Database

Once ClickHouse is running:

```cmd
# Open ClickHouse client
clickhouse.exe client

# Create database
CREATE DATABASE IF NOT EXISTS analytics;

# Verify
SHOW DATABASES;
```

## Step-by-Step Setup

### Step 1: Start Backend

```bash
cd C:\Users\chowh\Desktop\ai-db-advisor
python run.py
```

Backend should be running on http://127.0.0.1:8000

### Step 2: Start Frontend

```bash
cd C:\Users\chowh\Desktop\ai-db-advisor\tauri-app
npm run dev
```

Frontend opens on http://localhost:5173

### Step 3: Add Data Sources

#### Add PostgreSQL Connection (if not already added)

1. Go to **Connection Panel** (left side)
2. Click **"Add Connection"**
3. Fill in:
   - **ID**: `postgres-university`
   - **Engine**: PostgreSQL
   - **DSN**: `postgresql://postgres:postgres@localhost:5432/UniversityDB`
4. Click **Add**

#### Add ClickHouse Connection

1. In **Connection Panel**, click **"Add Connection"**
2. Fill in:
   - **ID**: `clickhouse-analytics`
   - **Engine**: ClickHouse
   - **DSN**: `clickhouse://default:@localhost:8123/analytics`
     - Format: `clickhouse://username:password@host:port/database`
     - Default username: `default`
     - No password by default (leave blank after colon)
     - Default port: `8123` (HTTP)
     - Database: `analytics` (created in Step 2)
3. Click **Add**

### Step 4: Switch to Analytics View

1. Click **"📊 Analytics"** button in the top header
2. You'll see a setup form:
   - **PostgreSQL Datasource ID**: Enter `postgres-university`
   - **ClickHouse Datasource ID**: Enter `clickhouse-analytics`
3. Click **"Load Analytics"**

### Step 5: Sync Data

1. The **Data Sync Status** section shows:
   - Synced Tables: 0
   - Unsynced Tables: 10 (all UniversityDB tables)
   - Out of Sync: 0

2. Click **"🔄 Sync All Tables"** button

3. Wait for sync to complete (will show progress):
   - Creates tables in ClickHouse with matching schema
   - Copies data in batches (1000 rows per batch)
   - Shows completion: "✅ Synced 10 tables (50,000+ rows)"

4. Click **"🔄 Refresh"** to update sync status

### Step 6: View Analytics

Once data is synced, click the metric buttons to view analytics:

#### 🎓 Student Enrollment
- Enrollment by year and department
- Student counts and course enrollments
- Average GPA by department

#### 💰 Fee Collection
- Total fees by status (Paid, Pending, Overdue)
- Collection statistics
- Average fee amounts

#### 📚 Library Usage
- Book loans by department
- Unique borrowers and books
- Average loan duration

#### 🏠 Hostel Occupancy
- Occupancy rates by hostel
- Capacity vs current occupancy
- Utilization percentages

#### 📖 Course Popularity
- Top 20 most popular courses
- Total enrollments per course
- Average grades

## API Endpoints

### Data Sync Endpoints

**Sync Single Table**:
```http
POST /analytics/sync/table
{
  "pg_ds_id": "postgres-university",
  "ch_ds_id": "clickhouse-analytics",
  "table_name": "public.students",
  "batch_size": 1000
}
```

**Sync All Tables**:
```http
POST /analytics/sync/all
{
  "pg_ds_id": "postgres-university",
  "ch_ds_id": "clickhouse-analytics",
  "batch_size": 1000
}
```

**Get Sync Status**:
```http
POST /analytics/sync/status
{
  "pg_ds_id": "postgres-university",
  "ch_ds_id": "clickhouse-analytics"
}
```

### Analytics Query Endpoints

**Custom Query**:
```http
POST /analytics/query
{
  "ds_id": "clickhouse-analytics",
  "query": "SELECT department_name, COUNT(*) as students FROM `public.students` GROUP BY department_name"
}
```

**Pre-built Metrics**:
```http
GET /analytics/{ds_id}/metrics/student-enrollment
GET /analytics/{ds_id}/metrics/fee-collection
GET /analytics/{ds_id}/metrics/library-usage
GET /analytics/{ds_id}/metrics/hostel-occupancy
GET /analytics/{ds_id}/metrics/course-popularity
```

## Troubleshooting

### Issue: ClickHouse not starting

**Solution 1**: Check if port 8123 is in use
```cmd
netstat -ano | findstr :8123
```

**Solution 2**: Try different port
```cmd
clickhouse.exe server --http_port=9123
```
Then update DSN: `clickhouse://default:@localhost:9123/analytics`

### Issue: Connection refused to ClickHouse

**Check**:
1. ClickHouse server is running: `curl http://localhost:8123`
2. Firewall allows port 8123
3. Database exists: `clickhouse.exe client` → `SHOW DATABASES;`

### Issue: Sync fails with "Permission denied"

**Solution**: Ensure ClickHouse has write permissions
```sql
-- In clickhouse.exe client
GRANT ALL ON analytics.* TO default;
```

### Issue: "Table not found" in analytics queries

**Cause**: Tables not synced yet

**Solution**: Click "🔄 Sync All Tables" and wait for completion

### Issue: Data out of sync

**Solution**: Run sync again (incremental sync)
```http
POST /analytics/sync/table
{
  "pg_ds_id": "postgres-university",
  "ch_ds_id": "clickhouse-analytics",
  "table_name": "public.students",
  "incremental": true,
  "timestamp_column": "enrollment_year"
}
```

## Performance Tips

### 1. Batch Size Optimization

For large tables (> 100,000 rows):
```json
{
  "batch_size": 5000
}
```

For small tables (< 10,000 rows):
```json
{
  "batch_size": 500
}
```

### 2. Incremental Sync

For tables with timestamp columns:
```json
{
  "incremental": true,
  "timestamp_column": "updated_at"
}
```

Only syncs rows newer than the last sync.

### 3. ClickHouse Indexes

Create skip indexes for frequently filtered columns:
```sql
-- In clickhouse.exe client
ALTER TABLE `public.students`
ADD INDEX idx_department department_id TYPE minmax GRANULARITY 4;
```

### 4. Table Engines

Use appropriate ClickHouse table engines:
- **MergeTree** (default): General purpose
- **SummingMergeTree**: For aggregated data
- **AggregatingMergeTree**: For pre-computed aggregates

## Advanced Usage

### Custom Analytics Queries

In the backend, add custom endpoints in `routers/analytics.py`:

```python
@router.get("/{ds_id}/metrics/custom-metric")
def get_custom_metric(ds_id: str):
    agent = resolve_agent(ds_id)

    query = """
        SELECT
            column1,
            COUNT(*) as count,
            AVG(column2) as average
        FROM table_name
        GROUP BY column1
        ORDER BY count DESC
    """

    result = agent.execute_query(query)
    return result
```

### Scheduled Sync (Future Enhancement)

Set up a cron job or scheduled task to sync periodically:

**Windows Task Scheduler**:
```cmd
schtasks /create /tn "ClickHouse Sync" /tr "python sync_script.py" /sc daily /st 02:00
```

**sync_script.py**:
```python
import requests

response = requests.post('http://127.0.0.1:8000/analytics/sync/all', json={
    'pg_ds_id': 'postgres-university',
    'ch_ds_id': 'clickhouse-analytics'
})
print(response.json())
```

## Benefits of ClickHouse Analytics

1. **Fast Analytics**: 100x faster than PostgreSQL for OLAP queries
2. **Columnar Storage**: Efficient compression and scanning
3. **Real-time Insights**: Query large datasets in milliseconds
4. **Separate Workloads**: Analytics don't impact OLTP performance
5. **Scalability**: Handles billions of rows effortlessly

## Example Queries

### Top 10 Students by GPA
```sql
SELECT
    s.first_name,
    s.last_name,
    d.department_name,
    AVG(CASE WHEN e.grade = 'A' THEN 4.0
             WHEN e.grade = 'B' THEN 3.0
             WHEN e.grade = 'C' THEN 2.0
             WHEN e.grade = 'D' THEN 1.0
             ELSE 0.0 END) as gpa
FROM `public.students` s
LEFT JOIN `public.departments` d ON s.department_id = d.department_id
LEFT JOIN `public.enrollments` e ON s.student_id = e.student_id
GROUP BY s.first_name, s.last_name, d.department_name
ORDER BY gpa DESC
LIMIT 10
```

### Monthly Fee Collection Trends
```sql
SELECT
    toYYYYMM(due_date) as month,
    status,
    COUNT(*) as count,
    SUM(amount) as total_amount
FROM `public.fees`
WHERE due_date >= today() - INTERVAL 12 MONTH
GROUP BY month, status
ORDER BY month DESC
```

### Department-wise Resource Usage
```sql
SELECT
    d.department_name,
    COUNT(DISTINCT s.student_id) as students,
    COUNT(DISTINCT c.course_id) as courses,
    COUNT(DISTINCT bl.book_id) as books_borrowed,
    COUNT(DISTINCT ha.allocation_id) as hostel_allocations
FROM `public.departments` d
LEFT JOIN `public.students` s ON d.department_id = s.department_id
LEFT JOIN `public.courses` c ON d.department_id = c.department_id
LEFT JOIN `public.bookloans` bl ON s.student_id = bl.student_id
LEFT JOIN `public.hostelallocation` ha ON s.student_id = ha.student_id
GROUP BY d.department_name
ORDER BY students DESC
```

## Next Steps

1. **✅ Complete**: Backend implementation
2. **✅ Complete**: Frontend dashboard
3. **✅ Complete**: Data sync service
4. **⏳ Pending**: Install ClickHouse server
5. **⏳ Pending**: Test end-to-end workflow
6. **Future**: Scheduled sync automation
7. **Future**: Custom dashboard builder
8. **Future**: Export reports to PDF/Excel

## Support

For issues or questions:
1. Check ClickHouse logs: `clickhouse.exe server` output
2. Check backend logs: `python run.py` output
3. Check browser console (F12) for frontend errors
4. Verify API calls in Network tab

## Resources

- ClickHouse Docs: https://clickhouse.com/docs
- ClickHouse SQL Reference: https://clickhouse.com/docs/en/sql-reference
- ClickHouse Performance: https://clickhouse.com/docs/en/operations/performance
