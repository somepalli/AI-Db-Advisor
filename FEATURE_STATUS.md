# Feature Status

## Frontend (Tauri App)

### Implemented
- Multi-view layout switches between Query Analyzer, Analytics, and Alerts, mounting the relevant panels while keeping shared state for connections (tauri-app/src/App.tsx:64).
- Connection manager persists datasources locally, syncs them to the backend, and surfaces stats/locks/top queries for the selected source (tauri-app/src/components/ConnectionPanel.tsx:22, tauri-app/src/components/ConnectionPanel.tsx:76, tauri-app/src/components/ConnectionPanel.tsx:103).
- Database explorer renders schema metadata, triggers whole-database or table-level optimization requests, and lets users apply selected SQL fixes directly (tauri-app/src/components/DBExplorer.tsx:20, tauri-app/src/components/DBExplorer.tsx:70, tauri-app/src/components/DBExplorer.tsx:136).
- SQL editor offers schema-aware autocomplete, lightweight validation, query execution with tabular results, streaming AI advice, and one-click handoff to the chat assistant (tauri-app/src/components/SQLEditorWithAutocomplete.tsx:28, tauri-app/src/components/SQLEditorWithAutocomplete.tsx:165, tauri-app/src/components/SQLEditorWithAutocomplete.tsx:224, tauri-app/src/components/SQLEditorWithAutocomplete.tsx:270).
- AI assistant streams responses from the `/ai-chat/chat/stream` endpoint, keeps multi-session history, and replays messages using the chat-history API (tauri-app/src/components/AIAssistant.tsx:28, tauri-app/src/components/AIAssistant.tsx:50, tauri-app/src/components/AIAssistant.tsx:113).
- Analytics dashboard pulls sync status, triggers whole-database replication, and visualizes KPI, trend, and distribution datasets via Recharts (tauri-app/src/components/AnalyticsDashboard.tsx:32, tauri-app/src/components/AnalyticsDashboard.tsx:83, tauri-app/src/components/AnalyticsDashboard.tsx:118).
- Alerts panel implements the three-tab workflow, auto-refresh, acknowledgement/resolution actions, and AI-driven incident analysis (tauri-app/src/components/AlertPanel.tsx:71, tauri-app/src/components/AlertPanel.tsx:85, tauri-app/src/components/AlertPanel.tsx:112).

### Needs Implementation
- Centralize API base handling for alerts; the panel hard-codes `http://127.0.0.1:8095`, bypassing the shared client and environment overrides (tauri-app/src/components/AlertPanel.tsx:71).
- Surface the optimizer approval flow in the UI; although the client defines `/suggestions` helpers, no component invokes them (tauri-app/src/api/client.ts:155).
- Provide secure, editable datasource storage instead of plain `localStorage` writes so secrets persist appropriately in the desktop runtime (tauri-app/src/components/ConnectionPanel.tsx:76).
- Extend analytics UX to support per-table or incremental sync controls rather than the blanket `syncAllTables` action (tauri-app/src/components/AnalyticsDashboard.tsx:83).
- Build UI affordances for alert rule management and monitoring lifecycle, matching the backend endpoints for create/update/delete and start/stop (tauri-app/src/api/client.ts:155, .venv/app/routers/alerts.py:490, .venv/app/routers/alerts.py:561).

## Backend APIs

### Implemented
- FastAPI orchestrates datasources, analytics, suggestions, AI chat, MCP, and alert routers while auto-starting the monitoring service and Prometheus instrumentation during lifespan events (.venv/app/main.py:28, .venv/app/main.py:118, .venv/app/main.py:134).
- Datasource router persists connections, lists them with engine metadata, and auto-enrolls them into background monitoring (.venv/app/routers/datasources.py:19, .venv/app/routers/datasources.py:31, .venv/app/routers/datasources.py:44).
- Query analysis endpoints expose schema/top queries/locks/stats, execute SQL across multiple engines, validate hypothetical indexes, and invoke AI explainers (.venv/app/routers/analyze.py:17, .venv/app/routers/analyze.py:40, .venv/app/routers/analyze.py:86, .venv/app/routers/analyze.py:128).
- Analytics endpoints coordinate Postgres→DuckDB syncs, track alignment, and provide dashboard-ready aggregates via the data sync service (.venv/app/routers/analytics.py:1, .venv/app/routers/analytics.py:68, .venv/app/routers/analytics.py:117, .venv/app/services/data_sync.py:18).
- AI chat (blocking and streaming) builds schema-aware prompts, validates generated SQL, and persists dialogue to Chroma for semantic recall (.venv/app/routers/ai_chat.py:24, .venv/app/routers/ai_chat_stream.py:24, .venv/app/services/chat_history.py:1).
- Suggestions workflow merges rule-based, AI, and validation results into unified recommendation objects, ready for dry-run or real application (.venv/app/routers/suggestions.py:27, .venv/app/services/super_agent.py:62).

### Needs Implementation
- Persist analyzed suggestions so `/suggestions/apply` can resolve IDs without clients resubmitting full objects (.venv/app/routers/suggestions.py:132).
- Add typed configuration for notification channels (SMTP/Slack) instead of relying on undeclared `Settings` attributes and empty fallbacks (.venv/app/config.py:12, .venv/app/services/notification_service.py:30).
- Reconcile the ClickHouse terminology with the current DuckDB-based sync implementation to avoid operational confusion (.venv/app/routers/analytics.py:1, .venv/app/services/data_sync.py:18).
- Harden cross-database agent support in analytics and query execution—for example, DuckDB/NoSQL paths skip plan validation and error translation (.venv/app/routers/analyze.py:182, .venv/app/services/duckdb_agent.py:70).
- Consolidate duplicate metric collector modules so the routing layer and monitoring service share one implementation (.venv/app/services/monitoring_service.py:16, .venv/app/routers/alerts.py:557, .venv/app/services/metric_collector.py:1).

## Alerts & Monitoring

### Implemented
- Alert engine ships 16 opinionated rules across P1–P3 severities, supports cooldowns, auto-resolve, and maintains active/history registries (.venv/app/services/alert_engine.py:59, .venv/app/services/alert_engine.py:200, .venv/app/services/alert_engine.py:470).
- Monitoring service runs per-datasource loops that gather metrics, evaluate rules, enrich incidents via AI, and dispatch notifications (.venv/app/services/monitoring_service.py:20, .venv/app/services/monitoring_service.py:70, .venv/app/services/monitoring_service.py:120, .venv/app/services/monitoring_service.py:272).
- Metrics collector samples database health, resource, replication, and storage indicators needed by the default rules (.venv/app/services/metrics_collector.py:24, .venv/app/services/metrics_collector.py:203, .venv/app/services/metrics_collector.py:330).
- Alert router exposes retrieval tabs, lifecycle actions, AI analysis, rule CRUD, and monitoring controls consumed by the desktop UI (.venv/app/routers/alerts.py:88, .venv/app/routers/alerts.py:129, .venv/app/routers/alerts.py:211, .venv/app/routers/alerts.py:490, .venv/app/routers/alerts.py:561).
- Notification service can email or post Slack messages with structured content, attaching AI remediation hints when available (.venv/app/services/notification_service.py:30, .venv/app/services/notification_service.py:72, .venv/app/services/notification_service.py:104).

### Needs Implementation
- Replace Windows-specific disk fallbacks and static growth estimates with platform-aware logic when deriving storage runway (.venv/app/services/metrics_collector.py:216, .venv/app/services/metrics_collector.py:403).
- Expand metric collection to handle non-Postgres engines gracefully; several queries assume PostgreSQL catalog semantics (.venv/app/services/metrics_collector.py:210, .venv/app/services/metrics_collector.py:286).
- Synchronize alert evaluation tooling so manual `/alerts/evaluate` reuses the same collector as the background service (.venv/app/routers/alerts.py:557, .venv/app/services/metrics_collector.py:24, .venv/app/services/metric_collector.py:1).
- Provide configuration/UX around notification endpoints (credentials, toggles) to make multi-channel delivery operational (.venv/app/services/notification_service.py:30).
- Expose monitoring status and configuration data through a user-facing dashboard, not just JSON endpoints (tauri-app/src/components/AlertPanel.tsx:71, .venv/app/routers/alerts.py:618).
