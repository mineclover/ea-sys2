# M2 v2 코어 패키지 매핑 (구현 기준)

## 1. 목적
- M2 v2 계약이 실제로 어느 패키지/모듈에 구현되어 있는지 기준 경로를 고정한다.
- 설계 문서와 운영 런북이 구현 경로를 동일하게 참조하도록 drift를 방지한다.

## 2. 패키지 매핑 표 (2026-02-21)
| 패키지명 | 상태 | 역할 | 구현 근거(핵심 모듈) |
| --- | --- | --- | --- |
| `ea-profile` | 구현됨 | v2 canonical spec, 정적 validator, serializer, legacy adapter | `packages/ea-profile/src/ea_profile/v2/types.py`, `packages/ea-profile/src/ea_profile/v2/validator.py`, `packages/ea-profile/src/ea_profile/v2/serializer.py`, `packages/ea-profile/src/ea_profile/v2/adapters.py`, `packages/ea-profile/src/ea_profile/v2/state_tokens.py` |
| `ea-governance` | 구현됨 | runtime hook/status, ops-event ingest/list/get, lineage replay(warn/block) | `packages/ea-governance/src/ea_governance/api_router.py`, `packages/ea-governance/src/ea_governance/needs_ops.py`, `packages/ea-governance/src/ea_governance/catalog_policy_store.py` |
| `ea-infra` | 구현됨 | infra asset catalog 저장소 + ops-event retention store | `packages/ea-infra/src/ea_infra/asset_catalog.py`, `packages/ea-infra/src/ea_infra/ops_ingestion.py` |
| `ea-ops` | 구현됨 | service ops event vocabulary/spec validation | `packages/ea-ops/src/ea_ops/events.py` |
| `ea-trace` | 구현됨 | lineage/evidence 공통 유틸 | `packages/ea-trace/src/ea_trace/chain.py`, `packages/ea-trace/src/ea_trace/evidence.py` |
| `ea-kernel` | 연동됨 | governance router 포함 및 운영 서버 엔트리포인트 | `packages/ea-kernel/src/ea_kernel/api/server.py` |
| `ea-flow`, `ea-projection`, `ea-decision`, `ea-needs`, `sdlc-domain` | 확장 예정/부분 연동 | v2 계약 소비 계층(도메인별 적용) | 각 패키지 내부 기존 모듈에서 계약 소비, 전용 `v2/` 모듈은 현재 범위 밖 |

## 3. 실제 모듈 경로

### 3.1 Canonical spec + validator
- `packages/ea-profile/src/ea_profile/v2/types.py`
- `packages/ea-profile/src/ea_profile/v2/validator.py`
- `packages/ea-profile/src/ea_profile/v2/state_tokens.py`
- `packages/ea-profile/src/ea_profile/v2/__init__.py`

### 3.2 Serialization + migration shim
- `packages/ea-profile/src/ea_profile/v2/serializer.py`
- `packages/ea-profile/src/ea_profile/v2/adapters.py`
- `packages/ea-profile/docs/v2-cutover-guide.md`

### 3.3 Runtime hook + replay + ops API
- `packages/ea-governance/src/ea_governance/api_router.py`
- `packages/ea-governance/docs/ops-events-api-runbook.md`
- `packages/ea-governance/docs/ops-lineage-replay-api.md`

### 3.4 Infra/ops/trace supporting contracts
- `packages/ea-infra/src/ea_infra/asset_catalog.py`
- `packages/ea-infra/src/ea_infra/ops_ingestion.py`
- `packages/ea-ops/src/ea_ops/events.py`
- `packages/ea-trace/src/ea_trace/chain.py`
- `packages/ea-trace/src/ea_trace/evidence.py`

### 3.5 Contract regression tests
- `packages/ea-profile/tests/test_v2_types.py`
- `packages/ea-governance/tests/test_api_router.py`
- `packages/ea-infra/tests/test_asset_catalog.py`

## 4. 관련 문서
- `docs/m2-v2-draft.md`
- `packages/ea-governance/docs/ops-events-api-runbook.md`
- `packages/ea-profile/docs/v2-cutover-guide.md`
