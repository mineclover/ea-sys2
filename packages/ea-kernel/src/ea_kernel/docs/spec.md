# ea-kernel v2.5.0 Feature Specification

## 개요

ea-kernel은 비즈니스 의사결정 구조를 프레임워크에 독립적으로 표현하는 경량 커널 메타모델이다.
KerML의 "행위는 관계의 자격(qualification)" 원리에 기반한 4계층 점진적 추상화로
15개 엔티티 × 14개 관계의 보편적 구조 제약을 정의한다.

**핵심 수치**:
- 15 entities (4 abstract + 11 concrete), 14 relations, 20 attributes
- 81 validity rules (67 explicit + 14 fallback)
- 2 layer constraints
- 5 framework profiles (ArchiMate, TOGAF, Zachman, SysML 2.0, BPMN 2.0)
- 1064+ tests, 92% code coverage
- Profile Framework: 12 modules (생성 + 수명주기 관리)
- Rule Corpus: 메타데이터 부착 + 쿼리 + 증거 기반 판단 (Phase 0.5)
- TopologyGraph: 그래프 탐색 + BFS 경로 열거 + 영향 분석 (Phase 2)
- InstanceValidator + DecisionLedger: M0 적합성 검증 + 의사결정 기록 (Phase 3)
- AIDecisionInterface: AI 에이전트 구조화된 컨텍스트 + 추천 + 설명 (Phase 4)

---

## 0. 설계 기반

### 0-A. 커널 범위와 시스템 경계

커널은 **토폴로지 거버넌스**를 담당한다: 타입 카탈로그(고유 식별) + 유효성 규칙(비즈니스 로직) + 프로파일 프레임워크(도메인 매핑).

**커널이 하는 것**:
- 15개 엔티티와 14개 관계의 타입 카탈로그 — 의사결정 구조의 보편적 어휘
- 67개 explicit rule + 14개 fallback rule — 구조적으로 허용/금지되는 관계의 경계
- 프로파일 프레임워크 — 도메인 프레임워크(ArchiMate, TOGAF 등)의 요소를 커널 타입에 매핑

**커널이 하지 않는 것**:
- Feature composition/typing 제약 — 커널 토폴로지와 직교하는 관심사. 소비자 레이어의 책임
- 분석/시각화 — 소비자 레이어의 책임

### 0-B. MOF 레이어링

| MOF 레이어 | ea-kernel 매핑 | 역할 |
|-----------|---------------|------|
| M3 | `types.py` | 메타모델 정의 어휘 (KernelEntity, KernelRelation, KernelValidityRule, KernelSchema) |
| M2 | `definition.py` + `spec` | 15 entities × 14 relations × 67 rules — 커널의 실체 |
| M1 | `profiles/*.py` + profile framework | 도메인 요소→커널 타입 매핑 (ArchiMate의 BusinessProcess→step 등) |
| M0 | 소비자 영역 | SQLite/TOML/TypeDB로 인스턴스 생성 — 커널 범위 밖 |

M3는 M2를 정의하는 문법이고, M2는 "무엇이 있고 무엇이 허용되는가"의 실체이며, M1은 특정 도메인의 어휘를 M2에 매핑한다.

### 0-C. KerML/SysML 2.0 참조

ea-kernel은 KerML의 설계 철학을 차용하되, 그 구현을 그대로 따르지는 않는다.

**차용한 핵심 원리**:
1. **"Feature는 Type이다"** — feature는 classifier와 동등한 metatype 하위이며, specialization/typing에 참여 가능
2. **"행위는 관계의 자격이다"** — L3 관계(flow, succession, triggering 등)는 L2 관계에 행위적 의미를 부여
3. **"Step은 Feature다"** — step(행위 단위)은 feature의 특수화로, 구조와 행위가 하나의 계층에 존재

**엔티티 매핑**:

| ea-kernel | KerML 원본 | 차이점 |
|-----------|-----------|--------|
| element | Element | 동일 — 루트 추상 타입 |
| namespace | Namespace | 동일 — 명명된 요소 컨테이너 |
| metatype | Type | 이름 변경 — `type`이 Python 예약어와 충돌 |
| classifier | Classifier | 동일 — 인스턴스를 분류하는 타입 |
| feature | Feature | 동일 — 타입의 구조적 특성 |
| port | PortUsage → Feature | 단순화 — Usage/Definition 이중 구조 없이 feature 하위로 |
| step | Step | 동일 — 행위의 기본 단위 |
| action | ActionUsage → Step | 단순화 — 실행 가능한 행위 |
| event | OccurrenceUsage → Feature | 단순화 — 이벤트 발생 |
| expression | Expression | 동일 — 평가 가능한 식 |
| state | StateUsage → Classifier | 재배치 — KerML에서는 Feature 하위이나, 커널에서는 상황 분류자로서 metatype 직계 |
| structure | — | 신규 — 능동 구조 (KerML에서는 Block/PartUsage에 해당) |
| item | — | 신규 — 수동 구조 (KerML에서는 Item에 해당) |
| datatype | DataType | 동일 — 값 타입 |
| package | Package | 동일 — 네임스페이스 컨테이너 (metatype 밖) |

**관계 매핑**:

| ea-kernel | KerML 원본 | 차이점 |
|-----------|-----------|--------|
| membership | Membership | 동일 |
| ownership | OwningMembership | 동일 — 소유 관계 |
| specialization | Specialization | 동일 |
| feature_typing | FeatureTyping | 동일 |
| association | Association | 동일 |
| connector | Connector | 동일 |
| redefinition | Redefinition | 동일 |
| subsetting | Subsetting | 동일 |
| flow | ItemFlow → Connector | 단순화 — 데이터/자원 흐름 |
| succession | Succession → Connector | 단순화 — 시간적 순서 |
| interaction | Interaction → Association | 단순화 — 상호작용 |
| triggering | TransitionUsage | 재해석 — 이벤트 트리거 관계 |
| guarding | TransitionUsage (guard) | 재해석 — 조건부 제어 |
| transition | Transition (StateMachine) | 신규 — 상태 전이 (UML 2.5.1 §14.2) |

**미차용 목록** (의도적 제외):
- **Conjugation** — 포트 방향 반전. 커널의 단순 port 모델에서 불필요
- **Disjoining** — 타입 간 배타적 관계. 커널은 deny rule로 동일 효과 달성
- **Usage/Definition 이중 구조** — KerML의 핵심이나 커널의 목적(프레임워크 간 비교)에는 과도한 복잡성
- **Multiplicity** — 속성으로 존재하나 유효성 규칙에는 미사용
- **Featuring** — Feature와 Type의 소유 관계. 커널에서는 ownership으로 통합

### 0-D. 구조 안정성

**15×14 구조**: v2.0에서 transition 관계 추가 (13→14). 67 explicit rule (v1.9의 66 + trans-01).

**67 규칙의 구성**:
- 30 deny 중 19개 타입 이론적 자명 (specialization deny 12개 등 — 계층 구조에서 논리적으로 불가능한 조합)
- 30 deny 중 10개 합리적 설계 선택 (interaction deny 3, guarding deny 5, triggering deny 2)
- 30 deny 중 1개 레이어 원칙 (own-04: item→structure ownership deny)
- 37 allow는 각 관계의 유효한 참여자를 명시 (v2.0: trans-01 추가)

**변경 여지 없는 영역**:
- specialization deny (12): 계층 구조에서 자명 — feature*↔classifier* 교차, package isolate 등
- succession allow (9): step/action/event 간 시간적 순서 — L4 behavioral 완전 열거
- guarding (6): state↔step* 기반 조건부 제어 — guard-01 allow + 5 deny
- triggering (4): feature*→step* 트리거 — trig-01/02 allow + trig-03/04 deny
- transition (1): state→state 상태 전이 — trans-01 allow + fallback deny

**식별 체계**:
- M3: `entity.name` — Python 식별자 (예: `"structure"`, `"step"`)
- M2: `rule.id` — 관계 약어 + 번호 (예: `"spec-04"`, `"assoc-01"`)
- M1: `element.name` + `profile.name` + `version` (예: `"BusinessProcess"` in `"ArchiMate 3.2"`)

---

## 1. Core Engine

### 1-A. 4-Layer Progressive Abstraction

| Layer | 역할 | 엔티티 | 관계 |
|-------|------|--------|------|
| L1 Structure | 정적 구조 요소 | element, namespace, metatype, classifier | — |
| L2 Relationship | 구조적 연결 | feature, port, structure, item, datatype, package | membership, ownership, specialization, feature_typing, association, connector, redefinition, subsetting |
| L3 Behavioral | 관계에 행위 자격 부여 | — | flow, succession, interaction, triggering, guarding, transition |
| L4 Concrete | 구체적 행위 모델 | step, action, event, expression, state | — |

L3는 L2와 별개가 아니라 L2의 자격부여이므로, 구조와 행위가 하나의 연속체로 표현된다.

### 1-B. 엔티티 계층

```
element (abstract)
├── namespace (abstract)
│   ├── metatype (abstract)
│   │   ├── feature           ← L2 structural attribute
│   │   │   ├── port          ← Interface point
│   │   │   ├── step          ← Behavioral step
│   │   │   ├── action        ← Executable action
│   │   │   ├── event         ← Event occurrence
│   │   │   └── expression    ← Evaluatable expression (owns: kind)
│   │   ├── classifier (abstract)
│   │   │   ├── structure     ← Active structure
│   │   │   ├── item          ← Passive structure
│   │   │   └── datatype      ← Value type
│   │   └── state             ← Situation classifier (plays: transition)
│   └── package               ← Namespace container (metatype 밖)
```

11개 concrete entity × 11 × 14 relations = **1,694** 검증 가능 트리플 (exhaustive analysis 대상)

### 1-C. 패턴 매칭

Validity rule의 source/target 패턴:

| 패턴 | 매칭 대상 |
|------|----------|
| `element*` | 모든 엔티티 (element + 모든 하위) |
| `namespace*` | namespace 하위 (package, metatype, classifier, feature, ...) |
| `metatype*` | metatype 하위 (feature, port, step, ..., classifier, structure, item, datatype, state) |
| `classifier*` | classifier 하위 (structure, item, datatype) |
| `feature*` | feature 하위 (port, step, action, event, expression) |
| `step*` | step + action |
| `feature` | feature만 (exact match) |

`*` suffix는 해당 엔티티 + 모든 하위 concrete 엔티티를 포함한다.

### 1-D. Priority-Based Rule Resolution

```
Priority 1       → deny-by-default fallback (관계당 1개, 14개)
Priority 40-50   → broad metatype-level allows
Priority 60      → general structural patterns
Priority 70      → specific behavioral patterns
Priority 80-90   → explicit prohibitions (override allows)
```

동일 priority에서 allow/deny 충돌 시 **deny-first tiebreak** 적용.
높은 priority 규칙이 낮은 priority 규칙을 항상 override.

### 1-E. Condition Types

| Condition | 의미 | 예시 |
|-----------|------|------|
| `LAYER_ORDER` | source layer ≤ target layer | mem-01: namespace→element 포함 관계 |
| `SAME_LAYER` | source, target 동일 layer | — |
| `SAME_ENTITY_BRANCH` | source, target가 동일 상속 분기 | own-03: feature→feature 중첩 소유 |
| `ANCESTOR_OF` | source가 target의 조상 | — |

### 1-F. Layer Constraints

규칙 매칭 이전에 적용되는 레이어 수준 제약 (2개):

| Source | Target | 금지 관계 | 예외 |
|--------|--------|----------|------|
| L4 | L4 | association | step*↔state (realization/motivation) |
| L4 | L4 | connector | (없음) |

L4 behavioral entity끼리의 L2 structural association/connector를 원천 차단한다.

### 1-G. Rule Corpus (Phase 0.5)

`validate_relationship()`과 **병렬 경로**로 증거 기반 판단을 제공하는 규칙 코퍼스.

**핵심 타입**:

| 타입 | 용도 |
|------|------|
| `RuleCategory` | structural / behavioral / domain / empirical |
| `RuleConfidence` | universal / common / contextual / empirical |
| `RuleMetadata` | domain, tags, category, confidence, source, rationale |
| `RuleCorpusEntry` | KernelValidityRule + RuleMetadata |
| `RuleEvidence` | 개별 규칙의 매칭·승리·조건 평가 증거 |
| `JudgmentReport` | verdict + evidence + confidence + domains + conflicts |

**사용법**:

```python
from ea_kernel.rule_corpus import RuleCorpus
from ea_kernel.spec import KERNEL_SPEC

corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)

# 쿼리
structural = corpus.by_category(RuleCategory.STRUCTURAL)
universal  = corpus.by_confidence(RuleConfidence.UNIVERSAL)

# 증거 기반 판단 (verdict는 validate_relationship()과 동일)
report = corpus.judge("structure", "item", "association")
# report.verdict, report.evidence, report.confidence, report.conflicts

# 교차 도메인 충돌 감지
conflicts = corpus.detect_conflicts("item", "structure", "specialization")
```

**메타데이터 추론**: TOML에 명시 metadata가 없으면 `infer_metadata()`가 관계 레이어(L2→structural, L3→behavioral)와 규칙 성격(deny+high→universal)에서 자동 추론.

### 1-H. Topology Navigation (Phase 2)

그래프 탐색과 경로 열거. AI가 "A에서 B까지의 흐름 경로"를 탐색, 영향 분석 수행.

**핵심 타입**:

| 타입 | 용도 |
|------|------|
| `GraphEdge` | source, target, relation + optional JudgmentReport |
| `GraphPath` | edges tuple + total_confidence + nodes/length properties |

**사용법**:

```python
from ea_kernel.graph_view import TopologyGraph
from ea_kernel.spec import KERNEL_SPEC

graph = TopologyGraph(KERNEL_SPEC)       # ~9min (exhaustive topology)
graph = TopologyGraph.from_spec()        # factory shortcut

out = graph.outgoing("structure", "association")  # → tuple[GraphEdge]
paths = graph.find_paths("structure", "item", max_depth=3)
reachable = graph.reachable("structure", max_depth=2)
impact = graph.impact_analysis("feature", direction="outgoing", max_depth=3)
dist = graph.relation_distribution()     # → dict[str, int]
```

### 1-I. Instance + Decision Recording (Phase 3)

M0 인스턴스 적합성 검증 + 의사결정 기록. 결정이 empirical 코퍼스 엔트리로 환류.

**핵심 타입**:

| 타입 | 용도 |
|------|------|
| `InstanceElement` | M0 인스턴스 요소 (id, entity_type, name, properties) |
| `InstanceRelation` | M0 인스턴스 관계 (id, relation_type, source_id, target_id) |
| `ConformanceResult` | 적합성 결과 (valid, element_id, check_type, details, rule_id) |
| `DecisionRecord` | 의사결정 기록 (actor, decision_type, subject_triple, judgment, override_reason) |

**사용법**:

```python
from ea_kernel.instance_validator import InstanceValidator
from ea_kernel.decision_ledger import DecisionLedger

validator = InstanceValidator(KERNEL_SPEC)
results = validator.validate_model(elements, relations)

ledger = DecisionLedger()
ledger = ledger.record(decision)         # mutable — returns self (v2.5.0)
patterns = ledger.override_patterns(min_count=3)
entries = ledger.to_empirical_entries()   # → RuleCorpusEntry tuple
```

### 1-J. AI Decision Interface (Phase 4)

AI 에이전트가 커널과 직접 상호작용하는 구조화된 인터페이스.

**핵심 타입**:

| 타입 | 용도 |
|------|------|
| `DecisionContext` | subject_triple + judgment + related_decisions + reachable_paths |
| `Recommendation` | triple + score(0-1) + judgment + rationale |

**Scoring**: UNIVERSAL→1.0, COMMON→0.7, CONTEXTUAL→0.4, EMPIRICAL→0.2 + override boost.

**사용법**:

```python
from ea_kernel.ai_interface import AIDecisionInterface

ai = AIDecisionInterface.from_kernel()
ctx = ai.build_context("structure", "item", "association")
recs = ai.recommend_relations("structure", "item", top_k=5)
recs = ai.recommend_targets("structure", "association", top_k=5)
explanation = ai.explain("structure", "item", "association")
results = ai.validate_model_with_context(elements, relations)
```

---

## 2. Rule Specification (TOML)

### 2-A. 파일 위치

```
src/ea_kernel/specs/kernel_rules.toml
```

### 2-B. TOML 구조

```toml
[meta]
kernel_version = "2.5.0"
total_explicit_rules = 67

fallback_relations = [
    "membership", "ownership", "specialization", ...
]

[[layer_constraints]]
source_layer = "L4"
target_layer = "L4"
forbidden = ["association"]
allowed_pairs = [["step*", "state"], ["state", "step*"]]
priority = 90

[rules.mem-01]
source = "namespace*"
target = "element*"
relation = "membership"
valid = true
priority = 40
conditions = ["LAYER_ORDER"]
notes = "Namespace contains elements (container layer <= member layer)"

# Phase 0.5: 선택적 메타데이터 (기존 _parse_rule()은 무시)
[rules.mem-01.metadata]
domain = "kernel"
tags = ["containment", "namespace"]
category = "structural"          # structural | behavioral | domain | empirical
confidence = "universal"         # universal | common | contextual | empirical
source = "UML 2.5.1 §7.4 Namespaces"
established_version = "1.0.0"
rationale = "Namespaces are the fundamental containment mechanism"
```

### 2-C. 규칙 분포 (v2.0+)

| 관계 | Explicit Rules | Allow | Deny |
|------|:-:|:-:|:-:|
| membership | 2 | 2 | 0 |
| ownership | 4 | 3 | 1 |
| specialization | 15 | 3 | 12 |
| feature_typing | 7 | 4 | 3 |
| association | 7 | 5 | 2 |
| connector | 1 | 1 | 0 |
| redefinition | 3 | 1 | 2 |
| subsetting | 1 | 1 | 0 |
| flow | 3 | 3 | 0 |
| succession | 9 | 9 | 0 |
| interaction | 4 | 1 | 3 |
| triggering | 4 | 2 | 2 |
| guarding | 6 | 1 | 5 |
| transition | 1 | 1 | 0 |
| **합계** | **67** | **37** | **30** |

+ 14 fallback deny = **81 total rules**

---

## 3. Profile System

### 3-A. 2-Stage Validation

```
Stage 1: Profile rules → 도메인 수준 제약 (@Category, #Layer 패턴)
Stage 2: Kernel rules → 구조적 불변식 (엔티티 계층 매칭)
```

프로파일은 커널 위에 제약만 추가할 수 있고, 커널 제약을 완화할 수 없다.

### 3-B. Framework Profiles

| Profile | Elements | Relations | Kernel Type Coverage | Kernel Relation Coverage |
|---------|:--------:|:---------:|:--------------------:|:------------------------:|
| ArchiMate 3.2 | 58 | 11 | 10/11 | 6/14 |
| TOGAF 10 | 54 | 18 | 10/11 | 6/14 |
| Zachman 6.0 | 36 | 12 | 10/11 | 6/14 |
| SysML 2.0 | 25 | 13 | **11/11** | 13/14 |
| BPMN 2.0 | 27 | 8 | 8/11 | 7/14 |

transition 관계(v2.0 추가)를 사용하는 프로파일은 아직 없음. SysML 2.0이 11/11 타입 완전 사용 달성.

### 3-C. Package Exposure Pattern

`package`는 `metatype` 계층 밖이므로 association에 직접 참여 불가.
package가 소유한 port를 노출점으로 선언하고, 외부 연결은 이 노출점을 통해 수행:

```
package ──ownership──→ port ──association──→ metatype*
         (own-01 ✅)          (assoc-01 ✅)
```

---

## 4. TypeDB Integration

### 4-A. Schema

```
src/ea_kernel/schemas/
  kernel.tql    — 28-element TypeDB schema definition
  seed.tql      — Initial seed data
```

### 4-B. Pure Python Parser

`schema/parser.py` — TypeDB 의존성 없이 TypeQL `define` 블록을 파싱하여
entity type, relation type, attribute type을 추출한다. 테스트 및 스키마 검증에 사용.

### 4-C. Client

`client/connection.py` — TypeDB 3.7+ lazy driver, context-managed transaction.
`@pytest.mark.typedb`로 TypeDB 의존 테스트 격리.

---

## 5. Module Dependency Map

```
types.py              ← 순수 dataclass, zero import (+ Rule Corpus 타입)
    ↑
definition.py         ← 15 entities, 14 relations, 20 attributes
    ↑
spec_loader.py        ← TOML → KernelValidityRule + RuleMetadata 파싱
    ↑
spec.py               ← KERNEL_SPEC (kernel_rules.toml 로드)

rule_corpus.py        ← 규칙 코퍼스 (types.py만 import)
graph_view.py         ← TopologyGraph (types.py + spec lazy import) [Phase 2]
instance_validator.py ← M0 인스턴스 검증 (types.py만 import) [Phase 3]
decision_ledger.py    ← 의사결정 원장 (types.py만 import) [Phase 3]
ai_interface.py       ← AI 인터페이스 (types.py + 위 모듈 lazy import) [Phase 4]

profile_types.py      ← 프로파일 타입 + 프레임워크 인터페이스 타입
    ↑
profile_builder.py    ← 프로파일 빌더 + build_with_corpus() (rule_corpus lazy import)
    ↑
profile_loader.py     ← TOML → KernelProfile 로드
profile_quality_gate.py ← 품질 게이트
test_harness.py       ← 표준 테스트 생성
profile_serializer.py ← JSON 직렬화
    ↑
profile_store.py      ← SQLite 영속화
    ↑
profile_registry.py   ← 인메모리 + 영속화 레지스트리
profile_diff.py       ← 프로파일 diff
profile_schema.py     ← 프로파일 스키마 검증
profile_query.py      ← 프로파일 쿼리
profile_composer.py   ← extend/subset 합성

schema/               ← TypeQL 파서, 로더
client/               ← TypeDB 연결
profiles/             ← 5개 프레임워크 프로파일
```

`definition.py`는 KERNEL_VERSION 외 변경 없음 보장. `types.py`는 Phase별 frozen dataclass 추가.

---

## 6. v1.2 이후 주요 변경 이력

| 버전 | 주요 변경 |
|------|----------|
| v1.2 | L4×L4 association deny, state↔feature deny, succession 세분화, own-05 추가 |
| v1.3 | expression/event succession 확장 (succ-05~09) |
| v1.4 | BPMN 2.0 프로파일 추가 |
| v1.5 | Profile analyzer, cross-profile 분석 |
| v1.6 | TypeQL parser, schema validation |
| v1.7 | Package association rules (assoc-05~07), layer constraints |
| v1.8 | Rule TOML externalization (spec.py → specs/kernel_rules.toml) |
| v1.9 | Rule version store, evaluation pipeline, integrity analysis, dead rule cleanup (own-03/04) |
| v1.9→flat | v2/ 디렉토리 구조를 flat 구조로 전환 (profile_types.py 합병), 13→12 모듈 |
| Phase 0.5 | Rule Corpus Model — 6 타입, rule_corpus.py, spec_loader 확장, builder 확장, 51 테스트 |
| v2.0 | 15×14 구조 변경 — transition 관계 추가, execution_mode/join_mode 속성, expression owns kind, state plays transition |
| v2.2.0 (Phase 2) | TopologyGraph — 2 타입, graph_view.py, BFS 경로 열거 + 영향 분석, ~80 테스트 |
| v2.3.0 (Phase 3) | Instance + Decision — 4 타입, instance_validator.py + decision_ledger.py, M0 검증 + 의사결정 원장, ~100 테스트 |
| v2.4.0 (Phase 4) | AI Decision Interface — 2 타입, ai_interface.py, 구조화된 컨텍스트 + 추천 + 설명, ~55 테스트 |
| v2.5.0 | 성능 최적화 (Breaking) — KernelSchema 인덱스, RuleCorpus judge 최적화, DecisionLedger mutable 전환, AI judgment 캐시, 타입 힌트 정리 |

### v1.9 Dead Rule Cleanup

v1.9에서 dead rule 분석을 통해 발견 및 정리:

- **old own-03** (`classifier*→feature*`, p60): `own-02` (`metatype*→feature*`, p60)에 완전 shadow됨 → **삭제**
- **old own-04** (`feature*→feature*`, p60, SAME_BRANCH): 동일하게 `own-02`에 shadow → **new own-03** (`feature*→feature*`, **p70**, SAME_BRANCH)으로 priority 승격
- **old own-05** → **new own-04** (renumber)

결과: 67 → 66 explicit rules, dead rules 2 → 0.

---

→ 장기 로드맵: `roadmap.md`

## 7. 검증 체계

```bash
cd packages/ea-kernel && PYTHONPATH=src python -m pytest tests/ -v
# 1064+ tests (graph_view tests ~9min due to exhaustive topology construction)
```

| 테스트 영역 | 파일 | 테스트 수 |
|------------|------|:-:|
| Kernel spec & validation | test_spec.py | ~200 |
| Kernel definition | test_definition.py | ~20 |
| TOML loader | test_spec_loader.py | ~30 |
| Profile types | test_profile_types.py | ~30 |
| Profile builder | test_profile_builder.py | ~40 |
| Profile loader | test_profile_loader.py | ~30 |
| Profile serializer | test_profile_serializer.py | ~20 |
| Profile store | test_profile_store.py | ~30 |
| Profile registry | test_profile_registry.py | ~30 |
| Profile diff | test_profile_diff.py | ~20 |
| Profile schema | test_profile_schema.py | ~20 |
| Profile query | test_profile_query.py | ~20 |
| Profile composer | test_profile_composer.py | ~20 |
| Quality gate | test_quality_gate.py | ~15 |
| Test harness | test_test_harness.py | ~10 |
| Framework profiles | test_{archimate,togaf,zachman,sysml2,bpmn}_profile.py | ~180 |
| Rule corpus | test_rule_corpus.py | ~51 |
| TypeDB schema | test_schema.py | ~30 |
| TopologyGraph (Phase 2) | test_graph_view.py | ~80 |
| InstanceValidator (Phase 3) | test_instance_validator.py | ~45 |
| DecisionLedger (Phase 3) | test_decision_ledger.py | ~55 |
| AIDecisionInterface (Phase 4) | test_ai_interface.py | ~55 |
