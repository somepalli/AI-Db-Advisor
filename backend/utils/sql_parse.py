from typing import List, Dict, Any
import sqlglot
from sqlglot.expressions import Column, Condition

def mine_predicates(sql: str) -> List[Dict[str, Any]]:
    try:
        expr = sqlglot.parse_one(sql)
    except Exception:
        return []
    out = []

    # WHERE/JOIN
    for e in expr.find_all(Condition):
        # naive extraction
        import itertools
        comparison_types = [sqlglot.exp.EQ, sqlglot.exp.GT, sqlglot.exp.GTE, sqlglot.exp.LT, sqlglot.exp.LTE]
        all_comparisons = itertools.chain(*[e.find_all(cmp_type) for cmp_type in comparison_types])
        for cmp in all_comparisons:
            col = cmp.left
            if isinstance(col, Column):
                out.append({"table": col.table, "column": col.name, "op": cmp.key, "ctx": "where"})
    # ORDER BY
    ob = expr.args.get("order")
    if ob:
        for o in ob.expressions:
            col = o.this
            if isinstance(col, Column):
                out.append({"table": col.table, "column": col.name, "op": "order", "ctx": "order_by"})

    # GROUP BY
    gb = expr.args.get("group")
    if gb:
        for g in gb.expressions:
            if isinstance(g, Column):
                out.append({"table": g.table, "column": g.name, "op": "group", "ctx": "group_by"})
    return out

def project_columns(sql: str):
    try:
        expr = sqlglot.parse_one(sql)
    except Exception:
        return []
    cols = []
    sel = expr.args.get("expressions") or []
    for e in sel:
        if isinstance(e, Column):
            cols.append(e.name)
    return cols
