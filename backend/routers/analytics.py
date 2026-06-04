"""
Analytics Router - DuckDB Analytics Endpoints
Handles data sync, analytics queries, and dashboard metrics
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.deps import resolve_agent
from backend.services.duckdb_agent import DuckDBAgent
from backend.services.postgres_agent import PostgresAgent
from backend.services.data_sync import DataSyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# Request/Response Models
class SyncTableRequest(BaseModel):
    pg_ds_id: str
    duckdb_ds_id: str
    table_name: str
    batch_size: int = 1000
    incremental: bool = False
    timestamp_column: Optional[str] = None


class SyncAllTablesRequest(BaseModel):
    pg_ds_id: str
    duckdb_ds_id: str
    exclude_tables: List[str] = []
    batch_size: int = 1000


class SyncStatusRequest(BaseModel):
    pg_ds_id: str
    duckdb_ds_id: str


class AnalyticsQueryRequest(BaseModel):
    ds_id: str
    query: str


# Sync Endpoints
@router.post("/sync/table")
def sync_table(request: SyncTableRequest):
    """Sync a single table from PostgreSQL to DuckDB"""
    try:
        logger.info(f"Syncing table {request.table_name} from {request.pg_ds_id} to {request.duckdb_ds_id}")

        # Resolve agents
        pg_agent = resolve_agent(request.pg_ds_id)
        analytics_agent = resolve_agent(request.duckdb_ds_id)

        # Validate agent types
        if not isinstance(pg_agent, PostgresAgent):
            raise HTTPException(status_code=400, detail="Source must be PostgreSQL datasource")

        if not isinstance(analytics_agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Target must be DuckDB datasource")

        # Create sync service
        sync_service = DataSyncService(pg_agent, analytics_agent)

        # Sync table
        result = sync_service.sync_table(
            table_name=request.table_name,
            batch_size=request.batch_size,
            incremental=request.incremental,
            timestamp_column=request.timestamp_column
        )

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync table error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/all")
def sync_all_tables(request: SyncAllTablesRequest):
    """Sync all tables from PostgreSQL to DuckDB"""
    try:
        logger.info(f"Syncing all tables from {request.pg_ds_id} to {request.duckdb_ds_id}")

        # Resolve agents
        pg_agent = resolve_agent(request.pg_ds_id)
        analytics_agent = resolve_agent(request.duckdb_ds_id)

        # Validate agent types
        if not isinstance(pg_agent, PostgresAgent):
            raise HTTPException(status_code=400, detail="Source must be PostgreSQL datasource")

        if not isinstance(analytics_agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Target must be DuckDB datasource")

        # Create sync service
        sync_service = DataSyncService(pg_agent, analytics_agent)

        # Sync all tables
        result = sync_service.sync_all_tables(
            exclude_tables=request.exclude_tables,
            batch_size=request.batch_size
        )

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync all tables error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/status")
def get_sync_status(request: SyncStatusRequest):
    """Get sync status comparing PostgreSQL and DuckDB"""
    try:
        logger.info(f"Getting sync status for {request.pg_ds_id} and {request.duckdb_ds_id}")

        # Resolve agents
        pg_agent = resolve_agent(request.pg_ds_id)
        analytics_agent = resolve_agent(request.duckdb_ds_id)

        # Validate agent types
        if not isinstance(pg_agent, PostgresAgent):
            raise HTTPException(status_code=400, detail="Source must be PostgreSQL datasource")

        if not isinstance(analytics_agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Target must be DuckDB datasource")

        # Create sync service
        sync_service = DataSyncService(pg_agent, analytics_agent)

        # Get sync status
        result = sync_service.get_sync_status()

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to get status"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get sync status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Analytics Query Endpoints
@router.post("/query")
def execute_analytics_query(request: AnalyticsQueryRequest):
    """Execute an analytics query on DuckDB"""
    try:
        logger.info(f"Executing analytics query on {request.ds_id}")

        # Resolve agent
        agent = resolve_agent(request.ds_id)

        # Validate agent type
        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        # Execute query
        result = agent.execute_query(request.query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analytics query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/metrics/student-enrollment")
def get_student_enrollment_metrics(ds_id: str):
    """Get student enrollment analytics (specific to UniversityDB)"""
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        # Query for enrollment by year and department
        query = """
            SELECT
                s.enrollment_year,
                d.department_name,
                count(*) as student_count,
                count(DISTINCT e.course_id) as courses_taken,
                avg(CASE WHEN e.grade = 'A' THEN 4.0
                         WHEN e.grade = 'B' THEN 3.0
                         WHEN e.grade = 'C' THEN 2.0
                         WHEN e.grade = 'D' THEN 1.0
                         ELSE 0.0 END) as avg_gpa
            FROM main.public_students s
            LEFT JOIN main.public_departments d ON s.department_id = d.department_id
            LEFT JOIN main.public_enrollments e ON s.student_id = e.student_id
            GROUP BY s.enrollment_year, d.department_name
            ORDER BY s.enrollment_year DESC, d.department_name
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Student enrollment metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/metrics/fee-collection")
def get_fee_collection_metrics(ds_id: str):
    """Get fee collection analytics"""
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        # Query for fee collection stats
        query = """
            SELECT
                status,
                count(*) as count,
                sum(amount) as total_amount,
                avg(amount) as avg_amount
            FROM main.public_fees
            GROUP BY status
            ORDER BY total_amount DESC
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fee collection metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/metrics/library-usage")
def get_library_usage_metrics(ds_id: str):
    """Get library usage analytics"""
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        # Query for library usage stats
        query = """
            SELECT
                d.department_name,
                count(DISTINCT bl.loan_id) as total_loans,
                count(DISTINCT bl.student_id) as unique_borrowers,
                count(DISTINCT bl.book_id) as unique_books,
                avg(date_diff('day', bl.loan_date, bl.return_date)) as avg_loan_days
            FROM main.public_bookloans bl
            LEFT JOIN main.public_students s ON bl.student_id = s.student_id
            LEFT JOIN main.public_departments d ON s.department_id = d.department_id
            GROUP BY d.department_name
            ORDER BY total_loans DESC
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Library usage metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/metrics/hostel-occupancy")
def get_hostel_occupancy_metrics(ds_id: str):
    """Get hostel occupancy analytics"""
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        # Query for hostel occupancy stats
        query = """
            SELECT
                h.hostel_name,
                h.capacity,
                count(ha.allocation_id) as current_occupancy,
                round((count(ha.allocation_id) * 100.0) / h.capacity, 2) as occupancy_rate
            FROM main.public_hostel h
            LEFT JOIN main.public_hostelallocation ha ON h.hostel_id = ha.hostel_id
            GROUP BY h.hostel_name, h.capacity
            ORDER BY occupancy_rate DESC
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hostel occupancy metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/metrics/course-popularity")
def get_course_popularity_metrics(ds_id: str):
    """Get course popularity analytics"""
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        # Query for course popularity
        query = """
            SELECT
                c.course_name,
                d.department_name,
                count(DISTINCT e.student_id) as total_enrollments,
                count(DISTINCT e.semester) as semesters_offered,
                avg(CASE WHEN e.grade = 'A' THEN 4.0
                         WHEN e.grade = 'B' THEN 3.0
                         WHEN e.grade = 'C' THEN 2.0
                         WHEN e.grade = 'D' THEN 1.0
                         ELSE 0.0 END) as avg_grade
            FROM main.public_courses c
            LEFT JOIN main.public_departments d ON c.department_id = d.department_id
            LEFT JOIN main.public_enrollments e ON c.course_id = e.course_id
            GROUP BY c.course_name, d.department_name
            HAVING total_enrollments > 0
            ORDER BY total_enrollments DESC
            LIMIT 20
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Course popularity metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ADVANCED ANALYTICS ENDPOINTS - Dashboard KPIs and Visualizations
# ============================================================================

@router.get("/{ds_id}/dashboard/kpis")
def get_dashboard_kpis(ds_id: str):
    """
    Get Key Performance Indicators (KPIs) for dashboard
    Returns: Total students, revenue, collection rate, library activity, hostel occupancy
    Visualization: Card/Stat widgets
    """
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        query = """
            WITH student_stats AS (
                SELECT
                    COUNT(*) as total_students,
                    COUNT(DISTINCT department_id) as total_departments
                FROM main.public_students
            ),
            fee_stats AS (
                SELECT
                    SUM(amount) as total_revenue,
                    SUM(CASE WHEN status = 'Paid' THEN amount ELSE 0 END) as collected_revenue,
                    COUNT(CASE WHEN status = 'Paid' THEN 1 END) as paid_count,
                    COUNT(*) as total_fees
                FROM main.public_fees
            ),
            library_stats AS (
                SELECT
                    COUNT(*) as total_loans,
                    COUNT(DISTINCT student_id) as active_borrowers
                FROM main.public_bookloans
            ),
            hostel_stats AS (
                SELECT
                    SUM(capacity) as total_capacity,
                    COUNT(DISTINCT student_id) as occupied_beds
                FROM main.public_hostel h
                LEFT JOIN main.public_hostelallocation ha ON h.hostel_id = ha.hostel_id
            )
            SELECT
                ss.total_students,
                ss.total_departments,
                fs.total_revenue,
                fs.collected_revenue,
                ROUND((fs.collected_revenue / NULLIF(fs.total_revenue, 0)) * 100, 2) as collection_rate,
                ROUND((fs.paid_count::DECIMAL / NULLIF(fs.total_fees, 0)) * 100, 2) as payment_compliance_rate,
                ls.total_loans,
                ls.active_borrowers,
                hs.total_capacity as hostel_capacity,
                hs.occupied_beds as hostel_occupied,
                ROUND((hs.occupied_beds::DECIMAL / NULLIF(hs.total_capacity, 0)) * 100, 2) as hostel_occupancy_rate
            FROM student_stats ss, fee_stats fs, library_stats ls, hostel_stats hs
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard KPIs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/dashboard/enrollment-trends")
def get_enrollment_trends(ds_id: str):
    """
    Get enrollment trends over time
    Returns: Year-wise enrollment data with growth rates
    Visualization: Line chart, Area chart
    """
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        query = """
            WITH yearly_enrollment AS (
                SELECT
                    enrollment_year,
                    COUNT(*) as student_count
                FROM main.public_students
                GROUP BY enrollment_year
                ORDER BY enrollment_year
            )
            SELECT
                enrollment_year,
                student_count,
                LAG(student_count) OVER (ORDER BY enrollment_year) as prev_year_count,
                ROUND(
                    ((student_count - LAG(student_count) OVER (ORDER BY enrollment_year))::DECIMAL /
                    NULLIF(LAG(student_count) OVER (ORDER BY enrollment_year), 0)) * 100,
                    2
                ) as growth_rate
            FROM yearly_enrollment
            ORDER BY enrollment_year
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enrollment trends error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/dashboard/department-distribution")
def get_department_distribution(ds_id: str):
    """
    Get student distribution across departments
    Returns: Department-wise student counts and percentages
    Visualization: Pie chart, Donut chart, Bar chart
    """
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        query = """
            WITH dept_counts AS (
                SELECT
                    d.department_name,
                    COUNT(s.student_id) as student_count,
                    COUNT(DISTINCT p.professor_id) as professor_count
                FROM main.public_departments d
                LEFT JOIN main.public_students s ON d.department_id = s.department_id
                LEFT JOIN main.public_professors p ON d.department_id = p.department_id
                GROUP BY d.department_name
            ),
            total_students AS (
                SELECT COUNT(*) as total FROM main.public_students
            )
            SELECT
                dc.department_name,
                dc.student_count,
                dc.professor_count,
                ROUND((dc.student_count::DECIMAL / ts.total) * 100, 2) as percentage,
                ROUND(dc.student_count::DECIMAL / NULLIF(dc.professor_count, 0), 2) as student_professor_ratio
            FROM dept_counts dc, total_students ts
            ORDER BY dc.student_count DESC
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Department distribution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/dashboard/grade-distribution")
def get_grade_distribution(ds_id: str):
    """
    Get grade distribution across all enrollments
    Returns: Grade counts and percentages with department breakdown
    Visualization: Stacked bar chart, Grouped bar chart
    """
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        query = """
            WITH grade_counts AS (
                SELECT
                    d.department_name,
                    e.grade,
                    COUNT(*) as count
                FROM main.public_enrollments e
                LEFT JOIN main.public_students s ON e.student_id = s.student_id
                LEFT JOIN main.public_departments d ON s.department_id = d.department_id
                WHERE e.grade IS NOT NULL AND e.grade != ''
                GROUP BY d.department_name, e.grade
            ),
            total_grades AS (
                SELECT
                    department_name,
                    SUM(count) as total
                FROM grade_counts
                GROUP BY department_name
            )
            SELECT
                gc.department_name,
                gc.grade,
                gc.count,
                ROUND((gc.count::DECIMAL / tg.total) * 100, 2) as percentage
            FROM grade_counts gc
            JOIN total_grades tg ON gc.department_name = tg.department_name
            ORDER BY gc.department_name, gc.grade
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grade distribution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/dashboard/revenue-analysis")
def get_revenue_analysis(ds_id: str):
    """
    Get revenue analysis with payment status breakdown
    Returns: Revenue by status, department, and time period
    Visualization: Stacked area chart, Multi-series bar chart
    """
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        query = """
            WITH monthly_revenue AS (
                SELECT
                    strftime(f.due_date, '%Y-%m') as month,
                    d.department_name,
                    f.status,
                    COUNT(*) as transaction_count,
                    SUM(f.amount) as total_amount,
                    AVG(f.amount) as avg_amount,
                    MIN(f.amount) as min_amount,
                    MAX(f.amount) as max_amount
                FROM main.public_fees f
                LEFT JOIN main.public_students s ON f.student_id = s.student_id
                LEFT JOIN main.public_departments d ON s.department_id = d.department_id
                WHERE f.due_date IS NOT NULL
                GROUP BY month, d.department_name, f.status
            )
            SELECT
                month,
                department_name,
                status,
                transaction_count,
                ROUND(total_amount, 2) as total_amount,
                ROUND(avg_amount, 2) as avg_amount,
                ROUND(min_amount, 2) as min_amount,
                ROUND(max_amount, 2) as max_amount
            FROM monthly_revenue
            ORDER BY month DESC, department_name, status
            LIMIT 200
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revenue analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/dashboard/library-analytics")
def get_library_analytics(ds_id: str):
    """
    Get comprehensive library usage analytics
    Returns: Most borrowed books, department-wise usage, loan patterns
    Visualization: Horizontal bar chart, Heat map
    """
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        query = """
            SELECT
                lb.title,
                lb.author,
                d.department_name,
                COUNT(bl.loan_id) as total_loans,
                COUNT(DISTINCT bl.student_id) as unique_borrowers,
                lb.available_copies,
                ROUND(AVG(date_diff('day', bl.loan_date, bl.return_date)), 2) as avg_loan_duration,
                MIN(bl.loan_date) as first_loan_date,
                MAX(bl.loan_date) as last_loan_date
            FROM main.public_librarybooks lb
            LEFT JOIN main.public_bookloans bl ON lb.book_id = bl.book_id
            LEFT JOIN main.public_departments d ON lb.department_id = d.department_id
            WHERE bl.loan_id IS NOT NULL
            GROUP BY lb.title, lb.author, d.department_name, lb.available_copies
            ORDER BY total_loans DESC
            LIMIT 30
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Library analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/dashboard/performance-metrics")
def get_performance_metrics(ds_id: str):
    """
    Get student academic performance metrics by department
    Returns: GPA distribution, pass rates, top performers
    Visualization: Box plot, Violin plot, Scatter plot
    """
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        query = """
            WITH student_gpa AS (
                SELECT
                    s.student_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    d.department_name,
                    s.enrollment_year,
                    COUNT(e.enrollment_id) as total_courses,
                    AVG(CASE
                        WHEN e.grade = 'A' THEN 4.0
                        WHEN e.grade = 'B' THEN 3.0
                        WHEN e.grade = 'C' THEN 2.0
                        WHEN e.grade = 'D' THEN 1.0
                        ELSE 0.0
                    END) as gpa,
                    SUM(CASE WHEN e.grade IN ('A', 'B', 'C', 'D') THEN 1 ELSE 0 END) as passed_courses,
                    SUM(CASE WHEN e.grade NOT IN ('A', 'B', 'C', 'D') OR e.grade IS NULL THEN 1 ELSE 0 END) as failed_courses
                FROM main.public_students s
                LEFT JOIN main.public_enrollments e ON s.student_id = e.student_id
                LEFT JOIN main.public_departments d ON s.department_id = d.department_id
                GROUP BY s.student_id, student_name, d.department_name, s.enrollment_year
            )
            SELECT
                department_name,
                enrollment_year,
                COUNT(*) as student_count,
                ROUND(AVG(gpa), 2) as avg_gpa,
                ROUND(MIN(gpa), 2) as min_gpa,
                ROUND(MAX(gpa), 2) as max_gpa,
                ROUND(AVG(total_courses), 2) as avg_courses_per_student,
                ROUND((SUM(passed_courses)::DECIMAL / NULLIF(SUM(total_courses), 0)) * 100, 2) as pass_rate,
                COUNT(CASE WHEN gpa >= 3.5 THEN 1 END) as honors_students,
                COUNT(CASE WHEN gpa < 2.0 THEN 1 END) as at_risk_students
            FROM student_gpa
            WHERE department_name IS NOT NULL
            GROUP BY department_name, enrollment_year
            ORDER BY enrollment_year DESC, department_name
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Performance metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/dashboard/hostel-analytics")
def get_hostel_analytics(ds_id: str):
    """
    Get detailed hostel occupancy and allocation analytics
    Returns: Occupancy trends, room utilization, allocation patterns
    Visualization: Gauge chart, Progress bars, Heat map
    """
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        query = """
            WITH hostel_stats AS (
                SELECT
                    h.hostel_name,
                    h.capacity,
                    h.warden_name,
                    COUNT(DISTINCT ha.student_id) as current_occupancy,
                    COUNT(DISTINCT ha.room_no) as occupied_rooms,
                    strftime(ha.allocation_date, '%Y-%m') as allocation_month
                FROM main.public_hostel h
                LEFT JOIN main.public_hostelallocation ha ON h.hostel_id = ha.hostel_id
                GROUP BY h.hostel_name, h.capacity, h.warden_name, allocation_month
            )
            SELECT
                hostel_name,
                capacity,
                warden_name,
                allocation_month,
                current_occupancy,
                occupied_rooms,
                capacity - current_occupancy as available_capacity,
                ROUND((current_occupancy::DECIMAL / capacity) * 100, 2) as occupancy_rate,
                ROUND(current_occupancy::DECIMAL / NULLIF(occupied_rooms, 0), 2) as avg_students_per_room
            FROM hostel_stats
            WHERE allocation_month IS NOT NULL
            ORDER BY allocation_month DESC, hostel_name
            LIMIT 100
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hostel analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/dashboard/comparative-analysis")
def get_comparative_analysis(ds_id: str):
    """
    Get comparative analysis across multiple dimensions
    Returns: Department comparisons, year-over-year trends, benchmarks
    Visualization: Radar chart, Multi-axis line chart, Comparison table
    """
    try:
        agent = resolve_agent(ds_id)

        if not isinstance(agent, DuckDBAgent):
            raise HTTPException(status_code=400, detail="Must be DuckDB datasource")

        query = """
            WITH dept_metrics AS (
                SELECT
                    d.department_name,
                    COUNT(DISTINCT s.student_id) as total_students,
                    COUNT(DISTINCT p.professor_id) as total_professors,
                    COUNT(DISTINCT c.course_id) as total_courses,
                    AVG(CASE
                        WHEN e.grade = 'A' THEN 4.0
                        WHEN e.grade = 'B' THEN 3.0
                        WHEN e.grade = 'C' THEN 2.0
                        WHEN e.grade = 'D' THEN 1.0
                        ELSE 0.0
                    END) as avg_gpa,
                    COUNT(DISTINCT bl.loan_id) as library_loans,
                    SUM(CASE WHEN f.status = 'Paid' THEN f.amount ELSE 0 END) as revenue_collected,
                    SUM(f.amount) as total_revenue
                FROM main.public_departments d
                LEFT JOIN main.public_students s ON d.department_id = s.department_id
                LEFT JOIN main.public_professors p ON d.department_id = p.department_id
                LEFT JOIN main.public_courses c ON d.department_id = c.department_id
                LEFT JOIN main.public_enrollments e ON s.student_id = e.student_id
                LEFT JOIN main.public_bookloans bl ON s.student_id = bl.student_id
                LEFT JOIN main.public_fees f ON s.student_id = f.student_id
                GROUP BY d.department_name
            )
            SELECT
                department_name,
                total_students,
                total_professors,
                total_courses,
                ROUND(avg_gpa, 2) as avg_gpa,
                library_loans,
                ROUND(revenue_collected, 2) as revenue_collected,
                ROUND(total_revenue, 2) as total_revenue,
                ROUND((revenue_collected / NULLIF(total_revenue, 0)) * 100, 2) as collection_rate,
                ROUND(total_students::DECIMAL / NULLIF(total_professors, 0), 2) as student_professor_ratio,
                ROUND(library_loans::DECIMAL / NULLIF(total_students, 0), 2) as loans_per_student
            FROM dept_metrics
            ORDER BY total_students DESC
        """

        result = agent.execute_query(query)

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comparative analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
