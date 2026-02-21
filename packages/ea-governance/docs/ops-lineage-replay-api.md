# Lineage Replay API

> Canonical combined API + operations runbook: `packages/ea-governance/docs/ops-events-api-runbook.md`

## Endpoint
- `GET /governance/lineage-replay/{decision_id}`

## Purpose
- Replays decision-trace lineage (`decision_trace_ops`) to expose the causal chain between decision, operation, and model nodes.

## Success Response (`200`)
- `decision_id`: replay target decision id
- `status`: `ok` or `warning`
- `replayed_nodes`: replayed lineage nodes
- `path_to_latest_operation`: composed path from cause/start node to latest operation
- `missing_required_relations`: missing required lineage relation names
- `path_error`: compose error text when the path is disconnected, otherwise `null`
- `warnings`: warning list with `code`, `message`, and optional `details`

## Path-Disconnection Warning Contract
- Path disconnection does **not** fail the request. The API returns `200` with `status=warning`.
- Warning code: `lineage_path_disconnected`
  - `details.path_error` contains the compose failure reason.
- If required lineage relations are missing, warning code `lineage_missing_required_relations` is also returned.

## Error Contract
- `422 lineage_replay_validation_error`
  - Returned when `decision_id` is invalid.
  - Envelope: `error`, `message`, `issues[]` (`field`, `message`)
- `404 lineage_replay_not_found`
  - Returned when the decision trace does not exist.
  - Envelope: `error`, `message`
