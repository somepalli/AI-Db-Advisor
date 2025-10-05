from __future__ import annotations
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from fastui import FastUI, components as c, events as e, forms as f, prebuilt_html
from fastui.components.forms import FormFieldTextarea
from fastui.components.display import DisplayLookup, DisplayMode
from pydantic import BaseModel, Field

from ..deps import resolve_agent
from ..schemas import DataSourceCreate, ExplainRequest
from ..services.advisor import index_advice_pg, rewrite_advice
from ..services.ai_client import LLMClient
from ..services.ai_suggest import ai_suggestions_for_sql_pg
from ..config import settings

ui = APIRouter(prefix="/ui", tags=["ui"])


# ---------- Table Models ----------
class QueryRow(BaseModel):
    idx: str = Field(title="#")
    calls: str = Field(title="Calls")
    avg_time: str = Field(title="Avg Time")
    rows: str = Field(title="Rows")
    query: str = Field(title="Query")

class LockRow(BaseModel):
    locktype: str = Field(title="Lock Type")
    mode: str = Field(title="Mode")
    granted: str = Field(title="Granted")
    pid: str = Field(title="PID")
    age: str = Field(title="Age")


# ---------- helpers ----------
def _json_pretty(data: Any) -> str:
    import json
    try:
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception:
        return str(data)


def _ds_cards() -> List[c.Component]:
    items = []
    for ds_id, cfg in settings.DATASOURCES.items():
        items.append(
            c.Div(components=[
                c.Heading(text=f"📊 {ds_id}", level=4),
                c.Paragraph(text=f"{cfg['engine']} → {cfg['dsn']}"),
                c.Button(text="Open", on_click=e.GoToEvent(url=f"/ui/pages/ds/{ds_id}")),
            ])
        )
    return items or [c.Text(text="No data sources configured yet.")]


# ---------- Pages (JSON) ----------
# These must be defined BEFORE the catch-all HTML route

# Root API endpoint - redirects to home page
@ui.get("/pages", response_model=FastUI, response_model_exclude_none=True)
@ui.get("/pages/", response_model=FastUI, response_model_exclude_none=True)
def page_root():
    """Root page redirects to home"""
    return page_home()

@ui.get("/pages/home", response_model=FastUI, response_model_exclude_none=True)
def page_home():
    # Get datasource count for display
    ds_count = len(settings.DATASOURCES)

    return [
        c.PageTitle(text="AI DB Advisor"),
        c.Page(
            components=[
                c.Heading(text="🤖 AI Database Performance Advisor", level=1),
                c.Paragraph(text="Intelligent database performance optimization powered by AI. Analyze queries, get real-time recommendations, and optimize your PostgreSQL databases."),

                c.Heading(text="Quick Start", level=3),
                c.Div(
                    components=[
                        c.Div(components=[
                            c.Heading(text="📊 Manage Data Sources", level=4),
                            c.Paragraph(text=f"{ds_count} source(s) configured"),
                            c.Paragraph(text="Register and manage PostgreSQL database connections"),
                            c.Button(
                                text="Manage Data Sources",
                                on_click=e.GoToEvent(url="/ui/pages/datasources"),
                                named_style="primary"
                            ),
                        ]),
                        c.Div(components=[
                            c.Heading(text="🔍 Analyze Queries", level=4),
                            c.Paragraph(text="Performance insights & recommendations"),
                            c.Paragraph(text="Run EXPLAIN plans, view top queries, and get optimization suggestions"),
                            c.Button(
                                text="Start Analysis",
                                on_click=e.GoToEvent(url="/ui/pages/analyze"),
                                named_style="primary"
                            ),
                        ]),
                    ]
                ),

                c.Heading(text="Features", level=3),
                c.Div(components=[
                    c.Heading(text="🎯 Rule-Based Index Recommendations", level=4),
                    c.Paragraph(text="• Analyze SQL predicates and suggest optimal composite indexes"),
                    c.Paragraph(text="• Validate recommendations using HypoPG hypothetical indexes"),
                    c.Paragraph(text="• Compare query plans before and after index creation"),
                ]),
                c.Div(components=[
                    c.Heading(text="🤖 AI-Powered Query Optimization", level=4),
                    c.Paragraph(text="• Get intelligent query rewrite suggestions from local LLM"),
                    c.Paragraph(text="• Context-aware recommendations based on schema and query patterns"),
                    c.Paragraph(text="• Natural language explanations of EXPLAIN plans"),
                ]),
                c.Div(components=[
                    c.Heading(text="📈 Performance Monitoring", level=4),
                    c.Paragraph(text="• View top queries by execution time (pg_stat_statements)"),
                    c.Paragraph(text="• Monitor database locks and active connections"),
                    c.Paragraph(text="• Track database size and backend statistics"),
                ]),
            ],
        )
    ]


@ui.get("/pages/datasources", response_model=FastUI, response_model_exclude_none=True)
def page_datasources():
    # Form to add a datasource using the Pydantic model
    ds_form = c.ModelForm(
        model=DataSourceCreate,
        submit_url="/datasources",
        method="POST",
    )

    # List existing datasources
    cards = _ds_cards()

    return [
        c.PageTitle(text="Data Sources - AI DB Advisor"),
        c.Page(
            components=[
                c.Heading(text="📊 Data Source Management", level=2),
                c.Paragraph(text="Register and manage your PostgreSQL database connections. Each data source requires a unique ID, engine type, and connection string (DSN)."),

                c.Heading(text="Add New Data Source", level=3),
                c.Div(components=[
                    c.Paragraph(text="💡 Example DSN: postgresql://user:password@localhost:5432/dbname"),
                    ds_form,
                ]),

                c.Heading(text=f"Registered Data Sources ({len(settings.DATASOURCES)})", level=3),
                c.Div(components=cards if cards else [
                    c.Text(text="No data sources configured yet. Add one above to get started.")
                ]),

                c.Div(components=[
                    c.Button(text="← Back to Home", on_click=e.GoToEvent(url="/ui/pages/home")),
                ]),
            ],
        )
    ]


@ui.get("/pages/analyze", response_model=FastUI, response_model_exclude_none=True)
def page_analyze(ds_id: Optional[str] = Query(default=None)):
    # If no ds_id chosen, render a selector
    options = [{"label": k, "value": k} for k in settings.DATASOURCES.keys()]

    comps: List[c.Component] = [
        c.Heading(text="🔍 Query Analyzer", level=2),
        c.Paragraph(text="Select a data source to view performance dashboard, analyze queries, and get optimization recommendations."),
    ]

    if not options:
        comps.extend([
            c.Div(components=[
                c.Heading(text="⚠️ No Data Sources", level=4),
                c.Paragraph(text="You need to register a data source before analyzing queries."),
                c.Button(text="Register Data Source", on_click=e.GoToEvent(url="/ui/pages/datasources"), named_style="primary"),
            ]),
            c.Button(text="← Back to Home", on_click=e.GoToEvent(url="/ui/pages/home")),
        ])
    else:
        comps.append(
            c.Form(
                submit_url="/ui/pages/analyze", method="GET",
                form_fields=[
                    c.FormFieldSelect(name="ds_id", title="Select Data Source", options=options, required=True),
                ],
            )
        )

        if ds_id:
            comps.extend([
                c.Heading(text=f"Selected: {ds_id}", level=3),
                c.Div(components=[
                    c.Button(text="📊 View Dashboard", on_click=e.GoToEvent(url=f"/ui/pages/ds/{ds_id}"), named_style="primary"),
                    c.Button(text="🔎 Explain Query", on_click=e.GoToEvent(url=f"/ui/pages/explain?ds_id={ds_id}")),
                    c.Button(text="← Back", on_click=e.GoToEvent(url="/ui/pages/home")),
                ]),
            ])
        else:
            comps.append(c.Button(text="← Back to Home", on_click=e.GoToEvent(url="/ui/pages/home")))

    return [c.PageTitle(text="Analyze - AI DB Advisor"), c.Page(components=comps)]


@ui.get("/pages/ds/{ds_id}", response_model=FastUI, response_model_exclude_none=True)
def page_ds(ds_id: str):
    agent = resolve_agent(ds_id)
    stats = agent.stats()
    locks = agent.locks()[:10]
    top = []
    has_queries = True

    try:
        top = agent.get_top_queries(limit=10)
    except Exception as ex:
        has_queries = False
        top = []

    # Format database size
    db_size_bytes = stats.get("total_db_size", 0)
    db_size_gb = round(db_size_bytes / (1024**3), 2) if db_size_bytes else 0

    comps: List[c.Component] = [
        c.Heading(text=f"📊 Performance Dashboard: {ds_id}", level=2),

        # Statistics cards
        c.Heading(text="Database Statistics", level=3),
        c.Div(components=[
            c.Div(components=[
                c.Heading(text="💾 Database Size", level=4),
                c.Heading(text=f"{db_size_gb} GB", level=5),
                c.Paragraph(text=f"{db_size_bytes:,} bytes")
            ]),
            c.Div(components=[
                c.Heading(text="👥 Active Connections", level=4),
                c.Heading(text=str(stats.get("active_backends", 0)), level=5),
                c.Paragraph(text="Current backends")
            ]),
            c.Div(components=[
                c.Heading(text="🔒 Active Locks", level=4),
                c.Heading(text=str(len(locks)), level=5),
                c.Paragraph(text="Database locks")
            ]),
        ]),

        # Quick actions
        c.Heading(text="Quick Actions", level=3),
        c.Div(components=[
            c.Button(text="🔎 Explain Query", on_click=e.GoToEvent(url=f"/ui/pages/explain?ds_id={ds_id}"), named_style="primary"),
            c.Button(text="💡 Get Recommendations", on_click=e.GoToEvent(url=f"/ui/pages/advise?ds_id={ds_id}&ai=0&sql=SELECT 1")),
        ]),
    ]

    # Top queries section
    if has_queries and top:
        comps.append(c.Heading(text="⚡ Top Queries by Execution Time", level=3))

        if top[0].get("source") == "pg_stat_activity":
            comps.append(c.Paragraph(text="⚠️ Note: pg_stat_statements unavailable. Showing currently running queries."))

        top_table_data = []
        for idx, r in enumerate(top, 1):
            query_text = r.get("query", "")
            # Truncate very long queries for display
            display_query = query_text[:200] + "..." if len(query_text) > 200 else query_text

            top_table_data.append(QueryRow(
                idx=str(idx),
                calls=str(r.get("calls", 0)),
                avg_time=f"{round(float(r.get('mean_time_ms', 0)), 2)} ms",
                rows=str(r.get("rows", 0)),
                query=display_query,
            ))

        comps.append(c.Table(data=top_table_data))
    else:
        comps.append(c.Heading(text="⚡ Top Queries", level=3))
        comps.append(c.Div(components=[
            c.Heading(text="ℹ️ Query Statistics Unavailable", level=4),
            c.Paragraph(text="pg_stat_statements extension is not available or no queries have been executed yet."),
            c.Paragraph(text="To enable: CREATE EXTENSION pg_stat_statements;"),
        ]))

    # Locks section
    comps.append(c.Heading(text="🔒 Current Database Locks", level=3))
    if locks:
        locks_data = []
        for lock in locks:
            locks_data.append(LockRow(
                locktype=lock.get("locktype", "-"),
                mode=lock.get("mode", "-"),
                granted="✅" if lock.get("granted") else "❌",
                pid=str(lock.get("pid", "-")),
                age=str(lock.get("age", "-")),
            ))
        comps.append(c.Table(data=locks_data))
    else:
        comps.append(c.Paragraph(text="✅ No active locks detected."))

    # Navigation
    comps.append(c.Div(components=[
        c.Button(text="← Back to Analyzer", on_click=e.GoToEvent(url="/ui/pages/analyze")),
        c.Button(text="🏠 Home", on_click=e.GoToEvent(url="/ui/pages/home")),
    ]))

    return [c.PageTitle(text=f"{ds_id} - Dashboard - AI DB Advisor"), c.Page(components=comps)]


@ui.get("/pages/explain", response_model=FastUI, response_model_exclude_none=True)
def page_explain(ds_id: str = Query(...), sql: Optional[str] = Query(default="")):
    comps: List[c.Component] = [
        c.Heading(text=f"🔎 Query EXPLAIN: {ds_id}", level=2),
        c.Paragraph(text="Enter your SQL query to view the execution plan. This helps identify performance bottlenecks and optimization opportunities."),
    ]

    form = c.Form(
        submit_url="/ui/pages/explain", method="GET",
        form_fields=[
            c.FormFieldInput(name="ds_id", title="", initial=ds_id, html_type="hidden"),
            FormFieldTextarea(
                name="sql",
                title="SQL Query",
                placeholder="Example: SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id WHERE u.created_at > '2024-01-01' GROUP BY u.name ORDER BY order_count DESC LIMIT 10;",
                initial=sql or "",
                required=True,
            ),
        ],
    )

    comps.append(form)

    if sql:
        try:
            agent = resolve_agent(ds_id)
            plan = agent.explain(sql, analyze=False)["plan"]

            # Extract key metrics from plan
            if plan and isinstance(plan, list) and len(plan) > 0:
                root_plan = plan[0].get("Plan", {})
                total_cost = root_plan.get("Total Cost", "N/A")
                plan_rows = root_plan.get("Plan Rows", "N/A")
                node_type = root_plan.get("Node Type", "N/A")

                comps.extend([
                    c.Heading(text="📊 Query Plan Summary", level=3),
                    c.Div(components=[
                        c.Div(components=[
                            c.Heading(text="💰 Estimated Cost", level=4),
                            c.Heading(text=str(total_cost), level=5),
                        ]),
                        c.Div(components=[
                            c.Heading(text="📦 Estimated Rows", level=4),
                            c.Heading(text=str(plan_rows), level=5),
                        ]),
                        c.Div(components=[
                            c.Heading(text="🔧 Root Node", level=4),
                            c.Heading(text=str(node_type), level=5),
                        ]),
                    ]),
                ])

            comps.extend([
                c.Heading(text="📄 Execution Plan (JSON)", level=3),
                c.Code(text=_json_pretty(plan), language="json"),

                c.Heading(text="💡 Get Optimization Recommendations", level=3),
                c.Div(components=[
                    c.Button(text="🎯 Rule-Based Advice", on_click=e.GoToEvent(url=f"/ui/pages/advise?ds_id={ds_id}&ai=0&sql={sql}"), named_style="primary"),
                    c.Button(text="🤖 AI-Powered Advice", on_click=e.GoToEvent(url=f"/ui/pages/advise?ds_id={ds_id}&ai=1&sql={sql}"), named_style="primary"),
                ]),
            ])
        except Exception as ex:
            comps.append(c.Div(components=[
                c.Heading(text="❌ Error", level=4),
                c.Paragraph(text=f"Failed to execute EXPLAIN: {str(ex)}")
            ]))

    comps.append(c.Div(components=[
        c.Button(text="← Back to Dashboard", on_click=e.GoToEvent(url=f"/ui/pages/ds/{ds_id}")),
        c.Button(text="🏠 Home", on_click=e.GoToEvent(url="/ui/pages/home")),
    ]))

    return [c.Page(components=comps)]


@ui.get("/pages/advise", response_model=FastUI, response_model_exclude_none=True)
def page_advise(ds_id: str = Query(...), sql: str = Query(...), ai: int = Query(0)):
    comps: List[c.Component] = [
        c.Heading(text=f"💡 Optimization Recommendations: {ds_id}", level=2),
        c.Paragraph(text="Get intelligent recommendations to improve query performance. Choose between rule-based analysis or AI-powered suggestions."),
    ]

    # Form to tweak SQL and resubmit
    form = c.Form(
        submit_url="/ui/pages/advise", method="GET",
        form_fields=[
            c.FormFieldInput(name="ds_id", title="", initial=ds_id, html_type="hidden"),
            c.FormFieldSelect(name="ai", title="Analysis Mode", options=[
                {"label": "🎯 Rule-Based (Fast)", "value": "0"},
                {"label": "🤖 AI-Powered (Ollama)", "value": "1"},
            ], initial=str(ai)),
            FormFieldTextarea(name="sql", title="SQL Query", initial=sql, required=True),
        ],
    )

    comps.append(form)

    try:
        agent = resolve_agent(ds_id)

        # Rule-based suggestions (always shown)
        comps.append(c.Heading(text="🎯 Rule-Based Recommendations", level=3))
        try:
            rule_recs = index_advice_pg(agent, sql) + rewrite_advice(sql)
            if rule_recs:
                for idx, r in enumerate(rule_recs, 1):
                    risk_icon = {"low": "✅", "medium": "⚠️", "high": "🚨"}.get(r.get("risk", "low"), "ℹ️")

                    card_content = [
                        c.Paragraph(text=f"**Category:** {r.get('category', 'N/A').title()}"),
                        c.Paragraph(text=f"**Risk Level:** {risk_icon} {r.get('risk', 'low').title()}"),
                    ]

                    if r.get("expected_gain"):
                        card_content.append(c.Paragraph(text=f"**Expected Gain:** {r.get('expected_gain')}"))

                    if r.get("sql_fix"):
                        card_content.extend([
                            c.Paragraph(text="**Suggested SQL:**"),
                            c.Code(text=r.get("sql_fix"), language="sql"),
                        ])

                    comps.append(c.Div(components=[
                        c.Heading(text=f"{idx}. {r.get('summary', 'Recommendation')}", level=4),
                        *card_content
                    ]))
            else:
                comps.append(c.Div(components=[
                    c.Heading(text="✅ No Issues Found", level=4),
                    c.Paragraph(text="The query looks good! No rule-based optimizations detected.")
                ]))
        except Exception as ex:
            comps.append(c.Div(components=[
                c.Heading(text="❌ Error", level=4),
                c.Paragraph(text=f"Failed to generate rule-based recommendations: {str(ex)}")
            ]))

        # AI-powered suggestions (if enabled)
        if ai:
            comps.append(c.Heading(text="🤖 AI-Powered Recommendations", level=3))
            try:
                llm = LLMClient()
                ai_sugs = ai_suggestions_for_sql_pg(agent, sql, llm)

                if ai_sugs:
                    for idx, s in enumerate(ai_sugs, 1):
                        suggestion_type = s.get("type", "note")
                        type_icon = {"index": "📊", "rewrite": "✏️", "note": "ℹ️"}.get(suggestion_type, "💡")
                        validated = s.get("validated", False)
                        validation_badge = "✅ Validated" if validated else "⚠️ Not Validated"

                        card_content = [
                            c.Paragraph(text=f"**Type:** {type_icon} {suggestion_type.title()}"),
                            c.Paragraph(text=f"**Validation:** {validation_badge}"),
                        ]

                        if s.get("rationale"):
                            card_content.append(c.Paragraph(text=f"**Rationale:** {s.get('rationale')}"))

                        if s.get("expected_gain"):
                            card_content.append(c.Paragraph(text=f"**Expected Gain:** {s.get('expected_gain')}"))

                        sql_code = s.get("new_sql") or s.get("sql_fix")
                        if sql_code:
                            card_content.extend([
                                c.Paragraph(text="**Suggested SQL:**"),
                                c.Code(text=sql_code, language="sql"),
                            ])

                        if s.get("risk"):
                            risk_icon = {"low": "✅", "med": "⚠️", "medium": "⚠️", "high": "🚨"}.get(s.get("risk", "low").lower(), "ℹ️")
                            card_content.append(c.Paragraph(text=f"**Risk:** {risk_icon} {s.get('risk', 'low').title()}"))

                        comps.append(c.Div(components=[
                            c.Heading(text=f"{idx}. {s.get('summary', 'AI Suggestion')}", level=4),
                            *card_content
                        ]))
                else:
                    comps.append(c.Div(components=[
                        c.Heading(text="ℹ️ No AI Suggestions", level=4),
                        c.Paragraph(text="The AI model did not generate any specific recommendations for this query.")
                    ]))
            except Exception as ex:
                comps.append(c.Div(components=[
                    c.Heading(text="❌ AI Error", level=4),
                    c.Paragraph(text=f"Failed to generate AI recommendations: {str(ex)}"),
                    c.Paragraph(text="Make sure Ollama is running and the configured model is available."),
                    c.Paragraph(text=f"Current config: {settings.LLM_PROVIDER} @ {settings.LLM_ENDPOINT}, model: {settings.LLM_MODEL}"),
                ]))

    except Exception as ex:
        comps.append(c.Div(components=[
            c.Heading(text="❌ Error", level=4),
            c.Paragraph(text=f"Failed to connect to data source: {str(ex)}")
        ]))

    # Navigation
    comps.append(c.Div(components=[
        c.Button(text="← Back to Dashboard", on_click=e.GoToEvent(url=f"/ui/pages/ds/{ds_id}")),
        c.Button(text="🔎 Explain Query", on_click=e.GoToEvent(url=f"/ui/pages/explain?ds_id={ds_id}&sql={sql}")),
        c.Button(text="🏠 Home", on_click=e.GoToEvent(url="/ui/pages/home")),
    ]))

    return [c.Page(components=comps)]


# ---------- HTML shell (must be last to not intercept /pages routes) ----------
@ui.get("/{path:path}", response_class=HTMLResponse)
def ui_html_shell(path: str = ""):
    """Serves the FastUI React app shell for any /ui/* route. JSON API is at /ui/pages"""
    return prebuilt_html(title="AI DB Advisor", api_root_url="/ui/pages")
