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
| FlowEdgeSpec | `id`, `from`, `to`, `kind`, `required` |
| StateTokenSpec | `id`, `layer`, `canonical`, `aliases[]` |
| TransitionSpec | `id`, `layer`, `from`, `to`, `requires_trace`, `requires_governance_event` |
| ArtifactTypeSpec | `id`, `tier`, `source_layers[]`, `kernel_element_pattern` |
| TraceLinkSpec | `id`, `source_type`, `target_type`, `relation`, `required` |
| GovernanceEventSpec | `name`, `must_include[]`, `retention_policy` |
| LoopContractSpec | `id`, `path[]`, `enforce_trace`, `enforce_event_chain` |
| InfraAssetSpec | `id`, `asset_type`, `owner`, `environment`, `criticality`, `exposure_refs[]` |
| ServiceOpsEventSpec | `name`, `severity`, `must_include[]`, `feeds_back_to` |
| EvidenceBindingSpec | `id`, `source_type`, `binds_to`, `required_fields[]` |

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
id = "decision.PROPOSED"
layer = "decision"
canonical = "PROPOSED"
aliases = ["DecisionStatusProposed"]

[[state_tokens]]
id = "decision.ACCEPTED"
layer = "decision"
canonical = "ACCEPTED"
aliases = ["DecisionStatusAccepted"]

[[transitions]]
id = "decision.proposed_to_accepted"
layer = "decision"
from = "decision.PROPOSED"
to = "decision.ACCEPTED"
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
name = "projection.exposed"
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

## 6. Validator 설계 체크리스트 (v2)

### 6.1 정적 검증 (load/compile 시점)
1. `profile.id`, `namespace`, `domain` 존재 및 형식 검사.
2. `layers.id` 유일성, `order` 유일성, `role` enum 검사.
3. `flow_edges` 참조 무결성(`from/to`가 존재 레이어인지).
4. `flow_edges`의 필수 경로 존재 검사:
   - `infra -> kernel`
   - `infra -> flow`
   - `decision -> needs`
   - `needs -> kernel`
   - `kernel -> flow`
   - `flow -> projection`
   - `projection -> decision`
5. `state_tokens.id` 유일성 + `layer` 존재 검사.
6. `transitions.from/to`가 같은 layer의 `state_tokens.id`를 참조하는지 검사.
7. `artifact_types.id` 유일성 + tier enum 검사.
8. `trace_links` 필수 relation 집합 충족 검사.
9. `governance_events.name` 유일성 + `must_include` 최소 키 검사.
10. `infra_assets.id` 유일성 + `owner/environment/criticality` 필수값 검사.
11. `service_ops_events.name` 유일성 + `severity` enum + `feeds_back_to` 레이어 참조 검사.
12. `evidence_bindings.id` 유일성 + `source_type/binds_to/required_fields` 완결성 검사.
13. `loop_contracts.path`가 실제 flow graph에서 닫힌 경로인지 검사.

### 6.2 런타임 검증 (store/execution 시점)
1. 상태 전이 시 `requires_trace=true`면 trace link 존재 강제.
2. 상태 전이/구조 변경/표층 노출 시 지정된 governance event 발행 강제.
3. `kernel_change -> flow_execution -> projection.exposed` 체인 누락 감지.
4. Projection 산출 artifact가 선언된 `artifact_types` 외 값이면 실패(`api/tool/page/url/file/identifier` 포함).
5. 운영 이벤트(`incident_opened`, `slo_breached`, `deployment_rolled_back`) 발생 시 `feeds_back_to` 레이어로 피드백 체인 생성 강제.
6. `kernel_change`, `flow_execution`, `surface_artifact`에 대해 대응 `evidence_bindings` 증거 누락 시 경고 또는 차단.
7. lineage 단위 causal chain 단절 시 경고 또는 차단.

## 7. M1과 M2 책임 경계
- M2가 책임지는 것:
  - 구조 정의, 관계 의미, 검증 계약, 추적 계약.
- M1(runtime)이 책임지는 것:
  - 실제 실행, 저장소 최신 상태 조회, 트랜잭션, 합성 view 생성 최적화.
- 원칙:
  - "선언으로 검증 가능한 제약"은 M2로 승격.
  - "실행 시점 정보가 필요한 제약"은 M1 훅으로 유지.

## 8. v2 도입 우선순위
1. **P0**: `StateTokenSpec`, `FlowEdgeSpec`, `LoopContractSpec` 도입.
2. **P0**: `InfraAssetSpec` + `ServiceOpsEventSpec` + `EvidenceBindingSpec` 도입.
3. **P0**: Governance 이벤트 강제 계약(`governance_events`) 도입.
4. **P1**: Projection source/registry discovery 선언형 전환.
5. **P1**: Namespace-aware loader/composer 1급 지원.
6. **P2**: 경로 제약 DSL(예: Service는 Repository 경유 필수) 추가.

## 9. v2 완료 기준 (Definition of Done)
- v2 스키마로 작성된 프로파일이 정적 validator를 통과한다.
- `projection -> decision -> needs -> kernel -> flow -> projection` 루프가 trace/event 체인으로 재생 가능하다.
- 거버넌스 이벤트만으로 의사결정 근거와 구조 변경 이유를 역추적할 수 있다.
- 인프라 자산(`infra_assets`)이 owner/environment/criticality 기준으로 카탈로그화되어 Projection에서 참조 가능하다.
- 서비스 운영 이벤트(`service_ops_events`)가 Decision/Needs/Kernel 피드백 루프로 연결된다.
- 구현 증거(`evidence_bindings`: code_commit/ci_run/deployment_record)가 trace chain에 연결되어 감사 재생이 가능하다.
- 새 도메인 추가 시 코드 하드코딩 없이 profile 등록/검증/표층 노출이 가능하다.

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

## 12. 구현 현황 (2026-02-21 기준)

### 12.1 `tasks/prd.json` (US-001~US-009) 구현 평가
| User Story | 상태 | 구현 근거 |
| --- | --- | --- |
| `US-001` SQLite Ops Event Store | 완료 | `packages/ea-infra/src/ea_infra/ops_ingestion.py`에 `SQLiteOpsEventStore`/`InMemoryOpsEventStore`(`append/read/count`) 구현, `packages/ea-infra/tests/test_ops_ingestion.py` 저장/조회/호환 테스트 |
| `US-002` Retention/Cleanup | 완료 | `OpsEventRetentionPolicy`, `cleanup_preview`, `cleanup` 구현 및 age/record 기준 테스트 (`packages/ea-infra/tests/test_ops_ingestion.py`) |
| `US-003` 단건 Ingestion API | 완료 | `POST /governance/ops-events/ingest` + 구조화 검증 오류 계약 (`packages/ea-governance/src/ea_governance/api_router.py`, `packages/ea-governance/tests/test_api_router.py`) |
| `US-004` 대량 Ingestion API | 완료 | `POST /governance/ops-events/ingest/bulk`, `strategy=partial`, 항목별 성공/실패, trace/lineage 상관관계 검증 (`packages/ea-governance/src/ea_governance/api_router.py`) |
| `US-005` Ops Event 조회 API | 완료 | list/get 엔드포인트 + `trace_id/lineage_id/event_name/time-range` 필터 + `limit/offset` (`packages/ea-governance/src/ea_governance/api_router.py`) |
| `US-006` Lineage Replay API | 완료 | `GET /governance/lineage-replay/{decision_id}` + `replayed_nodes`, `path_to_latest_operation`, `missing_required_relations`, warning 계약 (`packages/ea-governance/src/ea_governance/api_router.py`) |
| `US-007` Catalog Auto-Express 정책 테이블 | 완료 | 정책 모델/평가기/SQLite 저장소(`packages/ea-governance/src/ea_governance/catalog_policy_store.py`) + ingestion 경로 연동(`packages/ea-governance/src/ea_governance/needs_ops.py`) |
| `US-008` Needs 자동 반영 | 완료 | 정책 통과 시 `expressed_need` 생성, 트랜잭션 이벤트 기록, infra/needs snapshot 동시 생성 (`packages/ea-governance/src/ea_governance/needs_ops.py`, `packages/ea-governance/tests/test_needs_store.py`) |
| `US-009` API 명세/Runbook | 완료 | 명세+운영 절차 문서(`packages/ea-governance/docs/ops-events-api-runbook.md`, `packages/ea-governance/docs/ops-lineage-replay-api.md`) 및 참조(`packages/ea-governance/README.md`) |

검증 실행 결과(2026-02-21):
- `uv run pytest packages/ea-infra/tests/test_ops_ingestion.py packages/ea-governance/tests/test_catalog_policy_store.py packages/ea-governance/tests/test_needs_store.py packages/ea-governance/tests/test_api_router.py` → **41 passed**
- `ruff check`는 저장소 전체 기준 기존 누적 이슈가 있으나, US-001~US-009 관련 변경 파일 스코프(`ea-ops/events.py`, `ea-infra/ops_ingestion.py`, `ea-governance/api_router.py`, `ea-governance/catalog_policy_store.py`, `ea-governance/needs_ops.py`, 관련 테스트)는 **All checks passed**

### 12.2 M2 v2 핵심 엔티티별 도입 상태
| 엔티티 | 상태 | 현재 구현 메모 |
| --- | --- | --- |
| `ProfileSpec` | 부분 구현 | `KernelProfile`에 `name/version/kernel_version` 중심 구조 존재(`packages/ea-profile/src/ea_profile/types.py`), `namespace/domain`은 1급 필드로 미정착 |
| `LayerSpec` | 부분 구현 | `LayerDefinition`(`name/order/responsibility`) 존재하나 `role` 강제 계약은 미완료 (`packages/ea-profile/src/ea_profile/types.py`) |
| `FlowEdgeSpec` | 미구현 | `LayerStack`가 아직 문자열 flow 필드(`definition_flow/runtime_flow/feedback_flow`) 기반 |
| `StateTokenSpec` | 부분 구현 | 프로파일 validator에서 상태 토큰 해석/검증은 있으나 독립 spec 엔티티는 미도입 (`packages/ea-profile/src/ea_profile/profile_validator.py`) |
| `TransitionSpec` | 부분 구현 | `ProfileStateTransition` 존재하나 `requires_trace/requires_governance_event` 계약은 미도입 |
| `ArtifactTypeSpec` | 부분 구현 | `ProfileArtifactType` + 패턴 검증 존재 (`packages/ea-profile/src/ea_profile/types.py`, `packages/ea-profile/src/ea_profile/profile_validator.py`) |
| `TraceLinkSpec` | 부분 구현 | trace link 직렬화/재생 로직은 존재하나 공용 스키마 계약화는 미완료 (`packages/ea-governance/src/ea_governance/decision_trace_ops.py`) |
| `GovernanceEventSpec` | 미구현 | 트랜잭션 이벤트는 존재하나 `name/must_include/retention_policy` 기반 typed spec 부재 |
| `LoopContractSpec` | 미구현 | 폐루프 경로(`projection -> decision -> ...`)에 대한 독립 계약/validator 부재 |
| `InfraAssetSpec` | 미구현 | `infra_assets` 카탈로그 모델 및 owner/env/criticality 인덱스 미도입 |
| `ServiceOpsEventSpec` | 구현 완료 | `packages/ea-ops/src/ea_ops/events.py` + `ea-governance` ingestion/list/replay API에서 실사용 |
| `EvidenceBindingSpec` | 구현 완료 | `packages/ea-trace/src/ea_trace/evidence.py`에 spec/validator/payload 검증 구현 |

### 12.3 요약
- PRD 기준 `US-001`~`US-009` 범위 구현은 코드/테스트/문서 기준으로 완료 상태다.
- 다만 `m2-v2` 전체 관점의 P0 잔여 항목(`FlowEdgeSpec`, `LoopContractSpec`, `GovernanceEventSpec`, `InfraAssetSpec`)은 별도 후속 작업이 필요하다.
