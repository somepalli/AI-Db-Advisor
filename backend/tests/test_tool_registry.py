"""Unit tests for the provider-trust gated tool layer (no DB required)."""
import pytest

from backend.services.tool_registry import (
    REGISTRY,
    active_tools,
    normalize_sql,
    drop_value_arrays,
    strip_query_text,
    scrub_literals,
    names_only,
)
from backend.services import llm_settings
from backend.config import settings


# ---------------------------------------------------------------- selector
def test_hosted_excludes_data_tools():
    tools = active_tools("postgres", "hosted")
    tiers = {t.tier for t in tools}
    assert tiers == {"metadata"}
    assert not any(t.tier == "data" for t in tools)


def test_local_includes_data_tools():
    local = active_tools("postgres", "local")
    hosted = active_tools("postgres", "hosted")
    assert len(local) > len(hosted)
    data = [t.name for t in local if t.tier == "data"]
    assert set(data) == {"pg.sample_rows", "pg.run_query", "pg.profile_values"}


def test_unknown_engine_returns_nothing():
    assert active_tools("elasticsearch", "local") == []


def test_mysql_hosted_excludes_data_tools():
    hosted = active_tools("mysql", "hosted")
    assert hosted and {t.tier for t in hosted} == {"metadata"}


def test_mysql_local_includes_data_tools():
    local = active_tools("mysql", "local")
    hosted = active_tools("mysql", "hosted")
    assert len(local) > len(hosted)
    data = {t.name for t in local if t.tier == "data"}
    assert data == {"my.sample_rows", "my.run_query"}


def test_selector_isolates_engines():
    # A postgres session never sees mysql tools and vice versa.
    assert all(t.engine == "postgres" for t in active_tools("postgres", "local"))
    assert all(t.engine == "mysql" for t in active_tools("mysql", "local"))


def test_data_tools_have_no_sanitizers_and_metadata_ops_exist():
    # data tools never declare sanitizers; every tool maps to an executor op name.
    for t in REGISTRY:
        if t.tier == "data":
            assert t.sanitize == ()
        assert t.mcp_op


# ---------------------------------------------------------------- provider_trust
@pytest.mark.parametrize("provider,override,expected", [
    ("ollama", "", "local"),
    ("openai", "", "hosted"),
    ("anthropic", "", "hosted"),
    ("openai", "local", "local"),   # override wins (e.g. local LM Studio)
    ("ollama", "hosted", "hosted"),
])
def test_resolve_provider_trust(provider, override, expected, monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", provider, raising=False)
    monkeypatch.setattr(settings, "LLM_PROVIDER_TRUST", override, raising=False)
    assert llm_settings.resolve_provider_trust() == expected


# ---------------------------------------------------------------- sanitizers
def test_normalize_sql_parameterizes_literals():
    rows = [{"query": "select * from orders where id = 4021 and name = 'bob'", "calls": 3}]
    out = normalize_sql(rows)
    q = out[0]["query"]
    assert "4021" not in q and "'bob'" not in q
    assert "$1" in q and "$2" in q


def test_drop_value_arrays_keeps_shape_stats():
    rows = [{
        "attname": "email", "n_distinct": 1000.0, "null_frac": 0.01, "correlation": 0.3,
        "most_common_vals": "{a@x.com,b@x.com}", "histogram_bounds": "{...}",
        "most_common_elems": "{...}",
    }]
    out = drop_value_arrays(rows)
    assert "most_common_vals" not in out[0]
    assert "histogram_bounds" not in out[0]
    assert out[0]["n_distinct"] == 1000.0 and out[0]["null_frac"] == 0.01


def test_strip_query_text_removes_query_field():
    rows = [{"locktype": "relation", "mode": "AccessShare", "granted": True,
             "pid": 42, "query": "select secret from accounts"}]
    out = strip_query_text(rows)
    assert "query" not in out[0]
    assert out[0]["mode"] == "AccessShare"


def test_scrub_literals_masks_numbers_and_strings():
    masked = scrub_literals("orders for customer 4021 named 'alice'")
    assert "4021" not in masked
    assert "alice" not in masked
    assert "<n>" in masked


def test_names_only_drops_sample_values():
    schema = {"tables": {"public.students": [
        {"column": "id", "type": "integer", "nullable": "NO", "sample": "12345"},
    ]}}
    out = names_only(schema)
    col = out["tables"]["public.students"][0]
    assert col == {"column": "id", "type": "integer"}
    assert "sample" not in col and "nullable" not in col
