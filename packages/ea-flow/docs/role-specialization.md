# Flow Layer Role Specialization

> 정규 레이어 정의: `packages/ea-kernel/docs/system_spec_layers.md`
> Flow 프로파일: `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/50-flow.toml`

---

## 1. 레이어 정체성

Flow는 EA-Sys2 런타임 체인의 **종단 스테이지**(decision -> needs -> kernel -> **flow**)이자, 6x6 교차 레이어 계약 매트릭스(`FlowLayerContractMatrix`)의 **단일 소유자**다.

### 핵심 역할

- 실행/데이터 흐름 모델 정의 -- 단계 순서, 입출력 소비/생산, 트리거/전이
- `FlowLayerContractMatrix`를 통해 6개 레이어 간 모든 데이터 교환 계약을 소유하고 발행
- 상위 레이어(decision/needs/kernel)가 선언한 모델을 **실행 가능한 절차/데이터 전이**로 변환

### 3-Plane Execution Model

Flow는 선언-조율-실행을 수직으로 분리하는 3개 평면(Plane) 모델로 구조화된다.

| 평면 | 역할 | 핵심 타입 | 소스 |
|:-----|:-----|:---------|:-----|
| **P1 Specification** | 선언적 정의 -- "무엇을 실행할 것인가" | StepSpec, WorkflowSpec, SchemaSpec, FlowMetaStep, FlowTopology | `spec.py`, `schema.py` |
| **P2 Coordination** | 조율/그래프 -- "어떤 순서/조건으로" | ProcessSpec, DataFlowEdge, LogicCondition, DataTransformation | `topology.py` |
| **P3 Realization** | 명령적 실행 -- "실제로 어떻게 수행하는가" | FlowRuntime, StepImplementer, StepInterpretationResult | `runtime.py` |

설계 원칙: **Spec은 사실(fact), Implementer는 해석(interpretation)**. 동일 StepSpec에 환경별 다른 StepImplementer를 바인딩할 수 있다. P1/P2(선언)는 P3(실행)를 모른다 -- `spec.py`/`topology.py` -> `runtime.py` import 금지.

### 8단계 파이프라인

`50-flow.toml`에 정의된 Flow의 표준 실행 파이프라인:

```
ContextIngest -> Normalize -> BuildKernelInput -> MapKernelSpec
    -> ExecuteKernelAction -> VerifyOutcome -> PersistFlowState -> PublishFlowOutcome
```

| 단계 | TOML 요소명 | 카테고리 | 책임 |
|:-----|:-----------|:---------|:-----|
| 1. ContextIngest | `ContextIngestStep` | Behavior | 상위 decision/needs 컨텍스트 수집 |
| 2. Normalize | `NormalizeNeedStep` | Behavior | 요구/제약 정보 정규화 |
| 3. BuildKernelInput | `BuildKernelInputStep` | Behavior | 커널 입력 페이로드 구성 |
| 4. MapKernelSpec | `MapKernelSpecStep` | Behavior | 활성 커널 계약/버전에 매핑 |
| 5. ExecuteKernelAction | `ExecuteKernelAction` | Executable | 계약된 작업 실행 |
| 6. VerifyOutcome | `VerifyOutcomeStep` | Behavior | 실행 출력의 제약 검증 |
| 7. PersistFlowState | `PersistFlowStateStep` | Behavior | 상태/검증 흔적 영속화, 6x6 매트릭스 발행 |
| 8. PublishFlowOutcome | `PublishFlowOutcomeAction` | Executable | 최종 결과 스냅샷 발행 |

---

## 2. 메타-메타 모델 설계

### 2.1 FlowSchema 설계 대상

`50-flow.toml`에 선언된 요소들로부터 구축할 `FlowSchema` (frozen, SchemaPort-compatible)의 구성:

#### P1 Specification Plane

| 요소명 | 카테고리 | Python 대응 | 설명 |
|:------|:---------|:-----------|:-----|
| `SpecificationPlane` | Composite | -- | P1 평면 컨테이너 |
| `StepSpecContract` | Interface | `StepSpec` ABC | 추상 단계 명세 계약 (name, kernel_anchor, meta_type, input/output_schema) |
| `FlowMetaStepDefinition` | PassiveStructure | `FlowMetaStep` | 재사용 가능한 로직 패턴 정의 (frozen, name/description/input_schema/output_schema/kernel_type_requirement) |
| `KernelGroundedStepSpecType` | Behavior | `KernelGroundedStepSpec` | kernel_anchor로 커널 요소에 근거하는 StepSpec |
| `WorkflowSpecContract` | Interface | `WorkflowSpec` ABC | 추상 워크플로우 명세 계약 (name, kernel_anchor, input/output_schema, get_steps()) |
| `UseCaseSpecType` | Behavior | `UseCaseSpec` | 비즈니스 프로세스 정의 (description, primary_actor, success_criteria) |
| `ExecutionContextData` | PassiveStructure | `ExecutionContext` | 실행 컨텍스트 (execution_id, variables) |
| `StepResultSpecData` | PassiveStructure | `StepResultSpec` | 단계 결과 구조 명세 (output_schema, expected_log_patterns) |
| `FlowGenerationRuleData` | Assessment | `FlowGenerationRule` | 커널 엔티티 -> 플로우 스펙 생성 규칙 (source_kernel_type, target_flow_type, naming_pattern, required_steps, logic_conditions) |
| `FlowTopologyData` | PassiveStructure | `FlowTopology` | 선언적 프로세스 구조 (name, steps, entry/exit points, transition_rules, generation_rules) |

#### P2 Coordination Plane

| 요소명 | 카테고리 | Python 대응 | 설명 |
|:------|:---------|:-----------|:-----|
| `CoordinationPlane` | Composite | -- | P2 평면 컨테이너 |
| `ProcessSpecType` | ActiveStructure | `ProcessSpec` | 프로세스 루트 온톨로지 (id, name, version, steps, trigger_event, defined_schemas, data_flow_edges) |
| `StepDefinitionNode` | Behavior | `StepDefinition` | 프로세스 그래프 노드 (id, name, category, description, condition, transformation, schema_usage, routing) |
| `DataFlowEdgeLink` | PassiveStructure | `DataFlowEdge` | 단계 간 데이터 이동 (source_step.source_field -> target_step.target_field) |
| `LogicConditionExpr` | Assessment | `LogicCondition` | 조건식 (expression, engine: json-logic/python/sql, parameters) |
| `DataTransformationSpec` | Behavior | `DataTransformation` | 데이터 형태 변환 (input_schema -> output_schema, mapping_rules) |
| `SchemaDefinitionData` | PassiveStructure | `SchemaDefinition` | 데이터 형태 정의 (id, name, schema_format, definition) |
| `StepSchemaUsageSpec` | PassiveStructure | `StepSchemaUsage` | 단계 데이터 계약 (input/output_schema_id, required_fields) |
| `FlowOntologyRegistry` | ActiveStructure | `FlowOntology` | 프로세스 스펙 타입 레지스트리 (`describe()` 정적 메서드) |
| `FlowStepCategoryEnum` | Assessment | `FlowStepCategory` | 단계 역할 분류 (ACTION, DECISION, EVENT, GATEWAY, TRANSFORMATION) |

#### P3 Realization Plane

| 요소명 | 카테고리 | Python 대응 | 설명 |
|:------|:---------|:-----------|:-----|
| `RealizationPlane` | Composite | -- | P3 평면 컨테이너 |
| `FlowRuntimeEngine` | ActiveStructure | `FlowRuntime` | 순차 실행 + 보상 롤백 워크플로우 인터프리터 |
| `StepImplementerContract` | Interface | `StepImplementer` ABC | execute() + rollback() 보상 트랜잭션 패턴 |
| `StepInterpretationResultData` | PassiveStructure | `StepInterpretationResult` | 단계 해석 결과 (accepted, intent, logs) |
| `StepExecutionResultData` | PassiveStructure | `StepExecutionResult` | 후방 호환 별칭 (extends StepInterpretationResult) |
| `FlowExecutionResultData` | PassiveStructure | `FlowExecutionResult` | 전체 워크플로우 결과 (workflow_name, execution_id, success, step_results, logs, interpreted_intents, rollback_occurred) |

#### Schema Specs

| 요소명 | 카테고리 | Python 대응 | 설명 |
|:------|:---------|:-----------|:-----|
| `SchemaSpecContract` | Interface | `SchemaSpec` ABC | 스키마 명세 인터페이스 (format, validate(), to_dict()) |
| `JsonSchema2020SpecType` | ActiveStructure | `JsonSchema2020Spec` | JSON Schema 2020-12 검증 구현 |
| `DbSchemaSpecType` | ActiveStructure | `DbSchemaSpec` | DDL 방식 DB 스키마 (table_name, columns, ddl) |

#### Kernel Actions

| 요소명 | 카테고리 | Python 대응 | 설명 |
|:------|:---------|:-----------|:-----|
| `AddRuleStepSpecType` | Executable | `AddRuleStepSpec` | 규칙 추가 선언 스펙 (action_id, rule_asset_data, kernel_anchor) |
| `DeprecateRuleStepSpecType` | Executable | `DeprecateRuleStepSpec` | 규칙 폐기 선언 스펙 (rule_id, kernel_anchor) |
| `AddRuleImplementerType` | Executable | `AddRuleImplementer` | kernel.submit_rule 인텐트 생성 실행자 |
| `DeprecateRuleImplementerType` | Executable | `DeprecateRuleImplementer` | kernel.deprecate_rule 인텐트 생성 실행자 |

#### FlowProfile

| 요소명 | 카테고리 | Python 대응 | 설명 |
|:------|:---------|:-----------|:-----|
| `FlowProfileType` | Composite | `FlowProfile` | 도메인별 메타스텝 컬렉션 (name, version, meta_steps tuple, metadata) |

### 2.2 규칙 TOML 설계

`flow_rules.toml`로 외부화할 유효성 규칙 범주:

| 규칙 범주 | 설명 | 예시 |
|:---------|:-----|:-----|
| **Step sequence integrity** | `next` 체인 단절 검증 | ContextIngestStep -> NormalizeNeedStep -> ... -> PublishFlowOutcomeAction |
| **Data availability** | `consumes` 입력이 `produces`/초기 데이터로 충족되는지 | BuildKernelInputStep이 소비하는 PrioritizedNeedSet은 NormalizeNeedStep이 생산 |
| **Kernel grounding** | 모든 StepSpec의 kernel_anchor가 유효한 커널 요소를 참조하는지 | KernelGroundedStepSpec._anchor가 커널 엔티티 존재 |

### 2.3 커스텀 조건 설계

커널의 `LAYER_ORDER`, `SAME_BRANCH`에 대응하는 Flow 고유 조건:

| 조건명 | 설명 | 적용 대상 |
|:------|:-----|:---------|
| `SAME_PLANE` | source와 target이 동일 평면(P1/P2/P3)에 속하는지 | 평면 내부 의존성 규칙 |
| `SAME_STEP_CATEGORY` | 두 StepDefinition이 동일 FlowStepCategory를 가지는지 | 동종 단계 간 관계 제한 |
| `DATA_AVAILABLE` | target 단계의 consumes 입력이 선행 produces로 충족되는지 | 데이터 가용성 사전 검증 |

---

## 3. 파이프라인 구현 명세

`docs/ea-sys-conventions.md` 2.1절의 5단계 Design-First Pipeline에 대한 Flow 레이어 구현 현황:

| 단계 | 설명 | 상태 | 비고 |
|:-----|:-----|:-----|:-----|
| Stage 1: 선언 (TOML) | `specs/flow_schema.toml` + `flow_rules.toml` | -- 미구현 | `50-flow.toml` 프로파일은 존재하나 `specs/` 정규 스키마 미생성 |
| Stage 2: 파싱 (Schema) | TOML -> `FlowSchema` frozen 타입 | -- 미구현 | FlowSchema 타입 자체가 미정의 |
| Stage 3: 패턴 컴파일 | @Category/#Layer -> 구체 규칙 확장 | -- 미구현 | `condition_registry.py` 미생성, SAME_PLANE/DATA_AVAILABLE 등 미구현 |
| Stage 4: 자산 거버넌스 | DRAFT -> REVIEW -> APPROVED -> DEPRECATED | -- 미구현 | 수명주기 관리 코드 없음 |
| Stage 5: 카탈로그 합성 | 충돌 해소, 폴백 통합, 커버리지 검증 | 부분 구현 | FlowRuntime이 순차 실행을 수행하나 FlowTopology 시맨틱 그래프 미연동 |

### 프로파일 로딩

| 항목 | 상태 | 비고 |
|:-----|:-----|:-----|
| Profile Loading | -- 미구현 | `50-flow.toml`을 FlowSchema로 파싱하는 로더 없음 |
| Service Layer | -- 미구현 | `flow_service.py` (순수 함수 dict 반환) 미생성 |

---

## 4. 고유 전문성

### 4.1 3-Plane Model 상세

#### P1 Specification -- 선언적 정의

- **StepSpec** (ABC): `name` (str), `kernel_anchor` (str | None), `meta_type` (FlowMetaStep | None), `input_schema`/`output_schema` (SchemaSpec | None). 모든 실행 단계의 추상 계약
- **WorkflowSpec** (ABC): `name`, `kernel_anchor`, `input_schema`/`output_schema`, `get_steps() -> list[StepSpec]`. 단계 시퀀스/그래프의 추상 계약
- **FlowMetaStep** (frozen dataclass): 재사용 가능한 로직 패턴 메타데이터. `name` (I18nString), `description` (I18nString), `input_schema`/`output_schema`, `kernel_type_requirement`
- **KernelGroundedStepSpec**: kernel_anchor로 커널 요소에 바인딩되는 StepSpec 구현. FlowMetaStep의 meta_type을 상속받아 스키마 위임
- **UseCaseSpec**: WorkflowSpec 구현. `description`, `primary_actor`, `success_criteria` 포함. 비즈니스 프로세스의 일급 시민(first-class citizen)
- **FlowTopology** (frozen dataclass): name, steps, entry_point, exit_points, transition_rules, generation_rules. 선언적 프로세스 구조 + 메타모델링 지원
- **FlowGenerationRule** (frozen dataclass): 커널 엔티티 -> 플로우 스펙 자동 생성 규칙. `source_kernel_type`, `target_flow_type`, `naming_pattern`, `required_steps`, `logic_conditions`

#### P2 Coordination -- 조율/그래프

- **ProcessSpec** (frozen dataclass): 프로세스 루트. `id`, `name`, `version`, `steps: list[StepDefinition]`, `trigger_event`, `defined_schemas: list[SchemaDefinition]`, `data_flow_edges: list[DataFlowEdge]`
- **StepDefinition** (frozen dataclass): 프로세스 그래프 노드. `id`, `name`, `category: FlowStepCategory`, `description`, `condition: LogicCondition | None`, `transformation: DataTransformation | None`, `schema_usage: StepSchemaUsage | None`, `next_step_ids: list[str]`, `on_failure_step_id: str | None`
- **DataFlowEdge** (frozen dataclass): 단계 간 데이터 이동. `source_step_id.source_field` -> `target_step_id.target_field`, 선택적 `transformation_rule`
- **LogicCondition** (frozen dataclass): 조건식. `expression`, `engine` (json-logic/python/sql), `parameters`
- **DataTransformation** (frozen dataclass): 데이터 형태 변환. `input_schema` -> `output_schema`, `mapping_rules`
- **SchemaDefinition** (frozen dataclass): 데이터 형태 정의. `id`, `name`, `schema_format`, `definition: dict`
- **StepSchemaUsage** (frozen dataclass): 단계 데이터 계약. `input_schema_id`, `output_schema_id`, `required_fields`
- **FlowOntology**: 프로세스 스펙 타입 레지스트리. `describe() -> dict[str, str]` 정적 메서드
- **FlowStepCategory** (Enum): `ACTION`, `DECISION`, `EVENT`, `GATEWAY`, `TRANSFORMATION`

#### P3 Realization -- 명령적 실행

- **FlowRuntime**: 순차 워크플로우 인터프리터. `implementers: dict[str, StepImplementer]`로 이름 기반 디스패치. 실패 시 역순 보상 롤백 (compensating transaction)
  - `interpret(workflow, variables)` -> `FlowExecutionResult`
  - `execute()`: `interpret()`의 후방 호환 별칭
  - `_resolve_implementer()`: 정확 매칭 -> 접두사(`:` 앞) 매칭 폴백
- **StepImplementer** (ABC): `execute(spec, context) -> StepExecutionResult`, `rollback(spec, context) -> bool`. 모든 실행자는 보상 가능해야 함
- **StepInterpretationResult** (frozen dataclass): `accepted: bool`, `intent: Any`, `logs: list[str]`. `success`/`output` 프로퍼티로 후방 호환
- **FlowExecutionResult** (frozen dataclass): `workflow_name: str`, `execution_id: str`, `success: bool`, `step_results: dict[str, StepInterpretationResult]`, `logs: list[str]`, `interpreted_intents: list[Any]`, `rollback_occurred: bool`

### 4.2 Kernel Grounding

모든 StepSpec은 `kernel_anchor` 프로퍼티로 커널 요소에 근거(grounding)한다. 이는 실행의 구조적 정당성을 제공한다.

- `KernelGroundedStepSpec`: 생성 시 `anchor: str`과 `meta_type: FlowMetaStep`을 받아 커널 바인딩
- `AddRuleStepSpec`: `kernel_anchor` 기본값 `"ea:kernel:rule_creation"`, 커스텀 anchor 지정 가능
- `DeprecateRuleStepSpec`: `kernel_anchor` 기본값 `f"ea:kernel:rule:{rule_id}"`, 커스텀 anchor 지정 가능

### 4.3 Kernel Actions

Flow가 커널 규칙 시스템과 상호작용하는 선언-실행 쌍:

| P1 선언 스펙 | P3 실행자 | 생성 인텐트 |
|:------------|:---------|:-----------|
| `AddRuleStepSpec` | `AddRuleImplementer` | `kernel.submit_rule` -- rule_id, rule_payload, kernel_anchor |
| `DeprecateRuleStepSpec` | `DeprecateRuleImplementer` | `kernel.deprecate_rule` -- rule_id, kernel_anchor |

실행자는 부작용 없이(side-effect free) 선언적 인텐트 데이터만 생산한다. 롤백은 인텐트 계획이 무부작용이므로 보상 가능성만 확인한다.

### 4.4 Schema Validation

`SchemaSpec` ABC를 통한 단계 I/O 계약 검증:

- **JsonSchema2020Spec**: `jsonschema` 라이브러리 기반 JSON Schema 2020-12 검증. `validate(data) -> bool`, `to_dict() -> dict`
- **DbSchemaSpec**: DDL 방식 테이블/뷰 스키마. `table_name`, `columns: dict[str, str]`, 선택적 `ddl`. 구조적 키 존재 검증

### 4.5 FlowProfile

`FlowProfile` (frozen dataclass): 도메인별 메타스텝 컬렉션.

- `name: str`, `version: str`, `meta_steps: tuple[FlowMetaStep, ...]`, `metadata: dict[str, str]`
- `get_meta_step(name: str) -> FlowMetaStep | None`: 이름 기반 검색 (I18nString 텍스트 변환 후 비교)

### 4.6 I18nString 지원

`I18nString = str | dict[str, str]` 타입 별칭을 통해 다국어 단계명을 지원한다. `_as_text()` 헬퍼로 `str` 직접 반환 또는 `dict`에서 `"en"` 키 우선 추출.

---

## 5. 포트 계약 상세

Flow는 6x6 포트 체계를 통해 5개 레이어와 자기 자신에 대한 계약을 정의한다.

### 5.1 FlowModelPort (자체)

Flow 레이어의 자기 참조 포트. `FlowLayerContractMatrix`(6x6 교차 레이어 계약 매트릭스)를 소유한다.

### 5.2 Flow -> Infra

| 포트 요소 | 카테고리 | 설명 |
|:---------|:---------|:-----|
| `FlowStateCheckpoint` | PassiveStructure | 실행 재개를 위한 체크포인트 저장소 |
| `FlowExecutionLog` | PassiveStructure | 단계별 감사 추적 실행 로그 저장소 |

규칙 관계:
- `PersistFlowStateStep` -- depends_on -> `FlowStateCheckpoint` (재개용 상태 의존)
- `PersistFlowStateStep` -- produces -> `FlowExecutionLog` (단계별 실행 로그 생산)
- `ExecuteKernelAction` -- depends_on -> `FlowStateCheckpoint` (상태 복구 의존)
- `FlowRuntimeEngine` -- produces -> `FlowExecutionLog` (실행 로그 항목 생산)

### 5.3 Flow -> Governance

| 포트 요소 | 카테고리 | 설명 |
|:---------|:---------|:-----|
| `FlowApprovalGate` | Behavior | 플로우 모델 변경에 대한 거버넌스 승인 게이트 |
| `FlowAuditSubmission` | Interface | 플로우 실행 증거 제출 감사 포트 |
| `FlowCompliancePolicy` | Governance | 플로우 실행에 대한 거버넌스 준수 정책 |
| `FlowChangeRecord` | PassiveStructure | 플로우 모델 진화 변경 이력 |

규칙 관계:
- `FlowCompliancePolicy` -- constrains -> `ExecuteKernelAction` (준수 정책이 커널 실행 제약)
- `FlowCompliancePolicy` -- constrains -> `PersistFlowStateStep` (준수 정책이 상태 영속화 제약)
- `PublishFlowOutcomeAction` -- coordinates -> `FlowAuditSubmission` (결과 발행 시 감사 증거 제출)
- `PersistFlowStateStep` -- produces -> `FlowChangeRecord` (영속화 시 변경 이력 생산)
- `ContextIngestStep` -- coordinates -> `FlowApprovalGate` (컨텍스트 수집 시 승인 게이트 통과)

### 5.4 Flow -> Decision

| 포트 요소 | 카테고리 | 설명 |
|:---------|:---------|:-----|
| `FlowDecisionGate` | Behavior | 플로우 실행 내 의사결정 평가 지점 |
| `FlowBranchInput` | PassiveStructure | 플로우 전이 지점에서 소비되는 의사결정 분기 입력 |
| `FlowDecisionOutcome` | PassiveStructure | 플로우 경로 선택에 소비되는 의사결정 결과 |
| `FlowDecisionFeedback` | Interface | 플로우 결과를 의사결정 레이어에 보고하는 피드백 포트 |

규칙 관계:
- `MapKernelSpecStep` -- coordinates -> `FlowDecisionGate` (커널 스펙 매핑 시 의사결정 평가)
- `FlowBranchInput` -- consumes -> `BuildKernelInputStep` (커널 입력 구성 시 분기 입력 소비)
- `FlowDecisionOutcome` -- consumes -> `ExecuteKernelAction` (실행 시 의사결정 결과로 경로 선택)
- `PublishFlowOutcomeAction` -- coordinates -> `FlowDecisionFeedback` (결과 발행 시 의사결정 피드백)
- `ContextIngestStep` -- produces -> `FlowBranchInput` (상위 컨텍스트에서 분기 입력 추출)
- `MapKernelSpecStep` -- produces -> `FlowDecisionOutcome` (의사결정 게이트 평가 결과 생산)

### 5.5 Flow -> Needs

| 포트 요소 | 카테고리 | 설명 |
|:---------|:---------|:-----|
| `NeedsFulfillmentReport` | PassiveStructure | 플로우가 충족한 요구사항 추적 보고서 |
| `NeedsCompletionNotification` | Event | 요구 연결 작업 완료 시 알림 이벤트 |

규칙 관계:
- `VerifyOutcomeStep` -- produces -> `NeedsFulfillmentReport` (검증 시 요구 충족 보고서 생산)
- `PublishFlowOutcomeAction` -- produces -> `NeedsCompletionNotification` (발행 시 완료 알림 생산)

### 5.6 Flow -> Kernel

| 포트 요소 | 카테고리 | 설명 |
|:---------|:---------|:-----|
| `KernelContractReference` | PassiveStructure | 스펙 매핑에 소비되는 활성 커널 계약 |
| `KernelValidationResult` | PassiveStructure | 결과 검증에 소비되는 커널 검증 결과 |
| `KernelSpecVersion` | PassiveStructure | 계약 정렬을 위한 커널 스펙 버전 메타데이터 |
| `KernelConstraintHook` | Interface | 플로우 실행 중 커널 검증 호출 훅 |

규칙 관계:
- `KernelContractReference` -- consumes -> `MapKernelSpecStep` (스펙 매핑 시 활성 계약 소비)
- `KernelValidationResult` -- consumes -> `VerifyOutcomeStep` (결과 검증 시 커널 검증 결과 소비)
- `MapKernelSpecStep` -- depends_on -> `KernelSpecVersion` (커널 스펙 버전 메타데이터 의존)
- `ExecuteKernelAction` -- coordinates -> `KernelConstraintHook` (실행 시 커널 제약 훅 조율)
- `BuildKernelInputStep` -- produces -> `KernelContractReference` (커널 입력 구성 시 활성 계약 해석/생산)
- `ExecuteKernelAction` -- produces -> `KernelValidationResult` (커널 실행 결과로 검증 결과 생산)

---

## 6. 구현 로드맵

### HIGH 우선순위

| 항목 | 설명 | 의존성 |
|:-----|:-----|:------|
| **FlowSchema 생성** | frozen dataclass, SchemaPort-compatible. `50-flow.toml` 요소/관계를 정규 스키마 타입으로 변환 | 없음 |
| **FlowTopology 시맨틱 그래프** | ProcessSpec을 쿼리 가능한 그래프로 변환. StepDefinition.next_step_ids 기반 탐색, 도달 가능성 검증 | FlowSchema |
| **TOML 외부화** | `specs/flow_schema.toml` + `specs/flow_rules.toml` 생성. `[meta]` 섹션 포함, self-verification 검증 | FlowSchema |
| **flow_service.py 생성** | 순수 함수 + `dict[str, Any]` 반환 서비스 레이어. keyword-only 인자, lazy init 패턴 | FlowSchema, FlowTopology 그래프 |

### MEDIUM 우선순위

| 항목 | 설명 | 의존성 |
|:-----|:-----|:------|
| **런타임 실행 엔진 확장** | P2 Coordination 통합 -- DataFlowEdge/LogicCondition을 FlowRuntime에 연동. 현재 순차 반복만 지원 | FlowTopology 그래프 |
| **condition_registry.py 생성** | SAME_PLANE, SAME_STEP_CATEGORY, DATA_AVAILABLE 조건 등록/평가. 커널의 KernelConditionType 패턴 차용 | FlowSchema, flow_rules.toml |

### LOW 우선순위

| 항목 | 설명 | 의존성 |
|:-----|:-----|:------|
| **8단계 파이프라인 TOML 정합** | ContextIngest -> ... -> PublishFlowOutcome 전체 파이프라인을 TOML 정의와 런타임 구현 양쪽에서 정합성 검증 | flow_service.py, 런타임 확장 |
