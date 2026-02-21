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
