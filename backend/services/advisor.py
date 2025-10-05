from typing import List, Dict, Any
from .postgres_agent import PostgresAgent
from ..utils.sql_parse import mine_predicates, project_columns
from ..utils.plan_diff import summarize_diff

def index_advice_pg(agent: PostgresAgent, sql: str) -> List[Dict[str, Any]]:
    # 1) parse predicates from WHERE/JOIN/ORDER/GROUP
    preds = mine_predicates(sql)
    if not preds:
        return []

    # 2) simple ordering rule: equality → range → order-by cols
    eq = [p["column"] for p in preds if p["op"] == "="]
    rng = [p["column"] for p in preds if p["op"] in (">", "<", ">=", "<=", "between")]
    ord_cols = [p["column"] for p in preds if p["ctx"] in ("order_by","group_by")]

    proposal = []
    base_order = []
    for col in eq:
        if col not in base_order: base_order.append(col)
    for col in rng:
        if col not in base_order: base_order.append(col)
    for col in ord_cols:
        if col not in base_order: base_order.append(col)

    if not base_order:
        return []

    include = project_columns(sql)[:4]  # small include for covering
    table = preds[0].get("table")  # naive: first table hit
    if not table or table == "":
        # No table name found, cannot recommend index
        return []

    # ✅ CHECK IF INDEX ALREADY EXISTS
    if agent.index_exists(table, base_order):
        import logging
        logging.getLogger(__name__).info(f"Skipping index suggestion for {table}({', '.join(base_order)}) - already exists")
        return []

    hypo = agent.hypothetical_index(table, base_order, include=include, method="btree")
    before = agent.explain(sql, analyze=False)
    after = agent.plan_with_hypo(sql, hypo["hypo_stmt"])
    diff = summarize_diff(before["plan"], after["plan"])

    accepted = diff.get("cost_down", False) or diff.get("rows_down", False)
    if not accepted:
        return []

    idx_sql = f"CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_{table}_{'_'.join(base_order)} ON {table} ({', '.join(base_order)})"
    if include:
        idx_sql += f" INCLUDE ({', '.join(include)});"
    else:
        idx_sql += ";"

    return [{
        "category": "index",
        "summary": f"Composite index on {table}({', '.join(base_order)}) looks beneficial.",
        "sql_fix": idx_sql,
        "risk": "medium",
        "expected_gain": f"Plan cost ↓ {diff.get('cost_delta_pct','?')}%, rows ↓ {diff.get('rows_delta_pct','?')}%",
        "details": diff
    }]

def rewrite_advice(sql: str) -> List[Dict[str, Any]]:
    adv = []
    if "select *" in sql.lower():
        adv.append({
            "category": "rewrite",
            "summary": "Avoid SELECT *; project only required columns.",
            "sql_fix": None,
            "risk": "low"
        })
    if " offset " in sql.lower() and " order by " in sql.lower():
        adv.append({
            "category": "rewrite",
            "summary": "Use keyset pagination instead of OFFSET/LIMIT for deep pages.",
            "sql_fix": None,
            "risk": "low"
        })
    return adv
