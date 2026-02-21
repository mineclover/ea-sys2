# Ops Events API Spec + Operations Runbook

본 문서는 `ea_governance.api_router`의 운영 이벤트 API 계약과 운영 절차를 한 곳에 정리한 기준 문서다.

## Scope

- 단건 수집: `POST /governance/ops-events/ingest`
- 대량 수집: `POST /governance/ops-events/ingest/bulk`
- 목록 조회: `GET /governance/ops-events`
- 단건 조회: `GET /governance/ops-events/{event_id}`
- 라인리지 재생: `GET /governance/lineage-replay/{decision_id}`

## 공통 계약

### Validation Error Envelope (`422`)

검증 실패는 FastAPI `HTTPException` 규약에 따라 다음처럼 반환된다.

```json
{
  "detail": {
    "error": "ops_event_validation_error",
    "message": "Service ops ingestion request failed validation",
    "issues": [
      {"field": "payload.trace_id", "message": "missing required ops field: trace_id"}
    ]
  }
}
```

- `issues[].field`는 머신 파싱이 가능하도록 안정적인 경로를 사용한다.
- bulk 실패 항목은 `items[{index}].*` prefix를 사용한다.

## API 명세

### 1) `POST /governance/ops-events/ingest`

단건 서비스 운영 이벤트를 수집한다.

Request body:

```json
{
  "spec": {
    "name": "slo_breached",
    "severity": "high",
    "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
    "feeds_back_to": "needs"
  },
  "payload": {
    "trace_id": "trace-api-001",
    "lineage_id": "lineage-api-001",
    "service_id": "payments-api",
    "slo_name": "latency_p95"
  },
  "catalog_id": "catalog-001",
  "stakeholder_id": "stakeholder-001",
  "auto_express": false,
  "tags": ["ops", "slo"],
  "actor": "ops-bot"
}
```

검증 규칙(요약):

- `spec.name`: `^[a-z0-9][a-z0-9._-]{2,63}$`
- `spec.must_include`: 중복 금지, `trace_id`, `lineage_id` 필수
- `severity=critical`이면 `must_include`에 `runbook_url` 또는 `incident_id` 포함
- `payload`는 `must_include` 필드를 모두 채워야 함

Success (`200`) 핵심 응답 필드:

- `transaction_id`, `trace_id`, `lineage_id`
- `infra_snapshot_id`, `feedback_snapshot_id`, `snapshot_id`
- `needs_feedback_draft`
- `auto_express_decision` (`requested`, `allowed`, `reason_codes`, `policy_found`, `catalog_id`)
- `expressed_need` (`catalog_id`, `need_id`, `lineage_id`, `version`) 또는 `null`

### 2) `POST /governance/ops-events/ingest/bulk`

여러 이벤트를 고정 전략 `partial`로 수집한다.

Success/Partial (`200`) 응답:

```json
{
  "strategy": "partial",
  "success_count": 1,
  "failed_count": 1,
  "results": [
    {"index": 0, "status": "success", "result": {"transaction_id": "tx-api-001"}},
    {
      "index": 1,
      "status": "failed",
      "error": {
        "error": "ops_event_validation_error",
        "message": "Service ops ingestion request failed validation",
        "issues": [{"field": "items[1].payload.slo_name", "message": "missing required ops field: slo_name"}]
      }
    }
  ]
}
```

운영상 중요 포인트:

- 부분 실패여도 HTTP status는 항상 `200`
- 빈 리스트 요청만 `422` (`items` 최소 1개)
- bulk 내부 trace/lineage 상관관계가 다르면 해당 항목만 실패

### 3) `GET /governance/ops-events`

운영 이벤트 목록 조회.

Query:

- `trace_id`, `lineage_id`, `event_name`
- `ingested_from`, `ingested_to` (ISO-8601)
- `limit` (default `100`, `>=0`), `offset` (default `0`, `>=0`)

응답:

```json
{
  "total": 3,
  "limit": 2,
  "offset": 1,
  "items": [
    {
      "id": "service_ops_event:evt-002",
      "event_name": "slo_recovered",
      "severity": "medium",
      "feeds_back_to": "needs",
      "trace_id": "trace-001",
      "lineage_id": "lineage-001",
      "payload": {},
      "ingested_at": "2026-02-21T10:05:00+00:00Z"
    }
  ]
}
```

정렬/페이지네이션 규칙:

- `ingested_at`를 UTC로 파싱 후 내림차순 정렬
- 정렬 후 `offset`, `limit` 적용

검증 오류:

- 잘못된 timestamp 형식, 또는 `ingested_from > ingested_to`이면 `422 ops_event_query_validation_error`

### 4) `GET /governance/ops-events/{event_id}`

단건 이벤트 조회.

- 성공: `200` + 이벤트 본문
- 실패: `404 ops_event_not_found`

`event_id`는 infra snapshot id (`service_ops_event:*`)를 사용한다.

### 5) `GET /governance/lineage-replay/{decision_id}`

의사결정 라인리지 재생 조회.

성공 (`200`) 필드:

- `decision_id`
- `status`: `ok` | `warning`
- `replayed_nodes`
- `path_to_latest_operation`
- `missing_required_relations`
- `path_error`
- `warnings[]` (`code`, `message`, optional `details`)

Warning 계약:

- 경로 단절은 실패가 아니라 `status=warning`으로 반환
- `lineage_path_disconnected`, `lineage_missing_required_relations` 사용

오류 계약:

- `422 lineage_replay_validation_error`
- `404 lineage_replay_not_found`

## 운영 Runbook

### A) 검증 실패(422) 대응

1. `detail.error` 코드 확인 (`ops_event_validation_error`, `ops_event_query_validation_error`, `lineage_replay_validation_error`).
2. `detail.issues[]`를 `field` 단위로 분류해 입력 데이터 생성 경로를 수정한다.
3. bulk의 경우 `items[{index}]`로 실패 항목만 재시도한다.

### B) bulk 부분 실패(HTTP 200) 대응

1. `failed_count > 0`이면 실패로 판단한다.
2. `results[].status == "failed"` 항목의 `error.issues[]`를 기준으로 재시도 payload를 구성한다.
3. 이미 성공한 인덱스는 재전송하지 않는다(중복 수집 방지).

### C) Cleanup 절차 (Retention)

현재 ops-event retention cleanup은 API 엔드포인트가 아니라 스토어 레벨에서 수행한다.
(`ea_infra.SQLiteOpsEventStore`, `OpsEventRetentionPolicy`)

운영 순서:

1. 대상 DB 백업.
2. `cleanup_preview(...)`로 삭제 예정 수량 확인.
3. 검증 후 `cleanup(...)` 실행.
4. `count()` 및 샘플 `read(limit=...)`로 결과 검증.

예시:

```bash
UV_CACHE_DIR=.uv-cache uv run --no-sync python - <<'PY'
from datetime import UTC, datetime
from ea_infra import SQLiteOpsEventStore, OpsEventRetentionPolicy

db_path = "governance_data/ops-events.db"  # 운영 환경 경로로 교체
store = SQLiteOpsEventStore(db_path)
policy = OpsEventRetentionPolicy(max_age_days=30, max_records=20000)
now = datetime.now(UTC)

preview = store.cleanup_preview(policy, now=now)
print("preview", preview)

result = store.cleanup(policy, now=now)
print("cleanup", result)
print("count", store.count())
PY
```

## 수동 Smoke 절차 (문서 기준 재현)

### 0) 서버 기동

```bash
export EA_KERNEL_DATA_DIR=./governance_data
UV_CACHE_DIR=.uv-cache uv run --no-sync python -m ea_kernel.api.server
```

별도 터미널에서:

```bash
BASE_URL=http://localhost:8000
```

### 1) 단건 ingest 성공 확인

```bash
curl -sS -X POST "$BASE_URL/governance/ops-events/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "spec": {
      "name": "slo_breached",
      "severity": "high",
      "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
      "feeds_back_to": "needs"
    },
    "payload": {
      "trace_id": "trace-smoke-001",
      "lineage_id": "lineage-smoke-001",
      "service_id": "payments-api",
      "slo_name": "latency_p95"
    },
    "actor": "smoke-tester"
  }'
```

검증:

- HTTP `200`
- `transaction_id`, `trace_id`, `lineage_id`, `snapshot_id` 존재

### 2) 단건 ingest 검증 실패 확인

```bash
curl -sS -X POST "$BASE_URL/governance/ops-events/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "spec": {
      "name": "slo_breached",
      "severity": "high",
      "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
      "feeds_back_to": "needs"
    },
    "payload": {
      "trace_id": "trace-smoke-002",
      "lineage_id": "lineage-smoke-002",
      "service_id": "payments-api"
    }
  }'
```

검증:

- HTTP `422`
- `detail.error == "ops_event_validation_error"`
- `detail.issues`에 `payload.slo_name`

### 3) bulk 부분 실패 확인

```bash
curl -sS -X POST "$BASE_URL/governance/ops-events/ingest/bulk" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "spec": {
        "name": "slo_breached",
        "severity": "high",
        "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
        "feeds_back_to": "needs"
      },
      "payload": {
        "trace_id": "trace-smoke-bulk-001",
        "lineage_id": "lineage-smoke-bulk-001",
        "service_id": "payments-api",
        "slo_name": "latency_p95"
      }
    },
    {
      "spec": {
        "name": "slo_breached",
        "severity": "high",
        "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
        "feeds_back_to": "needs"
      },
      "payload": {
        "trace_id": "trace-smoke-bulk-001",
        "lineage_id": "lineage-smoke-bulk-001",
        "service_id": "payments-api"
      }
    }
  ]'
```

검증:

- HTTP `200`
- `strategy == "partial"`
- `success_count == 1`, `failed_count == 1`
- 실패 항목의 `issues[].field`에 `items[1].payload.slo_name`

### 4) list/get 확인

```bash
curl -sS "$BASE_URL/governance/ops-events?trace_id=trace-smoke-001&limit=10&offset=0"
```

검증:

- HTTP `200`
- `items[0].id`를 추출해 아래 조회 수행

```bash
EVENT_ID="service_ops_event:..."  # list 결과의 실제 id 사용
curl -sS "$BASE_URL/governance/ops-events/$EVENT_ID"
```

검증:

- HTTP `200`
- `id == EVENT_ID`

### 5) lineage replay 확인

```bash
curl -sS "$BASE_URL/governance/lineage-replay/decision-ok-001"
curl -sS "$BASE_URL/governance/lineage-replay/decision-broken-001"
```

검증:

- 정상 케이스: `status == "ok"`
- 단절 케이스: HTTP `200` + `status == "warning"` + `warnings[]`

