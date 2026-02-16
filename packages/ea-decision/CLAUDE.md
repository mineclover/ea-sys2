# ea-decision — Coding Conventions & Module Rules

의사결정 레이어. Design Thinking 기반 Intent→Choice→Decision 프로세스. ea-kernel에 단방향 의존.

## Design Philosophy

3-layer Narrative Abstraction:
- **N1 Vocabulary**: 불변 타입 정의 — Intent, Evidence, Option, Decision, Pattern 등 frozen 데이터
- **N2 Process**: 워크플로우 실행 — Topic(Aggregate Root)이 Diverge→Converge→Plan→Action 오케스트레이션
- **N3 Integration**: Kernel/Flow 연동 — ModelingAction→RuleAsset 변환, repository 영속화

핵심 원칙: **결정은 증거의 함수 — 모든 Decision은 Evidence에 의해 정당화되고, 확정 후 불변**

## Decision Process Principles

핵심 요약:
- 의도 선행: Option 생성 전 Intent 필수 — "왜 결정해야 하는가"가 "무엇을 결정할 것인가"에 선행
- 불변 기록: 확정된 Decision은 수정 불가, 새 Decision이 대체(supersede) — Kernel RuleLifecycle 패턴과 동일
- Pattern 기반 인지: 반복되는 결정 유형은 DecisionPattern으로 템플릿화하여 일관성 확보
- Kernel 단방향 의존: Decision → Kernel은 ModelingAction으로 요청, Kernel → Decision은 ID 기반 간접 참조(RuleProvenance.decision_ref). Kernel은 Decision 타입을 절대 import하지 않음

## Module Structure (flat)

```
src/ea_decision/
├── __init__.py          # 패키지 docstring
├── types.py             # N1: 통합 불변 타입 (Intent, Choice, DecisionResult, DecisionTopic 등)
├── topic.py             # N2: Topic Aggregate Root + mutable 프로세스 타입
├── pattern.py           # N1+N2: DecisionPattern + PatternSchema (pattern_schema 흡수)
├── lifecycle.py         # N2: DecisionLifecycle 상태 머신 (frozen, 전이→새 인스턴스)
├── evidence.py          # N1+N2: 구조화 증거 (EvidenceType, Evidence, EvidenceCollection)
├── evaluation.py        # N2: 평가 프레임워크 (EvaluationDimension, OptionScore, EvaluationResult)
├── decision_schema.py   # D2.5: DecisionSchema (SchemaPort) + DECISION_SCHEMA 싱글턴
├── condition_registry.py # D2.5: decision_condition_registry() — kernel defaults + 5개 조건
├── profile_bridge.py    # D3: load_decision_profile() / load_decision_profile_from_content()
├── kernel_bridge.py     # N3: Kernel 연동 (lazy import, 유일한 ea_kernel 참조점)
├── process.py           # N2: DesignThinkingProcess 오케스트레이터
├── registry.py          # N3: DecisionRegistry (패턴 등록/조회)
└── repository.py        # N3: DecisionRepository (파일 기반 영속화)
```

N1 타입 전부 `frozen=True`. N2 Aggregate(Topic)만 mutable 허용. DecisionLifecycle: frozen, 전이마다 새 인스턴스 반환(Kernel RuleLifecycle 패턴).

### 잔여 한계

Lifecycle 상태 머신(lifecycle.py)이 아직 Topic에 통합되지 않음 — 상태 전이가 Topic 메서드에 하드코딩. Evidence가 비구조화 마크다운(ResearchNote.content: str) — evidence.py의 구조화 타입과 미연동. evaluation.py의 EvaluationResult가 Topic의 Evaluation과 미통합.

## Import Convention

**절대 경로 중심**.

```python
from ea_decision.types import Intent, ChoiceOption, DecisionResult
from ea_decision.pattern import DecisionPattern
```

## Typing Convention

- Python 3.11+ 현대 문법: `list[]`, `dict[]`, `str | None`

## Module Rules

### File Size

목표 700줄, 경고 1000줄, 강제분할 1500줄.

### Dependency Direction

```
types.py: 독립 (I18nString, DecisionStatus, Reference, Intent, Choice 등)
  ← pattern.py (I18nString)
  ← lifecycle.py (_now)
  ← evidence.py (_generate_id, _now)
  ← topic.py (DecisionStatus, Reference, I18nString, _generate_id, _now)
types.py ← process.py (Intent, ChoiceOption, Choice, DecisionResult)
pattern.py ← topic.py (DecisionComplexity, DecisionPattern)
           ← registry.py (DecisionPattern)
topic.py ← repository.py (Topic)
decision_schema.py: 독립 (DecisionSchema, DecisionEntity, DecisionRelation, DECISION_SCHEMA)
condition_registry.py: ea_profile.types lazy import (ConditionRegistry)
profile_bridge.py: decision_schema + condition_registry ← ea_profile.loader lazy import
kernel_bridge.py: ea_kernel.types lazy import (유일한 Kernel 참조점)
```

types.py는 순수 어휘(N1)이므로 프로세스(N2)나 통합(N3) 모듈을 절대 import하지 않는다. 이는 Kernel의 types.py가 service/mcp 모듈을 모르는 것과 동일한 원칙이다.
kernel_bridge.py만 ea_kernel.types를 lazy import한다. 나머지 모듈은 Kernel 타입을 알지 못하며, string ID 기반 간접 참조만 사용한다.

### Test Convention

- 절대 경로 import
- self-contained 테스트 파일
