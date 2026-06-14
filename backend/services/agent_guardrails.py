"""
agent_guardrails.py — Structural safety wall for the AI-Db-Advisor agent loop.

Design principle:
    The deny-list is the WALL. HITL approval is the GATE.
    Destructive / irreversible operations are REJECTED at validation and
    never reach the approval queue. Approval only ever gates safe-but-impactful
    actions that have already passed the wall.

This module is provider-agnostic and engine-agnostic at the policy layer.
Engine-specific parsing lives in classify_statement().

NOTE ON NAMING:
    The plan referred to this module as ``guardrails.py``. A pre-existing
    ``guardrails.py`` already implements the *human-initiated* apply-flow safety
    checks (check_sql_safety / check_risk_level / validate_suggestion_for_apply
    with a different signature) and is wired into apply.py and super_agent.py.
    To avoid breaking that flow while introducing the stricter agentic wall,
    the new design lives here as ``agent_guardrails`` with its own single
    decision point ``evaluate()``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RiskClass(str, Enum):
    METADATA_READ = "metadata_read"      # EXPLAIN, catalog/stat views, schema introspection
    SAFE_WRITE = "safe_write"            # CREATE INDEX CONCURRENTLY, ANALYZE, SET config
    IMPACTFUL_WRITE = "impactful_write"  # CREATE INDEX (non-concurrent), VACUUM FULL, ALTER add column
    DESTRUCTIVE = "destructive"          # DROP/TRUNCATE/DELETE/UPDATE-without-where — HARD DENY
    UNKNOWN = "unknown"                  # anything we cannot positively classify — DENY by default


class GuardrailDecision(str, Enum):
    ALLOW = "allow"                # may execute (still subject to dry-run + HITL per policy)
    REQUIRE_APPROVAL = "approval"  # must pass HITL gate
    REQUIRE_ELEVATED = "elevated"  # destructive-but-explicitly-allowed path (NOT used by the agent loop)
    DENY = "deny"                  # rejected at the wall; never reaches the queue


@dataclass
class GuardrailResult:
    decision: GuardrailDecision
    risk_class: RiskClass
    reason: str
    matched_rule: Optional[str] = None
    alert: bool = False            # raise an out-of-band alert event
    require_typed_confirmation: bool = False
    notes: list[str] = field(default_factory=list)


# --- The WALL: verbs that are NEVER permitted on the agentic path -------------
# These are matched as leading statement keywords (after stripping comments/whitespace).
HARD_DENY_PATTERNS: list[tuple[str, str]] = [
    (r"^\s*DROP\s+DATABASE\b",                "DROP DATABASE"),
    (r"^\s*DROP\s+SCHEMA\b",                  "DROP SCHEMA"),
    (r"^\s*DROP\s+TABLE\b",                   "DROP TABLE"),
    (r"^\s*DROP\s+(MATERIALIZED\s+)?VIEW\b",  "DROP VIEW"),
    (r"^\s*TRUNCATE\b",                       "TRUNCATE"),
    (r"^\s*DELETE\b",                         "DELETE"),
    (r"^\s*DROP\s+TABLESPACE\b",              "DROP TABLESPACE"),
    (r"^\s*DROP\s+ROLE\b",                    "DROP ROLE"),
    (r"^\s*DROP\s+USER\b",                    "DROP USER"),
    (r"^\s*ALTER\s+TABLE\s+\S+\s+DROP\b",     "ALTER TABLE ... DROP COLUMN"),
    (r"\bCASCADE\b",                          "CASCADE clause"),
    # MongoDB / Redis / Cassandra destructive equivalents (string-level safety net)
    (r"\.drop\s*\(",                          "Mongo .drop()"),
    (r"\.deleteMany\s*\(",                    "Mongo .deleteMany()"),
    (r"\.remove\s*\(",                        "Mongo .remove()"),
    (r"^\s*FLUSHALL\b",                       "Redis FLUSHALL"),
    (r"^\s*FLUSHDB\b",                        "Redis FLUSHDB"),
    (r"^\s*DROP\s+KEYSPACE\b",                "Cassandra DROP KEYSPACE"),
]

# UPDATE/DELETE without a WHERE clause is treated as destructive.
UNQUALIFIED_WRITE = re.compile(r"^\s*(UPDATE|DELETE)\b(?!.*\bWHERE\b)", re.IGNORECASE | re.DOTALL)

# --- Allowed agentic remediation verbs (the only writes the agent may PROPOSE) -
SAFE_WRITE_PATTERNS: list[tuple[str, str]] = [
    (r"^\s*CREATE\s+INDEX\s+CONCURRENTLY\b", "CREATE INDEX CONCURRENTLY"),
    (r"^\s*ANALYZE\b",                       "ANALYZE"),
    (r"^\s*SET\b",                           "SET (session config)"),
    (r"^\s*RESET\b",                         "RESET (session config)"),
]
IMPACTFUL_WRITE_PATTERNS: list[tuple[str, str]] = [
    (r"^\s*CREATE\s+UNIQUE\s+INDEX\b",       "CREATE UNIQUE INDEX"),
    (r"^\s*CREATE\s+INDEX\b",                "CREATE INDEX (non-concurrent)"),
    (r"^\s*VACUUM\b",                        "VACUUM"),
    (r"^\s*ALTER\s+TABLE\s+\S+\s+ADD\b",     "ALTER TABLE ... ADD"),
    (r"^\s*REINDEX\b",                       "REINDEX"),
]
METADATA_READ_PATTERNS: list[tuple[str, str]] = [
    (r"^\s*EXPLAIN\b(?!.*\bANALYZE\b)",      "EXPLAIN (no ANALYZE)"),
    (r"^\s*SELECT\b.*\bpg_(stat|class|index|namespace|statio)", "catalog/stat SELECT"),
    (r"^\s*SHOW\b",                          "SHOW"),
]


def _strip(sql: str) -> str:
    """Remove SQL comments so deny patterns can't be smuggled past the anchor."""
    no_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    no_line = re.sub(r"--[^\n]*", " ", no_block)
    return no_line.strip()


def classify_statement(sql: str) -> RiskClass:
    s = _strip(sql)
    for pat, _ in HARD_DENY_PATTERNS:
        if re.search(pat, s, re.IGNORECASE):
            return RiskClass.DESTRUCTIVE
    if UNQUALIFIED_WRITE.search(s):
        return RiskClass.DESTRUCTIVE
    for pat, _ in METADATA_READ_PATTERNS:
        if re.search(pat, s, re.IGNORECASE):
            return RiskClass.METADATA_READ
    for pat, _ in SAFE_WRITE_PATTERNS:
        if re.search(pat, s, re.IGNORECASE):
            return RiskClass.SAFE_WRITE
    for pat, _ in IMPACTFUL_WRITE_PATTERNS:
        if re.search(pat, s, re.IGNORECASE):
            return RiskClass.IMPACTFUL_WRITE
    return RiskClass.UNKNOWN


def evaluate(sql: str, *, agentic: bool) -> GuardrailResult:
    """
    Single decision point for any statement the system might execute.

    agentic=True  -> the autonomous loop. NEVER allowed to touch destructive
                     verbs and never allowed to execute UNKNOWN statements.
    agentic=False -> human-initiated apply flow (still walls off destructive).
    """
    s = _strip(sql)

    for pat, label in HARD_DENY_PATTERNS:
        if re.search(pat, s, re.IGNORECASE):
            return GuardrailResult(
                decision=GuardrailDecision.DENY,
                risk_class=RiskClass.DESTRUCTIVE,
                reason=f"Destructive operation blocked at guardrail wall: {label}.",
                matched_rule=label,
                alert=True,
                notes=["Destructive operations are rejected before the approval queue."],
            )
    if UNQUALIFIED_WRITE.search(s):
        return GuardrailResult(
            decision=GuardrailDecision.DENY,
            risk_class=RiskClass.DESTRUCTIVE,
            reason="UPDATE/DELETE without a WHERE clause is treated as destructive.",
            matched_rule="UNQUALIFIED_WRITE",
            alert=True,
        )

    rc = classify_statement(s)

    if rc is RiskClass.METADATA_READ:
        return GuardrailResult(GuardrailDecision.ALLOW, rc,
                               "Metadata-only read; no row data, no mutation.")
    if rc is RiskClass.SAFE_WRITE:
        return GuardrailResult(GuardrailDecision.REQUIRE_APPROVAL, rc,
                               "Safe remediation; requires HITL approval and a passing dry-run.")
    if rc is RiskClass.IMPACTFUL_WRITE:
        return GuardrailResult(GuardrailDecision.REQUIRE_APPROVAL, rc,
                               "Impactful remediation; requires HITL approval, dry-run, and impact preview.",
                               alert=False, require_typed_confirmation=False)

    # UNKNOWN: deny on the agentic path, require elevated review otherwise.
    if agentic:
        return GuardrailResult(GuardrailDecision.DENY, RiskClass.UNKNOWN,
                               "Statement could not be positively classified; denied on the agentic path.",
                               matched_rule="UNKNOWN_DENY", alert=True)
    return GuardrailResult(GuardrailDecision.REQUIRE_ELEVATED, RiskClass.UNKNOWN,
                           "Unclassified statement; requires elevated human review with typed confirmation.",
                           require_typed_confirmation=True, alert=True)


def validate_suggestion_for_apply(sql: str, *, agentic: bool = False) -> GuardrailResult:
    """Entry point called by apply.py before any execution (dry-run or real)."""
    return evaluate(sql, agentic=agentic)
