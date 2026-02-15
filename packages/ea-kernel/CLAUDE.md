# ea-kernel — Coding Conventions & Module Rules

경량 커널 메타모델. UML 2.5.1 구조 참고 + KerML 설계 철학 기반. Python >=3.11, core는 zero dependency.

## Design Philosophy

4-layer progressive abstraction:
- **L1 Structure**: 정적 구조 요소 (Element, Type, Feature, Classifier, ...)
- **L2 Relationship**: 구조적 연결 (Specialization, FeatureTyping, Connector, ...)
- **L3 Behavioral**: 관계의 행위 자격 부여 (Flow, Succession, Triggering, Transition, ...)
- **L4 Concrete**: 구체적 행위 모델 (Step, Action, State, Transition, Expression)

핵심 원칙: **행위는 구조와 별개가 아니라, 관계의 자격(qualification)**

## Kernel Schema

정규 스키마: `src/ea_kernel/specs/kernel_schema.toml` (20 attributes / 15 entities / 14 relations)

### 엔티티 상속 트리

```
element (root, abstract — uid/name/description/qualified_name/layer)
└── namespace (abstract — visibility, containment 능력)
    ├── metatype (abstract — is_abstract, KerML Type 대응)
    │   ├── feature (multiplicity/ordering/derived/composite/readonly)
    │   │   ├── port (접근/상호작용 지점)
    │   │   ├── step (L4 — succession 참여 행위 단위)
    │   │   │   └── action (L4 — 실행 가능 step)
    │   │   ├── event (L4 — 상태 변화 발생)
    │   │   └── expression (L4 — 평가 가능 값 계산)
    │   ├── classifier (abstract — 인스턴스화 가능)
    │   │   ├── structure (능동 — UML Class)
    │   │   ├── item (수동 — 데이터 객체)
    │   │   └── datatype (값 타입, 정체성 없음)
    │   └── state (L4 — 생명주기 상황 분류)
    └── package (구체 이름 공간 컨테이너)
```

### 릴레이션 분류

| 계층 | 관계 | 역할 |
|:-----|:-----|:-----|
| L2 구조 | membership | 이름 공간 소속 (container ↔ member) |
| | ownership | 구성적 소유, 생명주기 결합 (owner ↔ owned) |
| | specialization | metatype 상속 (supertype ↔ subtype) |
| | feature_typing | feature 타입 지정 (typed_feature ↔ typing) |
| | association | metatype 수준 구조적 연결 (source_end ↔ target_end) |
| | connector | feature 수준 링크, L3의 base (source ↔ target) |
| | redefinition | feature 완전 교체 (original ↔ redefining) |
| | subsetting | feature 값 범위 축소 (subsetted ↔ subsetting_feature) |
| L3 행위 | flow | 데이터/객체 흐름 (← connector) |
| | succession | 시간적 선후관계 (← connector) |
| | interaction | 메시지 교환 (← connector) |
| | triggering | 이벤트 → 행위 인과 (독립) |
| | guarding | 조건 가드 (독립) |
| | transition | 상태 전이 (독립) |

### 핵심 설계 결정

1. **feature가 metatype 하위인 이유**: KerML에서 "Feature is a Type". 피처 자체가 타입이므로 specialization에 참여할 수 있고, 자신의 값에 대한 타입을 정의할 수 있다. metatype의 분류 능력을 그대로 상속.

2. **L3 행위 관계가 connector를 상속하는 이유**: flow/succession/interaction은 본질적으로 "두 feature를 잇는 링크"에 시간/데이터/메시지 의미론을 추가한 것. connector의 source/target 역할 구조를 재사용하여 중복 방지. "행위는 관계의 자격(qualification)"이라는 원칙의 구현.

3. **state가 metatype 직접 하위인 이유**: state는 생명주기 내 상황을 분류하는 타입(specialization 참여 가능)이지만, classifier처럼 인스턴스를 직접 생성하지 않는다. transition/guarding을 통한 행위 모델링이 목적이므로 classifier의 인스턴스화 의미론은 배제.

### Validity Rule 구조

정규 규칙: `src/ea_kernel/specs/kernel_rules.toml`

- **67 explicit rules** + **14 fallback deny-by-default** (각 relation당 1개) = **81 total**
- **2 layer constraints** (L4↔L4 association/connector 제한)
- Priority 체계: `1` (fallback deny) → `40-50` (metatype-level allow) → `60` (structural pattern) → `70` (behavioral pattern) → `80-90` (explicit prohibition, override)
- 조건 시스템: `LAYER_ORDER` (source layer ≤ target layer), `SAME_BRANCH` (동일 상속 분기)
- 각 규칙에 metadata 포함: domain, tags, category, confidence, source, rationale

## Profile Design Principles

→ `src/ea_kernel/docs/profile_design.md` 참조

핵심 요약:
- 2-Stage Validation: profile rules → kernel rules (프로파일은 커널 위에 제약만 추가)
- 11/11 커널 타입이 5개 프레임워크(ArchiMate, TOGAF, Zachman, SysML2, BPMN) 완전 매핑
- Package Exposure Pattern: package-typed 요소는 port를 통해 외부 연결 (직접 association 금지)
- Profile Framework: flat 구조, 프로파일 생성(Builder/TOML) + 수명주기(직렬화/영속화/레지스트리/diff/쿼리/합성)

## Module Structure (flat)

```
src/ea_kernel/
├── types.py              # L1-L4 커널 타입 + Rule Corpus + Graph/Instance/AI 타입
├── definition.py         # 커널 정의/규칙
├── spec.py               # 스펙 정의
├── spec_loader.py        # 스펙 로더 + 메타데이터 파싱
├── rule_corpus.py        # 규칙 코퍼스 — 메타데이터·쿼리·증거 기반 판단
├── graph_view.py         # 토폴로지 그래프 탐색 + 경로 열거 (Phase 2)
├── instance_validator.py # M0 인스턴스 적합성 검증 (Phase 3)
├── decision_ledger.py    # 의사결정 기록 + 패턴 탐지 (Phase 3)
├── ai_interface.py       # AI 에이전트 의사결정 인터페이스 (Phase 4)
├── kernel_service.py     # 서비스 계층 — 7개 온보딩 함수 (UC1-UC5)
├── mcp_server.py         # MCP 서버 — 7개 도구 + instructions
├── profile_types.py      # Profile 타입 정의
├── profile_builder.py    # Profile 빌더 + build_with_corpus()
├── profile_loader.py     # TOML 로더
├── profile_quality_gate.py # 품질 게이트
├── profile_serializer.py # 직렬화
├── profile_store.py      # 영속화
├── profile_registry.py   # 레지스트리
├── profile_diff.py       # diff/비교
├── profile_schema.py     # 스키마 검증
├── profile_query.py      # 쿼리
├── profile_composer.py   # 프로파일 합성
├── profile_auditor.py    # 프로파일 감사
├── profile_backup.py     # 프로파일 백업/복원
├── rule_verifier.py      # 규칙 검증
├── test_harness.py       # 테스트 하네스
└── profiles/             # 5개 프레임워크 프로파일
    ├── archimate.py
    ├── togaf.py
    ├── zachman.py
    ├── sysml2.py
    └── bpmn.py
```

## Import Convention

**절대 경로 중심**.

```python
from ea_kernel.types import KernelEntity, KernelRelation
from ea_kernel.profile_types import ProfileDef, RuleDef
```

## Typing Convention

- Python 3.11+ 현대 문법: `list[]`, `dict[]`, `str | None`

## Module Rules

### File Size

목표 700줄, 경고 1000줄, 강제분할 1500줄. Schema data 파일 예외.

### Dependency Direction

```
types.py ← definition.py, spec.py
         ← rule_corpus.py (types만 import)
         ← graph_view.py (types + spec lazy import)
         ← instance_validator.py (types만 import)
         ← decision_ledger.py (types만 import)
         ← ai_interface.py (types + 위 모듈 lazy import)
         ← kernel_service.py (types + 위 모듈 lazy import)

kernel_service.py ← mcp_server.py (도구 함수 내부에서 lazy import)

types.py + rule_corpus.py ← profile_builder.py (build_with_corpus에서 lazy import)

profile_types.py ← profile_builder.py ← profile_loader.py
                 ← profile_quality_gate.py
                 ← profile_auditor.py
                 ← profile_backup.py
                 ← test_harness.py
                 ← profile_serializer.py
                 ← profile_store.py ← profile_registry.py
                 ← profile_diff.py
                 ← profile_schema.py
                 ← profile_query.py
                 ← profile_composer.py

rule_corpus.py ← rule_verifier.py
```

Profile 모듈은 types.py에 의존하지만, types.py/definition.py는 Profile 모듈을 모른다.
rule_corpus.py는 types.py만 import. profile_builder.py는 build_with_corpus() 내부에서 lazy import.
kernel_service.py는 순수 함수로 구조화된 dict 반환, mcp_server.py는 이를 JSON으로 래핑.

### Test Convention

- 절대 경로 import
- self-contained 테스트 파일
- TypeDB 의존 테스트: `@pytest.mark.typedb`
