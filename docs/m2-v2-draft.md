# M2 v2 구조 설계 초안

## 0. 문서 목적
- 본 문서는 `docs/layer-freedom-analysis.md`, `docs/m2-expressiveness-report.md`에서 드러난 한계를 바탕으로,  
  다음 구조를 안정적으로 수행하기 위한 **M2 v2 최소 메타모델**을 제안한다.
- 기본 용어 정의는 `docs/system-terminology.md`, 기본 구조 설명은 `docs/system-foundation.md`를 기준으로 한다.
- 목적 기반 검증 항목은 `docs/system-usecases.md`를 기준으로 한다.
- 목표 구조:
  - `Infra`: 실행/저장/전송/관측을 위한 기반 substrate
  - "구현은 외부 영역"이라는 가정 아래, 시스템이 의존하는 기반 계약을 선언적으로 유지
  - `Decision -> Needs`: 기록과 인과 추적 중심
  - `Kernel -> Flow`: 구조/데이터의 구조화된 기억 중심
  - `Projection`: 구현 결과의 표층 노출(`api`, `tool`, `page`, `url`, `file`, `identifier` 등)
  - `Governance`: 전체 시스템 기록/감사/추적의 원장 계층

## 1. 문제 재정의 (v1 한계 요약)
- Flow가 문자열(`definition_flow/runtime_flow/feedback_flow`)이라 의미 검증이 약함.
- 상태 토큰의 canonical 정의가 없어 alias 보정 코드 의존이 큼.
- Projection 소스/아티팩트 탐색이 일부 코드 하드코딩에 묶여 확장성이 낮음.
- 멀티 도메인 공존 시 namespace/composition이 도구 레벨에서 1급 개념이 아님.
- Governance가 "중앙 추적 원장"으로 선언되지 않아 운영 규율이 문서/관례에 머무름.

## 2. M2 v2 설계 목표
- **G1. 의미 강제력 강화**: 레이어 역할과 흐름을 typed contract로 선언.
- **G2. 추적 일관성**: 모든 핵심 전이를 trace/governance 이벤트와 결합.
- **G3. 표층 폐루프 보장**: Projection 관측이 Decision으로 되돌아오는 반복 구조를 계약화.
- **G4. 도메인 확장성**: profile discovery, namespace, compose를 선언형으로 지원.
- **G5. 최소성 유지**: M1 런타임 책임은 남기되, M2에서 검증 가능한 부분은 최대한 승격.

## 3. 레이어 의미 모델 (v2)
| Layer | 핵심 역할 | 주 책임 | 필수 출력 |
| --- | --- | --- | --- |
| Infra | Runtime Substrate | 저장/전송/실행/관측의 기반 계약 제공 | `infra_contract`, `storage_binding`, `runtime_capability` |
| Governance | System Ledger | 전 계층 이벤트/감사/추적 | `governance_event`, `audit_trail` |
| Decision | Causal Memory | 관측 기반 판단, 선택, 근거 기록 | `decision_record`, `decision_state` |
| Needs | Causal Refinement | 필요성 정제, 우선순위/정합성 | `need_record`, `need_state` |
| Kernel | Business Skeleton | 비즈니스 로직의 뼈대, 불변 규칙, 경계 정의 | `domain_skeleton`, `kernel_change`, `rule_asset` |
| Flow | Data Modeling Memory | 데이터 모델/변환/전달 경로의 실행 모델 정의 | `data_model`, `flow_execution`, `flow_state` |
| Projection | Surface Memory | 최종 경험 산출물(API/Tools/Page/URL/File) 관리 및 노출 | `surface_artifact`, `surface_summary` |

### 3.1 구조 설명 (목적 중심)
- `Infra`는 시스템이 실제로 동작하기 위한 기반 계약 계층이다. 데이터 저장소, 큐/버스, 실행 런타임, 모니터링 채널 같은 실행 환경 제약을 선언한다.
- `Decision`과 `Needs`는 "왜 이것을 해야 하는가"를 기록하는 인과 메모리 계층이다.  
  Projection에서 관측한 표층 신호를 근거로 판단하고, 이를 필요한 구조 변경 요구로 정제한다.
- `Kernel`은 비즈니스 로직의 뼈대를 그리는 계층이다. 핵심 개념, 관계, 금지/허용 규칙을 정의한다.
- `Flow`는 Kernel 뼈대를 실제 데이터 처리 관점으로 펼치는 계층이다. 데이터 모델, 상태 전개, 실행 순서를 구조화한다.
- `Projection`은 사용자/운영자가 인지 가능한 최종 산출물 계층이다. API, Tool, Page, URL, File을 식별 가능한 artifact로 관리한다.
- `Governance`는 위 모든 과정을 사건(event) 단위로 기록하고, 추적 가능성을 유지하는 원장 계층이다.

## 4. M2 v2 최소 메타모델

### 4.1 필수 엔티티
1. `ProfileSpec`
2. `LayerSpec`
3. `FlowEdgeSpec`
4. `StateTokenSpec`
5. `TransitionSpec`
6. `ArtifactTypeSpec`
7. `TraceLinkSpec`
8. `GovernanceEventSpec`
9. `LoopContractSpec`
10. `InfraAssetSpec`
11. `ServiceOpsEventSpec`
12. `EvidenceBindingSpec`

### 4.2 각 엔티티 최소 필드
| Entity | 필수 필드 |
| --- | --- |
| ProfileSpec | `id`, `version`, `kernel_version`, `namespace`, `domain` |
| LayerSpec | `id`, `order`, `role`, `responsibility` |
| FlowEdgeSpec | `id`, `from_layer`, `to_layer`, `kind`, `required` (외부 직렬화 키: `from`, `to`) |
| StateTokenSpec | `id`, `layer`, `canonical`, `aliases[]` |
| TransitionSpec | `id`, `layer`, `from_state`, `to_state`, `requires_trace`, `requires_governance_event` (외부 직렬화 키: `from`, `to`) |
| ArtifactTypeSpec | `id`, `tier`, `source_layers[]`, `kernel_element_pattern` |
| TraceLinkSpec | `id`, `source_type`, `target_type`, `relation`, `required` |
| GovernanceEventSpec | `name`, `must_include[]`, `retention_policy` |
| LoopContractSpec | `id`, `path[]`, `enforce_trace`, `enforce_event_chain` |
| InfraAssetSpec | `id`, `asset_type`, `owner`, `environment`, `criticality`, `exposure_refs[]` |
| ServiceOpsEventSpec | `name`, `severity`, `must_include[]`, `feeds_back_to` |
| EvidenceBindingSpec | `id`, `source_type`, `binds_to`, `required_fields[]` |

### 4.3 엔티티 구현 모듈 매핑 (2026-02-21 기준)
| Entity | 구현 모듈 |
| --- | --- |
| `ProfileSpec` | `packages/ea-profile/src/ea_profile/v2/types.py` |
| `LayerSpec` | `packages/ea-profile/src/ea_profile/v2/types.py` |
| `FlowEdgeSpec` | `packages/ea-profile/src/ea_profile/v2/types.py`, `packages/ea-profile/src/ea_profile/v2/adapters.py` |
| `StateTokenSpec` | `packages/ea-profile/src/ea_profile/v2/types.py`, `packages/ea-profile/src/ea_profile/v2/state_tokens.py` |
| `TransitionSpec` | `packages/ea-profile/src/ea_profile/v2/types.py`, `packages/ea-profile/src/ea_profile/v2/state_tokens.py` |
| `ArtifactTypeSpec` | `packages/ea-profile/src/ea_profile/v2/types.py` |
| `TraceLinkSpec` | `packages/ea-profile/src/ea_profile/v2/types.py` |
| `GovernanceEventSpec` | `packages/ea-profile/src/ea_profile/v2/types.py` |
| `LoopContractSpec` | `packages/ea-profile/src/ea_profile/v2/types.py`, `packages/ea-profile/src/ea_profile/v2/validator.py` |
| `InfraAssetSpec` | `packages/ea-profile/src/ea_profile/v2/types.py`, `packages/ea-infra/src/ea_infra/asset_catalog.py` |
| `ServiceOpsEventSpec` | `packages/ea-profile/src/ea_profile/v2/types.py`, `packages/ea-ops/src/ea_ops/events.py`, `packages/ea-governance/src/ea_governance/api_router.py` |
| `EvidenceBindingSpec` | `packages/ea-profile/src/ea_profile/v2/types.py`, `packages/ea-trace/src/ea_trace/evidence.py`, `packages/ea-governance/src/ea_governance/api_router.py` |

## 5. 최소 TOML 스키마 (초안)
```toml
[profile]
id = "ea-m2-v2"
version = "2.0.0-draft"
kernel_version = "2.5.0"
namespace = "ea_sys"
domain = "governance_core"

[[layers]]
id = "infra"
order = 0
role = "runtime_substrate"
responsibility = "Storage, transport, execution, and observability substrate contracts"

[[layers]]
id = "governance"
order = 10
role = "system_ledger"
responsibility = "Cross-layer trace, audit, and policy enforcement"

[[layers]]
id = "decision"
order = 20
role = "causal_memory"
responsibility = "Observation-based decision and rationale capture"

[[layers]]
id = "needs"
order = 30
role = "causal_memory"
responsibility = "Need refinement and priority normalization"

[[layers]]
id = "kernel"
order = 40
role = "business_skeleton"
responsibility = "Domain model structure and rule integrity"

[[layers]]
id = "flow"
order = 50
role = "data_modeling_memory"
responsibility = "Execution sequence and dataflow progression"

[[layers]]
id = "projection"
order = 60
role = "surface_memory"
responsibility = "Manage and expose final artifacts: api/tool/page/url/file/identifier"

[[flow_edges]]
id = "infra_to_kernel"
from = "infra"
to = "kernel"
kind = "substrate_constraint"
required = true

[[flow_edges]]
id = "infra_to_flow"
from = "infra"
to = "flow"
kind = "runtime_capability_binding"
required = true

[[flow_edges]]
id = "decision_to_needs"
from = "decision"
to = "needs"
kind = "causal_handoff"
required = true

[[flow_edges]]
id = "needs_to_kernel"
from = "needs"
to = "kernel"
kind = "structure_request"
required = true

[[flow_edges]]
id = "kernel_to_flow"
from = "kernel"
to = "flow"
kind = "execution_spec"
required = true

[[flow_edges]]
id = "flow_to_projection"
from = "flow"
to = "projection"
kind = "surface_exposure"
required = true

[[flow_edges]]
id = "projection_to_decision"
from = "projection"
to = "decision"
kind = "feedback_observation"
required = true

[[state_tokens]]
id = "decision.proposed"
layer = "decision"
canonical = "PROPOSED"
aliases = ["DecisionStatusProposed"]

[[state_tokens]]
id = "decision.accepted"
layer = "decision"
canonical = "ACCEPTED"
aliases = ["DecisionStatusAccepted"]

[[transitions]]
id = "decision.proposed_to_accepted"
layer = "decision"
from = "decision.proposed"
to = "decision.accepted"
requires_trace = true
requires_governance_event = "decision.transitioned"

[[artifact_types]]
id = "api_endpoint"
tier = "function"
source_layers = ["flow", "projection"]
kernel_element_pattern = "@ActiveStructure"

[[artifact_types]]
id = "page"
tier = "ui"
source_layers = ["projection"]
kernel_element_pattern = "@Page"

[[artifact_types]]
id = "tool"
tier = "function"
source_layers = ["projection"]
kernel_element_pattern = "@Context"

[[artifact_types]]
id = "identifier"
tier = "evidence"
source_layers = ["projection"]
kernel_element_pattern = "@PassiveStructure"

[[artifact_types]]
id = "url"
tier = "ui"
source_layers = ["projection"]
kernel_element_pattern = "@Page"

[[artifact_types]]
id = "file"
tier = "data"
source_layers = ["projection", "flow"]
kernel_element_pattern = "@PassiveStructure"

[[infra_assets]]
id = "payments-db-prod"
asset_type = "database"
owner = "platform-data"
environment = "prod"
criticality = "tier0"
exposure_refs = ["url:jdbc:payments-db-prod", "file:infra/terraform/payments-db.tf"]

[[infra_assets]]
id = "orders-api-gateway-prod"
asset_type = "api_gateway"
owner = "platform-network"
environment = "prod"
criticality = "tier1"
exposure_refs = ["url:https://api.company.com/orders", "file:infra/k8s/orders-gateway.yaml"]

[[trace_links]]
id = "decision_informed_by_projection"
source_type = "decision_record"
target_type = "surface_artifact"
relation = "informed_by"
required = true

[[trace_links]]
id = "need_derived_from_decision"
source_type = "need_record"
target_type = "decision_record"
relation = "derived_from"
required = true

[[trace_links]]
id = "kernel_change_satisfies_need"
source_type = "kernel_change"
target_type = "need_record"
relation = "satisfies"
required = true

[[trace_links]]
id = "flow_execution_implements_kernel_change"
source_type = "flow_execution"
target_type = "kernel_change"
relation = "implements"
required = true

[[governance_events]]
name = "decision.transitioned"
must_include = ["trace_id", "lineage_id", "actor", "reason", "evidence_refs"]
retention_policy = "immutable"

[[governance_events]]
name = "kernel.changed"
must_include = ["trace_id", "lineage_id", "actor", "diff_ref", "approved_by"]
retention_policy = "immutable"

[[governance_events]]
name = "projection.artifact_exposed"
must_include = ["trace_id", "lineage_id", "artifact_type", "artifact_id"]
retention_policy = "immutable"

[[service_ops_events]]
name = "incident_opened"
severity = "high"
must_include = ["trace_id", "lineage_id", "service_id", "incident_id", "runbook_url"]
feeds_back_to = "decision"

[[service_ops_events]]
name = "slo_breached"
severity = "medium"
must_include = ["trace_id", "lineage_id", "service_id", "slo_name", "current_value", "target_value"]
feeds_back_to = "needs"

[[service_ops_events]]
name = "deployment_rolled_back"
severity = "high"
must_include = ["trace_id", "lineage_id", "service_id", "deployment_id", "rollback_reason"]
feeds_back_to = "kernel"

[[evidence_bindings]]
id = "kernel_change_to_code_commit"
source_type = "kernel_change"
binds_to = "code_commit"
required_fields = ["repo", "commit_sha", "pr_url"]

[[evidence_bindings]]
id = "flow_execution_to_ci_run"
source_type = "flow_execution"
binds_to = "ci_run"
required_fields = ["pipeline", "run_id", "status", "build_url"]

[[evidence_bindings]]
id = "projection_artifact_to_deployment"
source_type = "surface_artifact"
binds_to = "deployment_record"
required_fields = ["service_id", "deployment_id", "environment", "dashboard_url"]

[[loop_contracts]]
id = "continuous_refinement"
path = ["projection", "decision", "needs", "kernel", "flow", "projection"]
enforce_trace = true
enforce_event_chain = true
```

## 6. Validator 및 운영 검증 기준 (구현 기준)

### 6.1 정적 검증 (`ea_profile.v2` load 시점)
1. `ProfileSpec`, `LayerSpec`, `FlowEdgeSpec`, `StateTokenSpec`, `TransitionSpec`, `ArtifactTypeSpec`, `TraceLinkSpec`, `GovernanceEventSpec`, `LoopContractSpec`, `InfraAssetSpec`, `ServiceOpsEventSpec`, `EvidenceBindingSpec`는 각 dataclass `__post_init__`에서 형식/enum/필수 필드 검증을 수행한다.
2. `TypeSystemSpec.__post_init__`는 각 엔티티 ID/이벤트명 유일성 검사 후, 아래 aggregate 검증을 실행한다.
3. `packages/ea-profile/src/ea_profile/v2/validator.py`:
   - flow edge의 레이어 참조 무결성
   - canonical 필수 경로(`infra->kernel`, `infra->flow`, `decision->needs`, `needs->kernel`, `kernel->flow`, `flow->projection`, `projection->decision`)
   - loop path의 레이어 유효성 및 hop 연결성
   - canonical loop 레이어 집합이 모두 선언된 경우에만 mandatory path를 강제
4. `state_tokens`/`transitions`:
   - layer별 alias index(`id`, `canonical`, `aliases`)를 구성
   - `TransitionSpec.from_state/to_state`가 같은 layer state token으로 해석 가능한지 검사
5. `trace_links`/`evidence_bindings`:
   - `EvidenceBindingSpec.source_type`가 trace endpoint type 집합에 포함되는지 검사
   - `surface_artifact` source의 `required_fields`에 `environment` 포함 강제
6. 교차 제약:
   - `InfraAssetSpec.asset_type == api_gateway`이면 `exposure_refs`에 `url:` 또는 `api:` 필요
   - `ServiceOpsEventSpec.severity == critical`이면 `must_include`에 `runbook_url` 또는 `incident_id` 필요

### 6.2 정적 validator 이슈 코드 계약
`TypeSystemValidationError.issues[*]`는 아래 코드 집합을 사용한다.

| code | 의미 |
| --- | --- |
| `FLOW_EDGE_UNKNOWN_LAYER` | flow edge가 존재하지 않는 source/target layer를 참조 |
| `FLOW_REQUIRED_PATH_MISSING` | canonical required flow path 누락 |
| `LOOP_PATH_INVALID_LAYER` | loop path에 미정의 layer 포함 |
| `LOOP_PATH_DISCONNECTED` | loop path 인접 hop이 flow graph에서 연결되지 않음 |

### 6.3 런타임 훅 검증 (`ea-governance` API)
1. `GET /governance/v2-spec/status`
   - 12개 엔티티별 `loaded`, `validated`, `errors` 매트릭스 제공
   - `entities` query filter(`-`/`_` 정규화, 중복 제거) 지원
   - 잘못된 필터는 `422 v2_spec_validation_error` 반환
2. `POST /governance/ops-events/ingest`, `POST /governance/ops-events/ingest/bulk`
   - `ServiceOpsEventSpec`/payload 계약 위반을 구조화된 `issues[]`로 반환
3. `GET /governance/lineage-replay/{decision_id}`
   - `evidence_mode=warn|block` 계약 지원
   - `warn`: `200 status=warning` + `lineage_missing_required_evidence`
   - `block`: `409 lineage_replay_evidence_blocked` + `missing_evidence_operations`
   - path 단절은 `200 status=warning`으로 유지(`lineage_path_disconnected`)

### 6.4 운영 점검 루틴 기준 문서
- canonical runbook: `packages/ea-governance/docs/ops-events-api-runbook.md`
- 포함 루틴:
  - 정적 validator 실행 루틴 (`TypeSystemSpec`/`TypeSystemValidationError`)
  - runtime hook 점검 루틴 (`/governance/v2-spec/status`)
  - replay warn/block 점검 루틴 (`/governance/lineage-replay`)

## 7. M1과 M2 책임 경계
- M2가 책임지는 것:
  - 구조 정의, 관계 의미, 검증 계약, 추적 계약.
- M1(runtime)이 책임지는 것:
  - 실제 실행, 저장소 최신 상태 조회, 트랜잭션, 합성 view 생성 최적화.
- 원칙:
  - "선언으로 검증 가능한 제약"은 M2로 승격.
  - "실행 시점 정보가 필요한 제약"은 M1 훅으로 유지.

## 8. v2 도입 우선순위 (업데이트)
1. **완료**: `StateTokenSpec`, `FlowEdgeSpec`, `LoopContractSpec` 도입 및 정적 validator 통합.
2. **완료**: `InfraAssetSpec`, `ServiceOpsEventSpec`, `EvidenceBindingSpec` 도입 및 교차 제약 반영.
3. **완료**: runtime readiness hook(`GET /governance/v2-spec/status`) 및 lineage replay evidence mode(`warn|block`) 도입.
4. **진행 중**: 도메인별 profile discovery/composer의 namespace-aware 확장 고도화.
5. **후속**: 전 계층 governance event 강제/감사 정책을 단일 실행 경로로 통합.

## 9. v2 완료 기준 (Definition of Done)
1. `TypeSystemSpec` 기준 12개 엔티티 계약이 코드/테스트에서 모두 생성 가능해야 한다.
2. 정적 validator가 canonical flow/loop 위반을 코드화된 이슈(`FLOW_*`, `LOOP_*`)로 반환해야 한다.
3. transition/state-token alias 참조 무결성과 trace/evidence source-type 무결성이 aggregate load에서 강제되어야 한다.
4. runtime hook(`GET /governance/v2-spec/status`)이 엔티티별 `loaded/validated/errors`를 안정적으로 반환해야 한다.
5. lineage replay가 `evidence_mode=warn|block` 계약을 지키고, warning/blocked 응답을 구조화된 형태로 제공해야 한다.
6. 운영 runbook에 정적 validator + runtime hook + replay 점검 절차와 수동 smoke 절차가 재현 가능하게 문서화되어야 한다.

## 10. Enum 및 필드 제약 표준 (v2 baseline)

### 10.1 Enum 표준값
| 필드 | 허용값 |
| --- | --- |
| `layers.role` | `runtime_substrate`, `system_ledger`, `causal_memory`, `business_skeleton`, `data_modeling_memory`, `surface_memory` |
| `infra_assets.asset_type` | `compute_service`, `api_gateway`, `database`, `cache`, `queue`, `object_storage`, `network`, `observability`, `identity` |
| `infra_assets.environment` | `dev`, `staging`, `prod`, `sandbox`, `shared` |
| `infra_assets.criticality` | `tier0`, `tier1`, `tier2`, `tier3` |
| `service_ops_events.severity` | `low`, `medium`, `high`, `critical` |
| `service_ops_events.feeds_back_to` | `decision`, `needs`, `kernel` |
| `evidence_bindings.binds_to` | `code_commit`, `ci_run`, `deployment_record`, `dashboard_snapshot`, `incident_ticket`, `runbook_ref` |

### 10.2 필드 형식 제약
1. `id` 계열 필드(`infra_assets.id`, `evidence_bindings.id` 등):
   - regex: `^[a-z0-9][a-z0-9._-]{2,63}$`
2. `owner`:
   - 형식: team slug (`platform-data`, `commerce-core` 등)
3. `exposure_refs[]`:
   - 접두사 강제: `url:`, `file:`, `api:`, `dashboard:`
4. `must_include[]`:
   - 최소 `trace_id`, `lineage_id` 포함
5. `required_fields[]`:
   - 최소 3개 이상, 중복 불가

### 10.3 교차 제약 (Cross-field)
1. `infra_assets.asset_type=api_gateway`이면 `exposure_refs`에 최소 1개의 `url:` 또는 `api:`가 있어야 한다.
2. `service_ops_events.severity=critical`이면 `must_include`에 `runbook_url` 또는 `incident_id`가 반드시 포함되어야 한다.
3. `evidence_bindings.source_type=surface_artifact`이면 `required_fields`에 `environment`가 반드시 포함되어야 한다.

## 11. 패키지 매핑
- v2에서 변경/신규 코어 패키지 매핑은 `docs/m2-v2-package-map.md`를 기준으로 한다.

## 12. 구현 현황 (2026-02-21, US-011까지 반영)

### 12.1 핵심 결과 요약
- `ea_profile.v2` 네임스페이스에 12개 canonical 엔티티와 aggregate validator가 구현되었다.
- legacy profile을 v2로 이관하는 adapter/serializer/state-token normalization 경로가 구현되었다.
- `ea-governance` API에 runtime readiness hook(`GET /governance/v2-spec/status`)과 lineage replay evidence mode(`warn|block`)가 구현되었다.
- ops ingest/list/get/replay 운영 계약과 runbook이 `packages/ea-governance/docs/ops-events-api-runbook.md`에 통합되었다.

### 12.2 구현 근거(대표 모듈)
- `packages/ea-profile/src/ea_profile/v2/types.py`
- `packages/ea-profile/src/ea_profile/v2/validator.py`
- `packages/ea-profile/src/ea_profile/v2/state_tokens.py`
- `packages/ea-profile/src/ea_profile/v2/serializer.py`
- `packages/ea-profile/src/ea_profile/v2/adapters.py`
- `packages/ea-governance/src/ea_governance/api_router.py`
- `packages/ea-infra/src/ea_infra/asset_catalog.py`
- `packages/ea-ops/src/ea_ops/events.py`
- `packages/ea-trace/src/ea_trace/evidence.py`

### 12.3 대표 회귀 테스트
- `packages/ea-profile/tests/test_v2_types.py`
- `packages/ea-governance/tests/test_api_router.py`
- `packages/ea-infra/tests/test_asset_catalog.py`
