from typing import Dict, Any

def _dig_cost(plan_json):
    # plan_json is a list with one dict in PG JSON format
    n = plan_json[0]["Plan"]
    return n.get("Total Cost", n.get("Plan Rows", 0)), n.get("Plan Rows", 0)

def summarize_diff(before: Any, after: Any) -> Dict[str, Any]:
    try:
        bc, br = _dig_cost(before)
        ac, ar = _dig_cost(after)
    except Exception:
        return {}
    out = {
        "before_cost": bc, "after_cost": ac,
        "before_rows": br, "after_rows": ar,
    }
    if bc and ac:
        out["cost_delta_pct"] = round((bc - ac) * 100.0 / bc, 2)
        out["cost_down"] = ac < bc
    if br and ar:
        out["rows_delta_pct"] = round((br - ar) * 100.0 / br, 2)
        out["rows_down"] = ar < br
    return out
