# ea-flow — Coding Conventions & Module Rules

> **공통 구현 컨벤션**: `docs/ea-sys-conventions.md` 참조.
> 본 문서는 실행 레이어 고유 사항(P1/P2/P3 실행 모델, Kernel Grounding, Spec/Implementer 분리)만 기술한다.

실행 레이어. 두 가지 핵심 책임: (1) Spec→Coordination→Realization 3단계 워크플로우 실행, (2) 구체적인 데이터 스키마 스펙 소유. ea-kernel 요소에 근거(grounding), ea-decision에 비의존.

## Design Philosophy

**이중 책임**: Flow는 "어떻게 실행하는가"(실행 흐름)와 "데이터가 어떤 형상인가"(데이터 스키마)를 함께 소유한다. 실질적인 상태 전이 모델링이 일어나는 레이어이므로, 각 단계가 소비/생산하는 데이터의 구체적 스키마를 Flow가 정의하고 검증한다.

### 3-plane Execution Model (실행 흐름)

- **P1 Specification**: 선언적 정의 — StepSpec, WorkflowSpec — "무엇을 실행할 것인가"
- **P2 Coordination**: 조율/그래프 — FlowTopology, DataFlowEdge, LogicCondition — "어떤 순서/조건으로"
- **P3 Realization**: 명령적 실행 — StepImplementer, FlowRuntime — "실제로 어떻게 수행하는가"

### Data Schema Ownership (데이터 스키마)

Flow가 소유하는 데이터 스키마 스펙 체계:

- **SchemaSpec ABC** (schema.py): 스키마 정의·검증 계약. JsonSchema2020Spec, DbSchemaSpec 구현체
- **Step I/O Schema** (spec.py): 모든 StepSpec/WorkflowSpec이 `input_schema`, `output_schema`를 선언
- **Schema Topology** (topology.py): SchemaDefinition, StepSchemaUsage — 프로세스 내 스키마 정의·사용 매핑
- **Data Flow Edge** (topology.py): DataFlowEdge — 단계 간 데이터 흐름 + DataTransformation 변환 규칙
- **Data Contract Catalog** (50-flow.toml): DataContractSpec, SchemaVersionRecord, DataCatalogRegistry, SchemaCompatibilityRule, DataQualityGate, DataLineageRecord

다른 레이어는 추상적 어휘(Kernel의 요소/관계, Needs의 요구, Decision의 옵션/평가)만 정의한다. **구체적인 데이터 형상(JSON Schema, DB Schema, I/O 계약)은 Flow만 소유**한다.

### 핵심 원칙

- **Spec은 사실(fact), Implementer는 해석(interpretation)** — 같은 Spec에 환경별 다른 Implementer를 바인딩
- **스키마는 실행의 계약** — Step I/O 스키마가 단계 간 데이터 정합성을 보장

## Execution Design Principles

핵심 요약:
- Kernel Grounding: 모든 StepSpec은 kernel_anchor로 Kernel 요소에 근거 — 실행의 구조적 정당성
- 보상 가능성: 모든 Implementer의 execute()에 대응하는 rollback() 필수 — 트랜잭션 의미론
- Spec/Implementer 분리: 선언(P1)은 실행(P3)을 모름 — spec.py → runtime.py import 금지
- Decision 비의존: Flow는 Decision을 직접 import하지 않음 — ea-governance가 ModelingAction→StepSpec 변환 중개
- Schema 소유: 구체적 데이터 스키마(JSON Schema, DB Schema)는 Flow 레이어가 유일하게 정의·검증

## Naming Convention

- `~Spec`: 선언적 정의 (P1)
- `Flow~`: 그래프 노드/토폴로지 (P2)
- `~Implementer`: 실행자 (P3)
- `~Result`: 실행 결과 (P3)

## Module Structure (flat)

```
src/ea_flow/
├── __init__.py             # 패키지 docstring
├── types.py                # P1: 공유 타입, 열거형 (I18nString, FlowStepCategory)
├── spec.py                 # P1: ABC 계약 (StepSpec, WorkflowSpec, FlowTopology 등)
├── topology.py             # P2: 데이터 중심 프로세스 스펙 (ProcessSpec, DataFlowEdge)
├── schema.py               # P1: 데이터 스키마 스펙 소유 (SchemaSpec ABC, JsonSchema2020Spec, DbSchemaSpec)
├── kernel_actions.py       # P1: Kernel 연동 스펙 (AddRuleStepSpec, DeprecateRuleStepSpec)
├── kernel_implementers.py  # P3: Kernel 연동 실행 (AddRuleImplementer, DeprecateRuleImplementer)
├── profile.py              # P1: FlowProfile (도메인별 메타스텝 컬렉션)
├── flow_schema.py          # F2.5: FlowSchema (SchemaPort) + FLOW_SCHEMA 싱글턴
├── condition_registry.py   # F2.5: flow_condition_registry() — kernel defaults + 4개 조건
├── profile_bridge.py       # F3: load_flow_profile() / load_flow_profile_from_content()
├── runtime.py              # P3: 실행 엔진 (FlowRuntime, StepImplementer ABC)
├── execution_store.py      # S3: ExecutionStore (ABC → InMemory → SQLite) — 워크플로 실행 기록 영속화
├── flow_analyzer.py        # S4: FlowAnalyzer — 스텝 효과성·병목 감지·처리량 분석
├── flow_simulator.py       # S5: FlowSimulator — 토폴로지 변경 What-If 시뮬레이션
├── workflow_promotion.py   # S5: WorkflowPromotionEngine — 워크플로 승격/폐기 워크플로
├── flow_propagation.py     # S6: FlowPropagationEngine — 워크플로 변경의 기존 실행 기록 영향 전파 평가
├── anchor_validation.py    # Kernel↔Flow 양방향 인식 — kernel_anchor 검증 + 역방향 조회
└── workflow_version_store.py # S3: WorkflowVersionStore — 워크플로 스펙 버전 관리 (ABC → InMemory → SQLite)
```

### 잔여 한계

kernel_implementers.py는 context에서 governance_system 참조할 뿐 실제 Kernel import 없는 Mock 수준. FlowRuntime.execute()는 순차 반복만 지원하며, DataFlowEdge·LogicCondition은 정의만 존재하고 런타임에 연동되지 않음. FlowTopology.transition_rules가 Dict[str, str]이어서 그래프 탐색 불가.

## Import Convention

**절대 경로 중심**.

```python
from ea_flow.spec import StepSpec, WorkflowSpec
from ea_flow.runtime import FlowRuntime, StepImplementer
```

## Typing Convention

- Python 3.11+ 현대 문법: `list[]`, `dict[]`, `str | None`

## Module Rules

### File Size

목표 700줄, 경고 1000줄, 강제분할 1500줄.

### Dependency Direction

```
types.py: 독립 (I18nString, FlowStepCategory)
  ← spec.py (I18nString)
  ← topology.py (FlowStepCategory)
spec.py ← kernel_actions.py (StepSpec)
        ← profile.py (FlowMetaStep)
        ← runtime.py (WorkflowSpec, ExecutionContext, StepSpec)
runtime.py ← kernel_implementers.py (StepImplementer, StepExecutionResult)
kernel_actions.py ← kernel_implementers.py (AddRuleStepSpec, DeprecateRuleStepSpec)
schema.py: 독립 (외부 의존 없음)
flow_schema.py: 독립 (FlowSchema, FlowEntity, FlowRelation, FLOW_SCHEMA)
condition_registry.py: ea_profile.types lazy import (ConditionRegistry)
profile_bridge.py: flow_schema + condition_registry ← ea_profile.loader lazy import

[S3/S4/S5 Governance Lifecycle]
execution_store.py: 독립 (자체 도메인 타입 정의)
  ← flow_analyzer.py (ExecutionStore — TYPE_CHECKING import)
  ← flow_simulator.py (ExecutionStore — TYPE_CHECKING import)
flow_analyzer.py ← workflow_promotion.py (FlowAnalysisReport, StepEffectiveness — TYPE_CHECKING import)
flow_propagation.py: execution_store (ExecutionStore — TYPE_CHECKING import)
anchor_validation.py: ea_kernel.definition lazy import (kernel_anchor 검증 + 역방향 조회)
workflow_version_store.py: 독립 (자체 도메인 타입 정의)
```

선언(P1/P2)이 실행(P3)을 모르는 것이 최우선 규칙이다. spec.py/types.py → runtime.py/kernel_implementers.py import 금지. 이는 Kernel의 types.py가 kernel_service.py를 모르는 것과 동일한 원칙이다.
topology.py는 spec.py와 독립적으로 유지한다. 그래프 구조(P2)는 계약(P1)의 구현 세부사항을 알 필요가 없으며, types.py의 열거형만으로 충분하다.

### 6-Phase Governance Lifecycle (S3/S4/S5)

Kernel의 6-phase governance lifecycle 패턴을 Flow 도메인 어휘로 번역:
- **S3 Recording** (execution_store.py) — 워크플로 실행 기록 영속화 (ABC → InMemory → SQLite 3-tier)
- **S4 Analysis** (flow_analyzer.py) — 스텝 효과성, 병목 감지, 처리량 분석
- **S5 Evolution** (flow_simulator.py, workflow_promotion.py) — What-If 시뮬레이션 + 워크플로 승격/폐기 워크플로
- **S6 Propagation** (flow_propagation.py) — 워크플로/스텝 변경의 기존 실행 기록 영향 전파 평가

Store 패턴은 ea-kernel/decision_store.py와 동일: `__slots__`, `@contextmanager _connection()`, `_init_schema()`.
Promotion 패턴은 ea-kernel/promotion_engine.py와 동일: in-memory proposal store, vote/approve/reject/apply 워크플로.

### Test Convention

- 절대 경로 import
- self-contained 테스트 파일
