from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
import hashlib

class DataSourceCreate(BaseModel):
    id: str = Field(..., examples=["pg-dev"])
    engine: str = Field(..., examples=["postgres"])
    dsn: str = Field(..., examples=["postgresql://user:pass@host:5432/db"])

class ExplainRequest(BaseModel):
    sql: str
    analyze: bool = False

class HypoIndexRequest(BaseModel):
    table: str
    columns: List[str]
    include: Optional[List[str]] = None
    method: Optional[str] = None  # btree, gin, gist

class Recommendation(BaseModel):
    category: str
    summary: str
    sql_fix: Optional[str] = None
    risk: str = "low"
    expected_gain: Optional[str] = None
    details: Dict[str, Any] = {}

class TopQuery(BaseModel):
    query: str
    calls: int
    mean_time_ms: float
    rows: int

# ===== Suggestions Workflow Models =====

class Suggestion(BaseModel):
    """
    Unified suggestion model for database optimizations.
    Can represent index additions, query rewrites, config changes, etc.
    """
    id: str = Field(..., description="Stable hash-based ID for deduplication")
    level: Literal["db", "table", "query"] = Field(..., description="Scope of the suggestion")
    category: Literal["index", "rewrite", "config", "partition", "cleanup", "note"] = Field(
        ..., description="Type of optimization"
    )
    title: str = Field(..., description="Short human-readable title")
    summary: str = Field(..., description="Detailed explanation of the suggestion")
    sql_fix: Optional[str] = Field(None, description="SQL to apply the suggestion (if applicable)")
    validated: bool = Field(False, description="Whether suggestion was validated via EXPLAIN")
    confidence: Literal["rule-based", "ai-heuristic", "validated"] = Field(
        "rule-based", description="Source and reliability of the suggestion"
    )
    risk: Literal["low", "medium", "high"] = Field("low", description="Risk level of applying this suggestion")
    estimated_gain: Optional[str] = Field(None, description="Expected performance improvement")
    related_objects: List[str] = Field(default_factory=list, description="Tables, indexes, etc. affected")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context (before/after costs, etc.)")

    @staticmethod
    def generate_id(level: str, category: str, sql_fix: Optional[str], related_objects: List[str]) -> str:
        """Generate stable ID based on suggestion content"""
        content = f"{level}:{category}:{sql_fix or ''}:{','.join(sorted(related_objects))}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

class AnalyzeSuggestionsRequest(BaseModel):
    """Request to analyze a query and generate optimization suggestions"""
    ds_id: str = Field(..., description="Data source ID")
    sql: str = Field(..., description="SQL query to analyze")
    include_ai: bool = Field(True, description="Include AI-powered suggestions")
    top_k: int = Field(12, ge=1, le=50, description="Maximum number of suggestions to return")

class AnalyzeSuggestionsResponse(BaseModel):
    """Response containing consolidated optimization suggestions"""
    notes: List[str] = Field(default_factory=list, description="System notes about the analysis")
    suggestions: List[Suggestion] = Field(..., description="List of optimization suggestions")

class ApplySuggestionsRequest(BaseModel):
    """Request to apply one or more suggestions"""
    ds_id: str = Field(..., description="Data source ID")
    suggestion_ids: List[str] = Field(..., description="IDs of suggestions to apply")
    dry_run: bool = Field(False, description="If True, validate but rollback changes")

class ApplyResult(BaseModel):
    """Result of applying a single suggestion"""
    id: str = Field(..., description="Suggestion ID")
    status: Literal["success", "skipped", "error"] = Field(..., description="Application outcome")
    message: str = Field(..., description="Human-readable result message")
    rollback_sql: Optional[str] = Field(None, description="SQL to undo this change (if applicable)")

class ApplySuggestionsDirectRequest(BaseModel):
    """Request to apply suggestions directly with full Suggestion objects"""
    ds_id: str = Field(..., description="Data source ID")
    suggestions: List[Suggestion] = Field(..., description="Full Suggestion objects to apply")
    dry_run: bool = Field(False, description="If True, validate but rollback changes")

class ApplySuggestionsResponse(BaseModel):
    """Response from applying suggestions"""
    notes: List[str] = Field(default_factory=list, description="System notes about the application")
    results: List[ApplyResult] = Field(..., description="Results for each suggestion")
