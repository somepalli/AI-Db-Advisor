Perfect. Here’s a **crisp, execution-ready Test Plan per sprint** (Sprints 0–11) aligned to the step-by-step roadmap you approved. Each sprint includes: Objectives, Scope, Environments, Entry/Exit, Test Data, Test Cases (unit/integration/E2E/negatives), and Acceptance Criteria. Reuse this as your QA checklist in PRs and CI.

---

# Sprint 0 — Readiness & Architecture

**Objective**: Baseline validation; config schema + dev env stable.
**Scope**: `config.yaml` schema, env vars, service boot.

**Env**: Local dev (FastAPI, Tauri), Postgres, Chroma, Redis (planned), Prometheus.
**Entry**: Branch builds; services start.
**Exit**: `make dev-up` boots without errors; config validation enforced.

**Test Data**: Minimal `config.yaml` with notifications/monitoring/agents sections.

**Tests**

* Unit

  * S0-U1: Validate pydantic model loads `config.yaml` and rejects missing/unknown keys.
  * S0-U2: Feature flags default states (incident drawer off, etc.).
* Integration

  * S0-I1: FastAPI starts; Prometheus endpoint `/metrics` exposes app metrics.
  * S0-I2: Chroma and Postgres connectivity checks.
* E2E/Smoke

  * S0-E1: Tauri launches, hits API root, shows connected status.
* Negative

  * S0-N1: Malformed `config.yaml` → startup fails with actionable error.

**Acceptance**: Clear erroring on bad config; green health checks; docs updated.

---

# Sprint 1 — Incident Intelligence Layer

**Objective**: Persist incidents/findings/approvals + correlation + SSE incident events.
**Scope**: DB migrations, CRUD, `/similar`, SSE “incident”.

**Env**: Postgres with `pgvector` enabled, FastAPI SSE.

**Test Data**

* TD1: Three sample incidents (lock spike, disk, 5xx surge) with labels.
* TD2: Embeddings enabled.

**Tests**

* Unit

  * S1-U1: Migrations create tables with keys/indexes.
  * S1-U2: Embedding writer computes and stores cosine-searchable vectors.
* Integration

  * S1-I1: `POST /incidents` → `GET /incidents/{id}` returns all fields.
  * S1-I2: `POST /incidents/{id}/ack|resolve` transitions status (+timestamps).
  * S1-I3: `/incidents/{id}/similar?topk=5` returns nearest neighbors (self excluded).
  * S1-I4: SSE pushes `{type:"incident"}` event on create/update.
* E2E

  * S1-E1: Create incident → Tauri receives incident event → drawer shows title/priority.
* Negative

  * S1-N1: Missing fields → 422 with schema hints.
  * S1-N2: SSE disconnect → client reconnect resumes stream.

**Acceptance**: CRUD + correlation working; SSE visible in UI; status transitions logged.

---

# Sprint 2 — Agent Orchestration

**Objective**: Triage/Diagnosis/Advisor agents via Redis/pub-sub with HITL boundary.
**Scope**: Queues, workers, agent outputs persisted as findings.

**Env**: Redis (or in-proc bus), MCP connected to a test Postgres.

**Test Data**

* TD1: Fake alert payload: lock spike (wait_event/pg_locks).
* TD2: Long-running query + sample `pg_stat_activity`.

**Tests**

* Unit

  * S2-U1: Queue push/pop, backoff, poison-message handling.
  * S2-U2: Triage rules map payload → P1–P4 correctly.
* Integration

  * S2-I1: Alert→Triage→Diagnosis→Advisor pipeline populates `findings`.
  * S2-I2: Diagnosis MCP calls are read-only and time-boxed.
  * S2-I3: Advisor outputs SQL + rollback notes in findings.
* E2E

  * S2-E1: Inject alert → UI shows P2 incident → findings appear with evidence and SQL.
* Negative/Safety

  * S2-N1: No queue consumer → incidents remain pending (no crash).
  * S2-N2: Agent exception → incident notes log failure; retries capped.
  * S2-N3: Ensure **no execution** occurs without approval (audit check).

**Acceptance**: Pipeline runs end-to-end; findings persisted; no auto-exec.

---

# Sprint 3 — Frontend Unified Incident Console

**Objective**: Incident Drawer + inline approvals; secure vault for connections; API base centralization.
**Scope**: SSE consumption, HITL UI, secure storage.

**Env**: Tauri with OS keyring/Tauri secure store.

**Test Data**

* TD1: One incident with SQL fix suggestion.
* TD2: Existing connections in `localStorage` (migration path).

**Tests**

* Unit

  * S3-U1: API client respects env/base URL; no hardcoded host.
  * S3-U2: Secure vault encrypts/decrypts entries; migration succeeds.
* Integration

  * S3-I1: SSE stream renders live incident card with priority chips.
  * S3-I2: Approve/Reject buttons call backend and update UI state.
* E2E

  * S3-E1: Migrate connections → restart app → connections intact & decrypted.
* UX/Negatives

  * S3-N1: Offline UI shows cached last 50 incidents; actions disabled with tooltip.
  * S3-N2: Approval without required confirmation → blocked with message.

**Acceptance**: Approvals work; secrets secured; base URL central; graceful offline.

---

# Sprint 4 — Suggestions Registry & Apply-by-ID

**Objective**: Persist suggestions, apply via ID, dry-run/real-run toggle.
**Scope**: `suggestions` table, endpoints, UI binding.

**Test Data**

* TD1: Suggestion object with `sql_fix`, checksum, linked finding.
* TD2: Dry-run result sample.

**Tests**

* Unit

  * S4-U1: Checksum prevents duplicate suggestion rows.
  * S4-U2: Serialization/deserialization fidelity for suggestion body.
* Integration

  * S4-I1: `GET /suggestions?id=` returns stored payload.
  * S4-I2: `/suggestions/apply?id=…&mode=dryrun|apply` flows and audits.
* E2E

  * S4-E1: Approve suggestion from UI → backend apply-by-ID → audit entry created.
* Negative

  * S4-N1: Invalid ID → 404 with helpful message.
  * S4-N2: Apply in locked environment (read-only) → blocked, user notice.

**Acceptance**: Suggestions survive refresh; apply-by-ID + audit pass.

---

# Sprint 5 — Rule & Monitoring Management

**Objective**: Single collector, rule CRUD + test, start/stop monitoring.
**Scope**: Merge collectors; UI rule editor.

**Test Data**

* TD1: Create rule “p95 latency > X”.
* TD2: Datasource start/stop scenarios.

**Tests**

* Unit

  * S5-U1: Collector functions are shared by service & `/alerts/evaluate`.
* Integration

  * S5-I1: `POST/PUT/DELETE /alerts/rules` modifies live rule set.
  * S5-I2: `POST /alerts/test` returns preview (hit/miss) with sample metrics.
  * S5-I3: `/monitoring/{ds}/start|stop|status` works per datasource.
* E2E

  * S5-E1: Create/edit rule in UI → visible in list → test preview matches expectation.
* Negative

  * S5-N1: Invalid rule JSON → schema error with line/field.
  * S5-N2: Stop monitoring on active P1 → warning prompt required.

**Acceptance**: Single collector in use; rule lifecycle + monitoring controls stable.

---

# Sprint 6 — Incremental & Targeted Analytics

**Objective**: Per-table/Incremental DuckDB sync with watermarks & lineage.
**Scope**: Extended sync API + UI toggles.

**Test Data**

* TD1: Two tables (`orders`, `payments`) with timestamp columns.
* TD2: Watermark initial time and delta changes.

**Tests**

* Unit

  * S6-U1: Watermark read/write per table.
* Integration

  * S6-I1: `/analytics/sync` modes: all/table/incremental behave as specified.
  * S6-I2: Row counts before/after; only deltas processed for incremental.
* E2E

  * S6-E1: Toggle `orders` only → only that table syncs; lineage displays.
* Negative

  * S6-N1: Missing watermark column → graceful fallback + warning.
  * S6-N2: Concurrent sync attempts → serialized or rejected with 409.

**Acceptance**: Correct deltas; lineage visible; controls intuitive.

---

# Sprint 7 — Notifications & Escalation Policy

**Objective**: Config-driven channels; severity routing; test-send.
**Scope**: Startup validation; `/notifications/status`.

**Test Data**

* TD1: Valid SMTP + Slack webhook; one invalid config.

**Tests**

* Unit

  * S7-U1: Config parser validates required fields per channel.
* Integration

  * S7-I1: `POST /notifications/test` sends to enabled channels.
  * S7-I2: P1 incident triggers Slack+Email+Popup; P2 Email; P3/4 In-App only.
* E2E

  * S7-E1: Toggle channel OFF in UI → status updates → deliveries stop.
* Negative

  * S7-N1: Bad SMTP credentials → startup fails fast with clear error.
  * S7-N2: Slack 429 rate limit → exponential backoff, no crash, log notice.

**Acceptance**: Policies enforced; misconfig surfaced; test-send reliable.

---

# Sprint 8 — P4 Informational + Predictive Insights

**Objective**: Add P4 early warnings + suppression + digest.
**Scope**: New rules, suppression model, weekly digest job.

**Test Data**

* TD1: Synthetic trend to trigger index drift/stat staleness.
* TD2: User suppression with expiry.

**Tests**

* Unit

  * S8-U1: Suppression checks exclude suppressed incidents from active list.
  * S8-U2: Digest composer groups by rule and datasource.
* Integration

  * S8-I1: P4 rules fire → UI shows info badge + Learn More link/runbook.
  * S8-I2: Suppression hides item; reappears after expiry.
  * S8-I3: Digest email/slack summary sent with counts/links.
* E2E

  * S8-E1: End-to-end from rule trigger to digest delivery with links opening incidents.
* Negative

  * S8-N1: Multiple suppressions on same rule → deduped.

**Acceptance**: P4 usable without noise; digest accurate.

---

# Sprint 9 — Memory & Knowledge

**Objective**: Memory graph (in Postgres) + KB generation + retrieval in agents/UI.
**Scope**: entities/edges, kb_entries, similarity search.

**Test Data**

* TD1: Past resolved incident with approved fix and performance delta.
* TD2: New similar incident.

**Tests**

* Unit

  * S9-U1: KB embedding stored and indexed.
  * S9-U2: Entity/edge upsert idempotency.
* Integration

  * S9-I1: On `resolve`, KB entry auto-created (title/body/tags/embedding).
  * S9-I2: `GET /incidents/{id}/similar` includes KB references.
  * S9-I3: Agents query KB first; include citation in findings.
* E2E

  * S9-E1: New similar incident shows “Previously resolved” card with 1-click view.
* Negative

  * S9-N1: KB disabled via config → agents fall back to standard diagnosis.

**Acceptance**: KB creation + recall improves suggestions measurably (manual spot-check).

---

# Sprint 10 — Explainability, Safety, Audit

**Objective**: Reason traces, confidence, freshness; rollback enforcement; append-only audit.
**Scope**: Explainability UI, execution gates, exporter.

**Test Data**

* TD1: Sample finding with rules fired + metric evidence.
* TD2: Suggestion with rollback SQL.

**Tests**

* Unit

  * S10-U1: Confidence/freshness computed and bounded [0..1].
  * S10-U2: Audit writer uses append-only file/stream with checksum.
* Integration

  * S10-I1: UI shows rationale (rules/evidence/LLM summary).
  * S10-I2: Approval requires tick + confirmation type-in (e.g., “APPLY”).
  * S10-I3: Audit export `/audit/export` returns .jsonl with full chain.
* E2E

  * S10-E1: Full cycle from alert→approval→audit export is traceable.
* Negative

  * S10-N1: Missing rollback → suggestion blocked with error.

**Acceptance**: Transparent reasoning; guarded actions; complete audit trail.

---

# Sprint 11 — Integrations

**Objective**: Grafana deep links; optional Slack/Jira ticketing.
**Scope**: Link builders; webhook connectors.

**Test Data**

* TD1: Grafana URL template with variables.
* TD2: Slack/Jira test endpoints (mock or sandbox).

**Tests**

* Unit

  * S11-U1: Link builder substitutes datasource/incident variables correctly.
* Integration

  * S11-I1: “Open in Grafana” button leads to filtered dashboard/panel.
  * S11-I2: P1/P2 incident creates Slack thread/Jira ticket; external IDs stored.
* E2E

  * S11-E1: From incident, open Grafana, then jump back to incident from link.
* Negative

  * S11-N1: Connector disabled → UI hides buttons gracefully.

**Acceptance**: Links/tickets reliable; IDs persisted; UX consistent.

---

## Cross-Sprint Regression Pack (run every sprint)

* R1: SSE reconnect behavior (network flap) recovers without losing messages.
* R2: Read-only MCP contract holds (no accidental DDL/DML).
* R3: Large incident list (1k+) pagination, search, and filter performance.
* R4: Role checks (Admin vs Analyst) for approvals and rule edits.
* R5: Secrets never logged; PII redaction passes log scan.
* R6: Basic load: 50 incidents/min for 5 minutes—no dropped events, acceptable latency.

## Tooling & Automation

* CI: pytest markers `@sprintN`, integration via docker-compose (Postgres, Redis, Chroma).
* Contract tests for APIs via OpenAPI schema + Dredd/Prism.
* UI tests: Playwright scripts for drawer, approvals, rule editor, sync toggles.
* Synthetic metrics generator to trigger rules deterministically.

---

### Final Acceptance Gate (per milestone)

* **M1 (S1–S3)**: Incidents stream, agents produce findings, approvals recorded, secrets secure.
* **M2 (S4–S6)**: Suggestions registry works; rules editable/testable; targeted sync verified.
* **M3 (S7–S8)**: Policies honored; P4 insights + digest, suppression effective.
* **M4 (S9–S10)**: KB creation/reuse; explainability, safety, and audit pass.
* **M5 (S11)**: Grafana deep links + optional Slack/Jira connectors stable.

If you want, I can turn this into **Jira Epics → Stories → Test Cases** (CSV import) or generate **Playwright + pytest** skeletons named exactly as above.
