# ea-flow — Coding Conventions & Module Rules

실행 레이어. Spec→Coordination→Realization 3단계 워크플로우 실행. ea-kernel 요소에 근거(grounding), ea-decision에 비의존.

## Design Philosophy

3-plane Execution Model:
- **P1 Specification**: 선언적 정의 — StepSpec, WorkflowSpec, SchemaSpec — "무엇을 실행할 것인가"
- **P2 Coordination**: 조율/그래프 — FlowTopology, DataFlowEdge, LogicCondition — "어떤 순서/조건으로"
- **P3 Realization**: 명령적 실행 — StepImplementer, FlowRuntime — "실제로 어떻게 수행하는가"

핵심 원칙: **Spec은 사실(fact), Implementer는 해석(interpretation) — 같은 Spec에 환경별 다른 Implementer를 바인딩**

## Execution Design Principles

핵심 요약:
- Kernel Grounding: 모든 StepSpec은 kernel_anchor로 Kernel 요소에 근거 — 실행의 구조적 정당성
- 보상 가능성: 모든 Implementer의 execute()에 대응하는 rollback() 필수 — 트랜잭션 의미론
- Spec/Implementer 분리: 선언(P1)은 실행(P3)을 모름 — spec.py → runtime.py import 금지
- Decision 비의존: Flow는 Decision을 직접 import하지 않음 — ea-governance가 ModelingAction→StepSpec 변환 중개

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
├── schema.py               # P1: 스키마 구현 (SchemaSpec, JsonSchema2020Spec, DbSchemaSpec)
├── kernel_actions.py       # P1: Kernel 연동 스펙 (AddRuleStepSpec, DeprecateRuleStepSpec)
├── kernel_implementers.py  # P3: Kernel 연동 실행 (AddRuleImplementer, DeprecateRuleImplementer)
├── profile.py              # P1: FlowProfile (도메인별 메타스텝 컬렉션)
├── runtime.py              # P3: 실행 엔진 (FlowRuntime, StepImplementer ABC)
├── definitions.py          # ⚠️ shim → spec.py re-export (하위 호환)
└── ontology.py             # ⚠️ shim → topology.py re-export (하위 호환)
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
definitions.py: shim → spec.py
ontology.py: shim → topology.py
```

선언(P1/P2)이 실행(P3)을 모르는 것이 최우선 규칙이다. spec.py/types.py → runtime.py/kernel_implementers.py import 금지. 이는 Kernel의 types.py가 kernel_service.py를 모르는 것과 동일한 원칙이다.
topology.py는 spec.py와 독립적으로 유지한다. 그래프 구조(P2)는 계약(P1)의 구현 세부사항을 알 필요가 없으며, types.py의 열거형만으로 충분하다.
definitions.py와 ontology.py는 하위 호환 shim이다. 내부 코드는 새 경로(spec.py, topology.py)를 사용한다.

### Test Convention

- 절대 경로 import
- self-contained 테스트 파일
