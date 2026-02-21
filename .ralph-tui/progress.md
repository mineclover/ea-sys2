# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- SQLite store pattern: keep a private `_connection()` context manager with `sqlite3.Row`, initialize schema once in `__init__`, and track versions via `schema_version`.
- For append-only `read(after=..., limit=...)`, preserve in-memory parity by using insertion order (`rowid ASC`) and treating unknown `after` IDs as "start from beginning".
- For retention cleanup parity, compute deletion candidates from the same ordered `(id, ingested_at)` rows and expose a non-mutating `cleanup_preview(...)` alongside mutating `cleanup(...)`.

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
