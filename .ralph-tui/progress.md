# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- SQLite store pattern: keep a private `_connection()` context manager with `sqlite3.Row`, initialize schema once in `__init__`, and track versions via `schema_version`.
- For append-only `read(after=..., limit=...)`, preserve in-memory parity by using insertion order (`rowid ASC`) and treating unknown `after` IDs as "start from beginning".
- For retention cleanup parity, compute deletion candidates from the same ordered `(id, ingested_at)` rows and expose a non-mutating `cleanup_preview(...)` alongside mutating `cleanup(...)`.
- Router-level write APIs can keep validation deterministic by splitting errors into typed issue entries (`field`, `message`) and returning a stable 422 envelope from the endpoint layer.
- For bulk write APIs using fixed partial-failure strategy, keep HTTP 200 with `strategy/success_count/failed_count/results[]` and reuse the same validation envelope per failed item with `items[{index}].`-prefixed fields.
- For ops-event list APIs backed by generic layer snapshots, parse `ingested_at` to UTC and sort by that timestamp (not `model_id`) before applying `limit/offset`, so pagination stays chronological.
- For lineage replay APIs, return partial lineage data with `status=warning` + structured `warnings[]` on path disconnection instead of failing the whole request, while keeping 422/404 envelopes for invalid/missing decisions.
- For policy-gated optional actions (like auto-express), compute a single structured decision (`requested`, `allowed`, `reason_codes`) and persist the same structure to snapshot/event/response so diagnostics stay deterministic across layers.
- For auto-expressed ops→needs flow, reuse one `expressed_need` object (`catalog_id`, `need_id`, `lineage_id`, `version`) across transaction events and ingestion responses to keep audit/API parity deterministic.
- For operational APIs, keep one canonical docs/runbook file under the package `docs/` directory and reference it from both module-level entrypoints and package README to prevent contract drift.

---

## 2026-02-21 - US-002
- What was implemented
  - Added `OpsEventRetentionPolicy` model with `max_age_days` and `max_records` (non-negative validation).
  - Added `OpsEventCleanupResult` and retention planning helper shared by in-memory and SQLite stores.
  - Added `cleanup_preview(...)` (non-mutating before/after/deleted counts) and `cleanup(...)` (actual delete) to `InMemoryOpsEventStore` and `SQLiteOpsEventStore`.
  - Implemented retention semantics for age-based expiry and max-record cap while preserving append insertion order.
  - Added retention/cleanup tests for policy validation, age cleanup preview+execution, max-record cleanup, and in-memory parity.
- Files changed
  - `packages/ea-infra/src/ea_infra/ops_ingestion.py`
  - `packages/ea-infra/src/ea_infra/__init__.py`
  - `packages/ea-infra/tests/test_ops_ingestion.py`
  - `.ralph-tui/progress.md`
- **Learnings:**
  - Patterns discovered
    - Age and count retention can be made backend-agnostic by planning deletions from ordered `(id, ingested_at)` tuples, then applying that plan per backend.
  - Gotchas encountered
    - Existing `ingested_at` format includes a trailing `Z` even when offset is already present (`+00:00Z`), so cleanup parsing must normalize this before `datetime.fromisoformat(...)`.
---

## 2026-02-21 - US-001
- What was implemented
  - Added `SQLiteOpsEventStore` in `ea-infra` with append-only persistence for ops events.
  - Stored fields include `event_name`, `severity`, `feeds_back_to`, `trace_id`, `lineage_id`, `payload`, `ingested_at`.
  - Kept `append/read/count` API compatible with `InMemoryOpsEventStore`.
  - Updated `OpsEventRecord` to expose `event_name` and kept `name` as a backward-compatible alias.
  - Added unit tests for SQLite append/read/count, persistence across instances, `after/limit` behavior, and invalid limit handling.
- Files changed
  - `packages/ea-infra/src/ea_infra/ops_ingestion.py`
  - `packages/ea-infra/src/ea_infra/__init__.py`
  - `packages/ea-infra/tests/test_ops_ingestion.py`
  - `.ralph-tui/progress.md`
- **Learnings:**
  - Patterns discovered
    - Existing repo SQLite stores consistently use `schema_version` + explicit index creation; following this pattern keeps future migrations straightforward.
    - JSON payload fields are persisted as `*_json` text columns and materialized back to typed dicts at read boundaries.
  - Gotchas encountered
    - `uv run` attempted to use restricted cache/proxy paths in this sandbox; using `UV_CACHE_DIR=.uv-cache` and `--no-sync` stabilized lint/test execution.
---

## 2026-02-21 - US-003
- What was implemented
  - Added a single-event ingestion endpoint to ea-governance API router: `POST /governance/ops-events/ingest`.
  - Added request models for `ServiceOpsEventSpec + payload` contract and validated both spec-level and payload-level rules before ingestion.
  - Wired the endpoint to `GovernanceContainer.ingest_service_ops_event(...)` with support for optional `catalog_id`, `stakeholder_id`, `auto_express`, `tags`, and `actor`.
  - Added a stable structured 422 validation error envelope (`error`, `message`, `issues[]`) for contract failures.
  - Extended success response to always include `transaction_id`, `trace_id`, `lineage_id`, and `snapshot_id` (with infra/feedback snapshot IDs preserved).
  - Added API router tests for success and structured validation failures.
- Files changed
  - `packages/ea-governance/src/ea_governance/api_router.py`
  - `packages/ea-governance/tests/test_api_router.py`
  - `.ralph-tui/progress.md`
- **Learnings:**
  - Patterns discovered
    - Endpoint-level validation can combine domain validators (`validate_service_ops_event_spec`, `validate_service_ops_payload`) with stable API error envelopes to keep contract failures machine-parseable.
  - Gotchas encountered
    - The shared governance router is included by `ea-kernel` and may execute before container initialization, so endpoint code must resolve `app.state.governance_container` defensively.
---

## 2026-02-21 - US-004
- What was implemented
  - Added bulk ingestion endpoint to governance API router: `POST /governance/ops-events/ingest/bulk` with array input (`list[ServiceOpsIngestionRequest]`).
  - Fixed bulk API contract to a partial-failure strategy (`strategy = "partial"`): endpoint returns `success_count`, `failed_count`, and item-level `results[]` with `success`/`failed` status.
  - Reused the existing structured validation envelope (`error`, `message`, `issues[]`) per failed bulk item, prefixing issue fields as `items[{index}].*` for deterministic client parsing.
  - Added request-level trace/lineage correlation validation for bulk ingestion: all items must correlate to the same `trace_id` and `lineage_id`; mismatches fail only the offending item under partial strategy.
  - Added API router tests covering full-success bulk ingest, partial-failure behavior contract, and trace/lineage correlation mismatch validation.
- Files changed
  - `packages/ea-governance/src/ea_governance/api_router.py`
  - `packages/ea-governance/tests/test_api_router.py`
  - `.ralph-tui/progress.md`
- **Learnings:**
  - Patterns discovered
    - Bulk ingestion can stay machine-friendly by embedding the exact single-item validation envelope into each failed result entry and making fields index-addressable (`items[{index}].field`).
  - Gotchas encountered
    - Correlation checks should run after per-item spec/payload validation and only compare non-empty IDs, to avoid noisy duplicate errors when required fields are already missing.
---

## 2026-02-21 - US-005
- What was implemented
  - Added ops event query endpoints to governance router:
    - `GET /governance/ops-events` (list with filtering + `limit/offset`)
    - `GET /governance/ops-events/{event_id}` (single event lookup)
  - Implemented list filters for `trace_id`, `lineage_id`, `event_name`, and time range (`ingested_from`, `ingested_to`).
  - Added list response pagination contract with `total`, `limit`, `offset`, and `items`.
  - Normalized timestamp parsing for stored ops event timestamps (`...+00:00Z`) and added structured 422 query validation for invalid time parameters.
  - Added API tests for pagination, correlation/time-range filtering, and get success/404 behavior.
- Files changed
  - `packages/ea-governance/src/ea_governance/api_router.py`
  - `packages/ea-governance/tests/test_api_router.py`
  - `.ralph-tui/progress.md`
- **Learnings:**
  - Patterns discovered
    - Reconstructing ops-event read views from infra snapshots is reliable when `kind=service_ops_event` is treated as the boundary and response fields are normalized (`event_name` from `event_name|name`).
  - Gotchas encountered
    - Stored timestamps currently include a trailing `Z` even with an offset (`+00:00Z`), so direct `datetime.fromisoformat(...)` requires normalization before filter/sort comparisons.
---

## 2026-02-21 - US-006
- What was implemented
  - Added lineage replay endpoint: `GET /governance/lineage-replay/{decision_id}`.
  - Wired the endpoint to `decision_trace_ops` exploration data via `GovernanceContainer.explore_model_decision_trace(...)`.
  - Exposed replay contract fields required by the story: `replayed_nodes`, `path_to_latest_operation`, `missing_required_relations`.
  - Added path disconnection diagnostics contract:
    - `HTTP 200` with `status=warning` and structured `warnings[]` (`lineage_path_disconnected`, `lineage_missing_required_relations`).
    - Validation and missing-trace errors use stable envelopes (`422 lineage_replay_validation_error`, `404 lineage_replay_not_found`).
  - Added API documentation for endpoint/response/error-warning contract.
- Files changed
  - `packages/ea-governance/src/ea_governance/api_router.py`
  - `packages/ea-governance/tests/test_api_router.py`
  - `packages/ea-governance/docs/ops-lineage-replay-api.md`
  - `.ralph-tui/progress.md`
- **Learnings:**
  - Patterns discovered
    - Path compose failure is better represented as a warning-state replay response (with partial chain payload) than a hard API failure, so clients can still render available lineage evidence.
  - Gotchas encountered
    - Replay output should sanitize lineage arrays defensively (`list[dict]`, `list[str]`) because exploration payloads are generic mappings and can include malformed rows.
---

## 2026-02-21 - US-007
- What was implemented
  - Added catalog-level auto-express policy domain model + evaluator with criteria checks for `severity`, `event_name`, `feeds_back_to`, and stakeholder mapping.
  - Added SQLite-backed catalog policy table store with `schema_version` tracking and `save/get/list` support.
  - Wired policy storage into `GovernanceContainer` and exposed policy CRUD delegates for catalog-level governance control.
  - Updated `ingest_service_ops_event(...)` to evaluate policy before auto-express execution and gate need creation on the evaluation result.
  - Added structured policy decision payload (`requested`, `allowed`, `reason_codes`, `policy_found`) to feedback snapshot, transaction event, and ingestion response.
  - Added tests for policy persistence, criteria evaluation pass/fail paths, and policy-miss reason-code behavior.
- Files changed
  - `packages/ea-governance/src/ea_governance/catalog_policy_store.py`
  - `packages/ea-governance/src/ea_governance/facade.py`
  - `packages/ea-governance/src/ea_governance/needs_ops.py`
  - `packages/ea-governance/tests/test_catalog_policy_store.py`
  - `packages/ea-governance/tests/test_needs_store.py`
  - `.ralph-tui/progress.md`
- **Learnings:**
  - Patterns discovered
    - Evaluating policy once and reusing the exact serialized decision object across persistence/audit/API boundaries keeps failure reasoning stable for debugging and client parsing.
  - Gotchas encountered
    - `catalog_id`/`stakeholder_id` should be normalized (`strip`) before policy lookup; blank strings otherwise silently bypass keyed policy checks.
---

## 2026-02-21 - US-008
- What was implemented
  - Verified the auto-expression execution path after policy-pass already creates a need in the catalog and increments need count on ingestion.
  - Strengthened ingest integration test assertions to verify auto-expression reflection payload (`need_id`, `lineage_id`, `version`) is consistently recorded in both response and transaction events.
  - Verified infra snapshot and needs feedback snapshot creation behavior in the ingest flow through story-scoped tests.
- Files changed
  - `packages/ea-governance/tests/test_needs_store.py`
  - `.ralph-tui/progress.md`
- **Learnings:**
  - Patterns discovered
    - A single shared `expressed_need` payload reused across `service_ops_event_ingested` and `needs_expressed_from_service_ops` events plus API/container response prevents drift between audit and client-facing contracts.
  - Gotchas encountered
    - Existing ingest tests validated need-count increase but did not explicitly pin `need_id/lineage_id/version` parity across all emitted transaction events; adding these checks prevents silent contract regressions.
---

## 2026-02-21 - US-009
- What was implemented
  - Added a canonical governance ops API + operations runbook document covering single/bulk ingestion, list/get, and lineage replay contracts.
  - Documented runbook procedures for validation failures (`422`), bulk partial failures (`200` with failed items), and retention cleanup (`cleanup_preview` + `cleanup`).
  - Added reproducible manual smoke procedure with server startup, curl calls, and expected verification points.
  - Linked the canonical docs from `ea_governance.api_router` module docstring and `ea-governance` package README.
- Files changed
  - `packages/ea-governance/docs/ops-events-api-runbook.md`
  - `packages/ea-governance/docs/ops-lineage-replay-api.md`
  - `packages/ea-governance/src/ea_governance/api_router.py`
  - `packages/ea-governance/README.md`
  - `.ralph-tui/progress.md`
- **Learnings:**
  - Patterns discovered
    - Keeping one canonical ops API/runbook document and linking it from both runtime entrypoints and README reduces drift between implementation and operations docs.
  - Gotchas encountered
    - Bulk ingestion partial failures return `HTTP 200`, so runbooks must explicitly instruct operators to treat `failed_count > 0` as failure.
---
