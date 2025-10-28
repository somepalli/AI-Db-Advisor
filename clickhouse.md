P — Purpose

Set up a production-grade ClickHouse stack in Docker, provision credentials, ingest seed data, wire a non-demo connection in our Tauri desktop app, and integrate Google’s GenAI Toolbox (MCP server for databases) so our AI chat can query ClickHouse via MCP. Also stand up monitoring + alerts and define DBA-style alert rules for ClickHouse health & performance.

Use secure defaults, idempotent scripts, and emit verifiable artifacts (compose files, .env, seed SQL/CSV, toolbox tools.yaml, Grafana dashboards/alerts). Instrument with Prometheus/Grafana and expose metrics.

R — Role

Act as:

DevOps – Docker/Docker-Compose, secrets, volumes, networks.

Data Eng – create DB/user, push sample data (CSV + SQL).

Desktop Eng – add a real ClickHouse datasource into the Tauri app’s connection manager (persisted config).

MCP Integrator – deploy genai-toolbox as an MCP server, configure a tool for ClickHouse, and expose it to our AI chat. Toolbox is an OSS MCP server for databases; use its quickstart & Docker deployment patterns.
GitHub
. Use official quickstarts for local/MCP and Docker Compose.
Google APIs
Google APIs
Google APIs
GitHub

DBA – author Prometheus alert rules & Grafana panels for ClickHouse availability, latency, errors, replicas lag, merges backlog, parts explosion, disk pressure, and memory limits. Reuse the monitoring stack patterns already documented (Prometheus, Grafana, metrics endpoints, Alertmanager).

O — Output (deliverables to produce)

docker-compose.clickhouse.yml – ClickHouse server (+ optional clickhouse-exporter) with persistent volumes, ports 9000 (native), 8123 (HTTP).

.env.clickhouse – CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DB.

seed/ – schema.sql, seed.csv, and a small loader script (load_seed.sh) using HTTP or clickhouse-client.

Tauri app: a persisted ClickHouse datasource saved to the same config store the app uses for other DBs (not a demo/temp connection). The connection must show up in the Tauri UI and be selectable in the SQL editor.

GenAI Toolbox:

toolbox/tools.yaml mapping a ClickHouse tool (read-only SELECT, DESCRIBE, LIST TABLES).

docker-compose.toolbox.yml to run the Toolbox server with this tools.yaml. Provide a simple bearer API key if Toolbox auth is enabled. Use the official docs for binary/Docker Compose or Cloud Run; prefer Docker Compose here.
Google APIs
Google APIs
Google APIs

AI chat MCP integration – register the Toolbox MCP endpoint with our app’s MCP bridge so the chat can call the ClickHouse tool. (MCP is the Anthropic-led standard to connect AI assistants to external systems.)
The Verge

If needed or preferable, you may instead (or additionally) run the ClickHouse native MCP server (mcp-clickhouse) and register it with the bridge.
GitHub
ClickHouse
ClickHouse

Monitoring & Alerts:

monitoring/prometheus.yml scrape jobs for ClickHouse/Toolbox.

monitoring/alerts.yml with alert rules listed under A — Alerts below.

Import/extend our existing dashboards; add panels for Toolbox/MCP metrics (req rate, errors, latency).

README.md with step-by-step make up, make seed, make down, and verification commands.

M — Markers (checklist the agent must follow)
1) ClickHouse up (Docker)

Create docker-compose.clickhouse.yml with:

clickhouse/clickhouse-server:latest

env: CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DB (from .env.clickhouse)

volumes: /var/lib/clickhouse, /var/log/clickhouse

ports: 9000, 8123

On first start, create DB/user if not auto-provisioned via env. Print final creds to console and write to .env.clickhouse.

Verify health:

curl http://localhost:8123/ping → Ok.

curl -u $CLICKHOUSE_USER:$CLICKHOUSE_PASSWORD 'http://localhost:8123/?query=SELECT+1'

2) Seed data

schema.sql: create 2–3 tables (e.g., events, orders, users) with proper engines (e.g., MergeTree with partitions & primary keys).

seed.csv (~1–5k rows).

load_seed.sh:

curl -u user:pass -X POST 'http://localhost:8123/?query=CREATE+TABLE…'

curl -u user:pass --data-binary @seed.csv 'http://localhost:8123/?query=INSERT+INTO+events+FORMAT+CSV'

Verify row counts & sample query.

3) Tauri connection (non-demo)

Extend the app’s datasource registry to include a ClickHouse engine (persisted). If our backend uses typed agents, implement a clickhouse_agent.py honoring the BaseAgent contract (schema, top queries, explain, stats).

Save connection in the same persistent store used by other datasources so it appears in the SQL editor and AI chat context. Expose the datasource through our API alongside others (see existing endpoints in our guide).

Test a simple SELECT count() from the editor; ensure validation and suggestions still work with this datasource flow.

4) GenAI Toolbox (MCP server) + MCP bridge

Use genai-toolbox to host an MCP server for DB tools: follow MCP quickstart & Docker Compose docs. Produce toolbox/tools.yaml pointing to our ClickHouse DSN/HTTP, with tools like list_tables, describe_table, run_query.
Google APIs
Google APIs
Google APIs

Run via docker-compose.toolbox.yml. Confirm it’s up. Record version (latest release).
GitHub

Register the Toolbox MCP endpoint with our app’s MCP bridge so AI chat can call tools (the bridge already exposes metrics we can scrape).

Alternatively or additionally, bring up mcp-clickhouse and register it (docs show direct ClickHouse MCP config).
GitHub
ClickHouse

5) Observability & Dashboards

Reuse the project’s Prometheus/Grafana setup; add scrape jobs for:

ClickHouse HTTP exporter (or direct /metrics if present)

MCP bridge (/metrics)

Toolbox server (/metrics)

Import/update dashboards; add panels: request rate, P95 latency, error rate for Toolbox/MCP; ClickHouse active merges, parts per table, insert throughput, query duration.

Verify scrape targets & Grafana connectivity.

6) Security hardening

Do not commit secrets; use .env.clickhouse.

Disable default/guesstable accounts; least-privileged ClickHouse role for Toolbox.

Enable auth for Toolbox (bearer key) if supported; otherwise restrict via network.

P — Patterns & Policies

Idempotent scripts: running twice should not fail.

No destructive defaults; never drop tables outside the seed DB.

Read-only tools for AI: allow only SELECT/DESCRIBE unless explicitly required.

Respect our MCP integration shape already used by the app (bridge server + metrics).

Keep observability first: expose metrics for every new service.

T — Tests (acceptance & verification)
Connectivity

curl http://localhost:8123/ping ⇒ Ok.

clickhouse-client --host localhost --user $U --password $P --query "SELECT count() FROM system.tables" ⇒ returns count.

Tauri datasource

New ClickHouse entry is persisted, selectable, and usable in the SQL editor; validation & suggestions still function through the existing API.

MCP & AI Chat

GET /tools from our MCP bridge lists the ClickHouse tools (via Toolbox or mcp-clickhouse).

AI chat can list tables and run a read-only SELECT via MCP.

Monitoring

Prometheus shows UP targets for ClickHouse, MCP bridge, Toolbox; Grafana dashboards render throughput/latency/error panels.

A — Alerts (DBA-style for ClickHouse)

Add these to monitoring/alerts.yml with sensible thresholds (label with severity P1/P2/P3), then wire to Alertmanager routes:

Availability / Connectivity

ClickHouseDown (P1): target down for >1m.

ClickHousePingSlow (P2): HTTP /ping latency p95 > 500ms for 5m.

Workload health

QueryErrorSpike (P1): 5xx/exception rate above baseline for 5m.

QueryLatencyHigh (P2): p95 SELECT latency > N ms for 10m.

InsertStall (P2): insert throughput drops by >80% vs hourly baseline for 10m.

Storage & Replication

DiskSpaceLow (P1): free disk < 10%.

PartsExplosion (P2): parts per table > threshold (engine-specific).

ReplicaLagHigh (P1): replication lag or queue backlog above threshold for 5m.

MergesBacklog (P2): active merges backlog consistently high for 10m.

Resources & Limits

TooManyConnections (P1): active connections near max for 5m.

MemoryLimitBreached (P1): memory limit exceeded / frequent OOMs.

CPUThrottling (P3): sustained CPU saturation.

MCP/Toolbox service health

MCPServerErrors (P2): error rate on Toolbox/MCP bridge > 5% for 5m.

MCPLatencyHigh (P3): p95 tool call latency > 2s for 10m.
Use the existing Prometheus/Grafana patterns in our repo for HTTP request rate, latency, and error panels to back these rules.

Implementation Hints (the agent may output these as files)
docker-compose.clickhouse.yml

Service clickhouse with CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DB from .env.clickhouse, volumes for data/logs, ports 8123/9000, healthcheck with /ping.

toolbox/tools.yaml

Define a ClickHouse connection (host, port 8123, db, user, password) and expose tools like list_tables, describe_table, run_query. Follow the Toolbox MCP Quickstart semantics and Docker compose guide.
Google APIs
Google APIs
Google APIs

MCP choice

Primary: GenAI Toolbox (actively maintained; recent releases).
GitHub

Optional: mcp-clickhouse (native server from ClickHouse community) if you want direct, minimal config.
GitHub
ClickHouse
ClickHouse