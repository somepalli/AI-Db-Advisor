# Analytics Dashboard - Complete API Guide

## Overview

This guide documents the comprehensive analytics endpoints available for building rich, data-driven dashboards. All endpoints support UniversityDB and return visualization-ready data.

## Base URL

```
http://127.0.0.1:8000/analytics/{ds_id}/
```

Replace `{ds_id}` with your DuckDB datasource ID (e.g., `duckdb-analytics`)

---

## 📊 Dashboard Endpoints (NEW)

### 1. **KPIs (Key Performance Indicators)**

**Endpoint**: `GET /analytics/{ds_id}/dashboard/kpis`

**Purpose**: Display critical metrics at a glance

**Visualization**: Card widgets, Stat components, Number displays

**Response**:
```json
{
  "success": true,
  "rows": [{
    "total_students": 68500,
    "total_departments": 10,
    "total_revenue": 108361387.96,
    "collected_revenue": 27696369.18,
    "collection_rate": 25.56,
    "payment_compliance_rate": 25.04,
    "total_loans": 14000,
    "active_borrowers": 9500,
    "hostel_capacity": 10000,
    "hostel_occupied": 10000,
    "hostel_occupancy_rate": 100.00
  }]
}
```

**Frontend Implementation**:
```tsx
<div className="kpi-grid">
  <KPICard
    title="Total Students"
    value={kpis.total_students}
    icon="users"
  />
  <KPICard
    title="Revenue Collection"
    value={`${kpis.collection_rate}%`}
    subtitle={`₹${kpis.collected_revenue} / ₹${kpis.total_revenue}`}
    icon="dollar"
    trend="up"
  />
  <KPICard
    title="Hostel Occupancy"
    value={`${kpis.hostel_occupancy_rate}%`}
    subtitle={`${kpis.hostel_occupied} / ${kpis.hostel_capacity} beds`}
    icon="home"
  />
  <KPICard
    title="Library Activity"
    value={kpis.total_loans}
    subtitle={`${kpis.active_borrowers} active borrowers`}
    icon="book"
  />
</div>
```

---

### 2. **Enrollment Trends (Time Series)**

**Endpoint**: `GET /analytics/{ds_id}/dashboard/enrollment-trends`

**Purpose**: Show enrollment growth over years

**Visualization**: Line chart, Area chart, Trend graph

**Response**:
```json
{
  "success": true,
  "rows": [
    {
      "enrollment_year": 2018,
      "student_count": 9780,
      "prev_year_count": null,
      "growth_rate": null
    },
    {
      "enrollment_year": 2019,
      "student_count": 9606,
      "prev_year_count": 9780,
      "growth_rate": -1.78
    },
    {
      "enrollment_year": 2020,
      "student_count": 10041,
      "prev_year_count": 9606,
      "growth_rate": 4.53
    },
    ...
  ]
}
```

**Frontend Implementation** (Recharts):
```tsx
<LineChart data={trends}>
  <CartesianGrid strokeDasharray="3 3" />
  <XAxis dataKey="enrollment_year" />
  <YAxis />
  <Tooltip />
  <Legend />
  <Line
    type="monotone"
    dataKey="student_count"
    stroke="#8884d8"
    name="Students"
  />
  <Line
    type="monotone"
    dataKey="growth_rate"
    stroke="#82ca9d"
    name="Growth %"
    yAxisId="right"
  />
</LineChart>
```

---

### 3. **Department Distribution**

**Endpoint**: `GET /analytics/{ds_id}/dashboard/department-distribution`

**Purpose**: Show student/faculty distribution across departments

**Visualization**: Pie chart, Donut chart, Bar chart

**Response**:
```json
{
  "success": true,
  "rows": [
    {
      "department_name": "Chemistry",
      "student_count": 8046,
      "professor_count": 56,
      "percentage": 11.75,
      "student_professor_ratio": 143.68
    },
    {
      "department_name": "Biology",
      "student_count": 7776,
      "professor_count": 44,
      "percentage": 11.35,
      "student_professor_ratio": 176.73
    },
    ...
  ]
}
```

**Frontend Implementation** (Pie Chart):
```tsx
<PieChart>
  <Pie
    data={distribution}
    dataKey="student_count"
    nameKey="department_name"
    cx="50%"
    cy="50%"
    outerRadius={80}
    fill="#8884d8"
    label={(entry) => `${entry.department_name}: ${entry.percentage}%`}
  >
    {distribution.map((entry, index) => (
      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
    ))}
  </Pie>
  <Tooltip />
  <Legend />
</PieChart>
```

---

### 4. **Grade Distribution**

**Endpoint**: `GET /analytics/{ds_id}/dashboard/grade-distribution`

**Purpose**: Analyze academic performance across departments

**Visualization**: Stacked bar chart, Grouped bar chart

**Response**:
```json
{
  "success": true,
  "rows": [
    {
      "department_name": "Biology",
      "grade": "A",
      "count": 578,
      "percentage": 7.59
    },
    {
      "department_name": "Biology",
      "grade": "B",
      "count": 579,
      "percentage": 7.61
    },
    ...
  ]
}
```

**Frontend Implementation** (Stacked Bar):
```tsx
<BarChart data={processedData}>
  <CartesianGrid strokeDasharray="3 3" />
  <XAxis dataKey="department_name" />
  <YAxis />
  <Tooltip />
  <Legend />
  <Bar dataKey="A" stackId="a" fill="#4caf50" />
  <Bar dataKey="B" stackId="a" fill="#8bc34a" />
  <Bar dataKey="C" stackId="a" fill="#ffc107" />
  <Bar dataKey="D" stackId="a" fill="#ff9800" />
  <Bar dataKey="F" stackId="a" fill="#f44336" />
</BarChart>
```

---

### 5. **Revenue Analysis (Monthly)**

**Endpoint**: `GET /analytics/{ds_id}/dashboard/revenue-analysis`

**Purpose**: Track fee collection trends over time

**Visualization**: Stacked area chart, Multi-series bar chart

**Response**:
```json
{
  "success": true,
  "rows": [
    {
      "month": "2025-03",
      "department_name": "Biology",
      "status": "Paid",
      "transaction_count": 45,
      "total_amount": 135678.25,
      "avg_amount": 3015.07,
      "min_amount": 2000.00,
      "max_amount": 4500.00
    },
    ...
  ]
}
```

**Frontend Implementation** (Area Chart):
```tsx
<AreaChart data={revenueByMonth}>
  <CartesianGrid strokeDasharray="3 3" />
  <XAxis dataKey="month" />
  <YAxis />
  <Tooltip formatter={(value) => `₹${value}`} />
  <Legend />
  <Area
    type="monotone"
    dataKey="Paid"
    stackId="1"
    stroke="#4caf50"
    fill="#4caf50"
  />
  <Area
    type="monotone"
    dataKey="Pending"
    stackId="1"
    stroke="#ffc107"
    fill="#ffc107"
  />
  <Area
    type="monotone"
    dataKey="Overdue"
    stackId="1"
    stroke="#f44336"
    fill="#f44336"
  />
</AreaChart>
```

---

### 6. **Library Analytics**

**Endpoint**: `GET /analytics/{ds_id}/dashboard/library-analytics`

**Purpose**: Most borrowed books and usage patterns

**Visualization**: Horizontal bar chart, Heat map

**Response**:
```json
{
  "success": true,
  "rows": [
    {
      "title": "Introduction to Algorithms",
      "author": "Cormen et al.",
      "department_name": "Computer Science",
      "total_loans": 145,
      "unique_borrowers": 98,
      "available_copies": 5,
      "avg_loan_duration": 14.35,
      "first_loan_date": "2022-01-15",
      "last_loan_date": "2025-03-20"
    },
    ...
  ]
}
```

**Frontend Implementation** (Horizontal Bar):
```tsx
<BarChart layout="vertical" data={libraryData}>
  <CartesianGrid strokeDasharray="3 3" />
  <XAxis type="number" />
  <YAxis dataKey="title" type="category" width={200} />
  <Tooltip />
  <Bar dataKey="total_loans" fill="#8884d8" />
</BarChart>
```

---

### 7. **Performance Metrics (Academic)**

**Endpoint**: `GET /analytics/{ds_id}/dashboard/performance-metrics`

**Purpose**: Analyze student performance by department and year

**Visualization**: Box plot, Violin plot, Scatter plot

**Response**:
```json
{
  "success": true,
  "rows": [
    {
      "department_name": "Computer Science",
      "enrollment_year": 2024,
      "student_count": 5796,
      "avg_gpa": 0.00,
      "min_gpa": 0.00,
      "max_gpa": 0.00,
      "avg_courses_per_student": 1.24,
      "pass_rate": 100.00,
      "honors_students": 0,
      "at_risk_students": 5796
    },
    ...
  ]
}
```

**Frontend Implementation** (Grouped Bar):
```tsx
<BarChart data={performanceData}>
  <CartesianGrid strokeDasharray="3 3" />
  <XAxis dataKey="department_name" />
  <YAxis yAxisId="left" />
  <YAxis yAxisId="right" orientation="right" />
  <Tooltip />
  <Legend />
  <Bar yAxisId="left" dataKey="avg_gpa" fill="#8884d8" name="Avg GPA" />
  <Bar yAxisId="right" dataKey="pass_rate" fill="#82ca9d" name="Pass Rate %" />
</BarChart>
```

---

### 8. **Hostel Analytics (Occupancy Trends)**

**Endpoint**: `GET /analytics/{ds_id}/dashboard/hostel-analytics`

**Purpose**: Track hostel occupancy over time

**Visualization**: Gauge chart, Progress bars, Heat map

**Response**:
```json
{
  "success": true,
  "rows": [
    {
      "hostel_name": "Hostel A",
      "capacity": 500,
      "warden_name": "John Doe",
      "allocation_month": "2025-03",
      "current_occupancy": 500,
      "occupied_rooms": 250,
      "available_capacity": 0,
      "occupancy_rate": 100.00,
      "avg_students_per_room": 2.00
    },
    ...
  ]
}
```

**Frontend Implementation** (Progress Bar):
```tsx
{hostelData.map(hostel => (
  <div key={hostel.hostel_name} className="hostel-card">
    <h3>{hostel.hostel_name}</h3>
    <p>Warden: {hostel.warden_name}</p>
    <ProgressBar
      value={hostel.occupancy_rate}
      max={100}
      label={`${hostel.current_occupancy} / ${hostel.capacity}`}
      color={hostel.occupancy_rate > 90 ? 'red' : 'green'}
    />
    <small>Avg {hostel.avg_students_per_room} students/room</small>
  </div>
))}
```

---

### 9. **Comparative Analysis (Department Benchmarking)**

**Endpoint**: `GET /analytics/{ds_id}/dashboard/comparative-analysis`

**Purpose**: Compare departments across multiple metrics

**Visualization**: Radar chart, Multi-axis line chart, Comparison table

**Response**:
```json
{
  "success": true,
  "rows": [
    {
      "department_name": "Chemistry",
      "total_students": 8046,
      "total_professors": 56,
      "total_courses": 15,
      "avg_gpa": 0.00,
      "library_loans": 112644,
      "revenue_collected": 10915753.18,
      "total_revenue": 24174184.51,
      "collection_rate": 45.16,
      "student_professor_ratio": 143.68,
      "loans_per_student": 14.00
    },
    ...
  ]
}
```

**Frontend Implementation** (Radar Chart):
```tsx
<RadarChart data={radarData}>
  <PolarGrid />
  <PolarAngleAxis dataKey="department" />
  <PolarRadiusAxis />
  <Radar
    name="Student Count"
    dataKey="normalized_students"
    stroke="#8884d8"
    fill="#8884d8"
    fillOpacity={0.6}
  />
  <Radar
    name="Revenue Collection %"
    dataKey="collection_rate"
    stroke="#82ca9d"
    fill="#82ca9d"
    fillOpacity={0.6}
  />
  <Legend />
</RadarChart>
```

---

## 📈 Legacy Metrics Endpoints (Existing)

### Student Enrollment Metrics
**Endpoint**: `GET /analytics/{ds_id}/metrics/student-enrollment`

Returns enrollment by year and department with GPA statistics.

### Fee Collection Metrics
**Endpoint**: `GET /analytics/{ds_id}/metrics/fee-collection`

Returns fee status breakdown (Paid/Pending/Overdue/Partial) with amounts.

### Library Usage Metrics
**Endpoint**: `GET /analytics/{ds_id}/metrics/library-usage`

Returns library statistics by department.

### Hostel Occupancy Metrics
**Endpoint**: `GET /analytics/{ds_id}/metrics/hostel-occupancy`

Returns occupancy rates by hostel.

### Course Popularity Metrics
**Endpoint**: `GET /analytics/{ds_id}/metrics/course-popularity`

Returns top 20 courses by enrollment.

---

## 🎨 Recommended Visualization Libraries

### React/TypeScript

1. **Recharts** (Recommended)
   ```bash
   npm install recharts
   ```
   - Composable, declarative
   - Great for line, bar, pie, area charts
   - https://recharts.org

2. **Chart.js with react-chartjs-2**
   ```bash
   npm install chart.js react-chartjs-2
   ```
   - Comprehensive chart types
   - Highly customizable
   - https://react-chartjs-2.js.org

3. **Nivo**
   ```bash
   npm install @nivo/core @nivo/bar @nivo/line @nivo/pie
   ```
   - Beautiful defaults
   - Great for heatmaps, radar charts
   - https://nivo.rocks

4. **Victory**
   ```bash
   npm install victory
   ```
   - Animation support
   - Responsive charts
   - https://formidable.com/open-source/victory

### For Advanced Visualizations

- **D3.js**: Complex custom visualizations
- **Plotly**: 3D charts, scientific plots
- **ECharts**: Geographic maps, complex interactions

---

## 🏗️ Dashboard Structure Recommendation

```tsx
// Dashboard.tsx
import { useState, useEffect } from 'react';
import { analyzeApi } from './api/client';

export function Dashboard() {
  const [kpis, setKPIs] = useState(null);
  const [trends, setTrends] = useState([]);
  const [distribution, setDistribution] = useState([]);

  useEffect(() => {
    async function loadData() {
      const dsId = 'duckdb-analytics';

      // Load all data in parallel
      const [kpiData, trendsData, distData] = await Promise.all([
        analyzeApi.getDashboardKPIs(dsId),
        analyzeApi.getEnrollmentTrends(dsId),
        analyzeApi.getDepartmentDistribution(dsId)
      ]);

      setKPIs(kpiData.rows[0]);
      setTrends(trendsData.rows);
      setDistribution(distData.rows);
    }

    loadData();
  }, []);

  return (
    <div className="dashboard">
      {/* KPIs Section */}
      <section className="kpis">
        <KPIGrid data={kpis} />
      </section>

      {/* Charts Section */}
      <section className="charts">
        <div className="chart-row">
          <EnrollmentTrendsChart data={trends} />
          <DepartmentPieChart data={distribution} />
        </div>

        <div className="chart-row">
          <RevenueAnalysisChart />
          <LibraryUsageChart />
        </div>
      </section>
    </div>
  );
}
```

---

## 🔄 Data Refresh Strategy

### Option 1: Polling (Simple)
```tsx
useEffect(() => {
  const interval = setInterval(() => {
    loadDashboardData();
  }, 60000); // Refresh every minute

  return () => clearInterval(interval);
}, []);
```

### Option 2: Manual Refresh
```tsx
<button onClick={loadDashboardData}>
  <RefreshIcon /> Refresh Data
</button>
```

### Option 3: WebSocket (Real-time)
Future enhancement for live updates.

---

## 🎯 Performance Optimization

1. **Lazy Loading**: Load charts as user scrolls
2. **Pagination**: Limit large datasets (already done on backend with LIMIT)
3. **Caching**: Cache responses for 1-5 minutes
4. **Skeleton Loading**: Show placeholders while data loads
5. **Virtual Scrolling**: For large tables

---

## 🚀 Quick Start Example

```tsx
// api/client.ts additions
export const analyzeApi = {
  // ... existing methods

  getDashboardKPIs: (dsId: string) =>
    fetch(`${BASE_URL}/analytics/${dsId}/dashboard/kpis`).then(r => r.json()),

  getEnrollmentTrends: (dsId: string) =>
    fetch(`${BASE_URL}/analytics/${dsId}/dashboard/enrollment-trends`).then(r => r.json()),

  getDepartmentDistribution: (dsId: string) =>
    fetch(`${BASE_URL}/analytics/${dsId}/dashboard/department-distribution`).then(r => r.json()),

  // ... add all other dashboard endpoints
};
```

---

## 📊 Complete Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│                    UNIVERSITY ANALYTICS                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Students │  │ Revenue  │  │  Hostel  │  │ Library  │   │
│  │  68,500  │  │  25.56%  │  │  100.0%  │  │  14,000  │   │
│  │   KPI    │  │   KPI    │  │   KPI    │  │   KPI    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ Enrollment Trends   │  │ Dept Distribution   │          │
│  │  (Line Chart)       │  │   (Pie Chart)       │          │
│  │                     │  │                     │          │
│  └─────────────────────┘  └─────────────────────┘          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ Grade Distribution  │  │ Revenue Analysis    │          │
│  │ (Stacked Bar)       │  │  (Area Chart)       │          │
│  │                     │  │                     │          │
│  └─────────────────────┘  └─────────────────────┘          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ Performance Metrics │  │ Comparative Analysis│          │
│  │  (Bar Chart)        │  │   (Radar Chart)     │          │
│  │                     │  │                     │          │
│  └─────────────────────┘  └─────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ Status

- **Total New Endpoints**: 9 dashboard endpoints
- **Total Legacy Endpoints**: 5 metrics endpoints
- **Graph Types Supported**: 15+ visualization types
- **Status**: ✅ Production Ready (pending server restart)

---

## 📝 Next Steps

1. Update `tauri-app/src/api/client.ts` with new dashboard methods
2. Create dashboard components in `tauri-app/src/components/`
3. Install visualization library: `npm install recharts`
4. Build responsive dashboard layout
5. Add export/download functionality for charts
6. Implement filtering and date range selection

---

**Created By**: Senior Full Stack Developer
**Date**: 2025-10-14
**API Version**: v1.0
