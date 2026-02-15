# ea-kernel — Coding Conventions & Module Rules

> **공통 구현 컨벤션**: `docs/ea-sys-conventions.md` 참조.
> 본 문서는 커널 고유 사항(L1-L4 온톨로지, 스키마 판정, 규칙 코퍼스)만 기술한다.

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

### 핵심 모듈 (Kernel core)

```
src/ea_kernel/
├── types.py              # L1-L4 커널 타입 + Rule Corpus + Graph/Instance/AI 타입
├── definition.py         # 커널 정의/규칙
├── spec.py               # 스펙 정의
├── spec_loader.py        # 스펙 로더 + 메타데이터 파싱
├── schema_loader.py      # TOML 스키마 파서 (specs/ → KernelSchema)
├── rule_corpus.py        # 규칙 코퍼스 — 메타데이터·쿼리·증거 기반 판단
├── profile_rule_compiler.py # @Category/#Layer → 구체 규칙 확장 (커널 런타임용)
├── profile_graph.py      # 프로파일 기반 토폴로지 그래프
├── graph_view.py         # 토폴로지 그래프 탐색 + 경로 열거 (Phase 2)
├── instance_validator.py # M0 인스턴스 적합성 검증 (Phase 3)
├── decision_ledger.py    # 의사결정 기록 + 패턴 탐지 (Phase 3)
├── ai_interface.py       # AI 에이전트 의사결정 인터페이스 (Phase 4)
├── kernel_service.py     # 서비스 계층 — 7개 온보딩 함수 (UC1-UC5)
├── mcp_server.py         # MCP 서버 — 7개 도구 + instructions
├── governance.py         # 거버넌스 관리
├── governance_types.py   # 거버넌스 타입 (RuleAsset, 수명주기)
├── lifecycle_controller.py # 수명주기 컨트롤러
├── i18n_store.py         # i18n 번역 저장소
├── localizer.py          # 프로파일 로컬라이저
├── rule_verifier.py      # 규칙 검증
└── test_harness.py       # 테스트 하네스
```

### Re-export shim 모듈 (ea_profile → ea_kernel 호환)

ea-profile로 추출된 모듈의 후방 호환 shim. 기존 `from ea_kernel.profile_*` import를 유지.

```
src/ea_kernel/
├── profile_types.py      # → ea_profile.types re-export
├── profile_builder.py    # → ea_profile.builder re-export + build_with_corpus() 확장
├── profile_loader.py     # → ea_profile.loader re-export
├── profile_quality_gate.py # → ea_profile.quality_gate re-export
├── profile_serializer.py # → ea_profile.serializer re-export
├── profile_store.py      # → ea_profile.store re-export
├── profile_registry.py   # → ea_profile.registry re-export
├── profile_diff.py       # → ea_profile.diff re-export
├── profile_schema.py     # → ea_profile.schema re-export
├── profile_query.py      # → ea_profile.query re-export
├── profile_composer.py   # → ea_profile.composer re-export
├── profile_auditor.py    # → ea_profile.auditor re-export
└── profile_backup.py     # 프로파일 백업/복원
```

> **Note**: `profile_builder.py`만 단순 re-export가 아님 — `build_with_corpus()`가 `ea_kernel.rule_corpus`와 `ea_kernel.types`에 의존하는 커널 전용 확장.

## Specs Convention

`specs/` 디렉토리는 커널 스키마와 규칙의 정규 TOML 정의를 보관한다.

```
src/ea_kernel/specs/
├── kernel_schema.toml      # 정규 스키마 — 엔티티/관계/속성 정의
├── kernel_schema.ko.toml   # i18n — 한국어 스키마 번역
└── kernel_rules.toml       # 정규 규칙 — 67 explicit + 14 fallback = 81 rules
```

- 네이밍: `kernel_{aspect}.toml`, i18n: `kernel_{aspect}.{lang}.toml`
- `[meta]` 섹션 필수: `kernel_version`, `total_entities`, `total_relations` 등 집계 메타데이터
- 파서: `schema_loader.py` (스키마 TOML → KernelSchema), `spec_loader.py` (스펙 TOML → 메타데이터)

## Profiles Convention

`profiles/` 디렉토리는 프레임워크 프로파일과 시스템 프로파일을 보관한다.

```
src/ea_kernel/profiles/
├── archimate.toml          # ArchiMate 3.2 프레임워크 프로파일
├── togaf.toml              # TOGAF 10
├── zachman.toml            # Zachman Framework
├── sysml2.toml             # SysML v2
├── bpmn.toml               # BPMN 2.0
├── system_self_model.toml  # 시스템 자기 모델
├── governance_lifecycle.toml
├── systemselfmodel.ko.patch.toml   # i18n patch
├── ea_sys/                 # EA-system 레이어 프로파일
│   ├── 00-infra.toml
│   ├── 10-governance.toml
│   ├── 20-decision.toml
│   ├── 30-needs.toml
│   ├── 40-kernel.toml
│   ├── 50-flow.toml
│   ├── 60-web-kernel-viz.toml
│   ├── easystem-infra.ko.patch.toml
│   ├── easystem-governance.ko.patch.toml
│   ├── easystem-decision.ko.patch.toml
│   ├── easystem-needs.ko.patch.toml
│   ├── easystem-kernel.ko.patch.toml
│   └── easystem-flow.ko.patch.toml
└── governance_profile_stack/
    ├── 00-governance-meta-model.toml
    └── 20-external-governance.toml
```

- 넘버링: `{NN}-{name}.toml` — NN은 레이어 정렬 순서 (00 infra, 10 governance, 20 decision, ...)
- i18n patches: `easystem-{layer}.ko.patch.toml` — description/display_name 필드만 오버라이드
- TOML 포맷 상세 → `packages/ea-profile/CLAUDE.md` 참조

## Import Convention

공통 import 규율은 `docs/ea-sys-conventions.md` §9 참조. 커널 고유 예시:

```python
# Kernel core
from ea_kernel.types import KernelEntity, KernelRelation, KernelSchema

# Profile (권장: ea_profile 직접 import)
from ea_profile.types import KernelProfile, ProfileRule, ProfileElement
from ea_profile.builder import ProfileBuilder

# Profile (후방 호환 via shim)
from ea_kernel.profile_types import KernelProfile, ProfileRule
from ea_kernel.profile_builder import ProfileBuilder
```

## Typing / File Size

공통: `docs/ea-sys-conventions.md` §1.5, §10.2, §10.3 참조. Schema data 파일 예외.

## Module Rules

### Dependency Direction

**외부 의존**: ea-kernel은 `ea-profile`을 pyproject.toml에서 의존한다. profile_*.py shim 모듈이 ea_profile을 re-export.

```
[Kernel core]
types.py ← definition.py, spec.py
         ← rule_corpus.py (types만 import)
         ← graph_view.py (types + spec lazy import)
         ← instance_validator.py (types만 import)
         ← decision_ledger.py (types만 import)
         ← ai_interface.py (types + 위 모듈 lazy import)
         ← kernel_service.py (types + 위 모듈 lazy import)

kernel_service.py ← mcp_server.py (도구 함수 내부에서 lazy import)

[Kernel ← ea_profile]
types.py + rule_corpus.py ← profile_builder.py (shim: build_with_corpus에서 lazy import)
profile_rule_compiler.py ← ea_kernel.types + ea_kernel.profile_types (shim)

rule_corpus.py ← rule_verifier.py
```

- profile_*.py shim 모듈은 ea_profile 대응 모듈을 단순 re-export (profile_builder.py 제외).
- profile_builder.py shim만 `build_with_corpus()` 확장을 보유 (ea_kernel.rule_corpus + ea_kernel.types 의존).
- types.py/definition.py는 ea_profile을 모른다 (역방향 의존 금지).
- kernel_service.py는 순수 함수로 구조화된 dict 반환, mcp_server.py는 이를 JSON으로 래핑.

### Test Convention

공통: `docs/ea-sys-conventions.md` §8 참조. 커널 전용:
- TypeDB 의존 테스트: `@pytest.mark.typedb`

## Kernel-Specific Patterns

공통 컨벤션(`docs/ea-sys-conventions.md`)에 더해 커널만 적용하는 패턴:

### L1-L4 Layer 추상화
- `Layer(StrEnum)`: L1/L2/L3/L4 고정 (다른 레이어는 자체 분류 사용)
- `KernelSchema.__post_init__`: 엔티티/관계/규칙 O(1) 인덱스 구축
- `effective_plays()`: 상속 트리 탐색으로 엔티티 역할 합산

### KernelValidityRule (ProfileRule 확장)
- ProfileRule의 커널 전용 서브클래스
- KernelConditionType 바인딩 (SAME_LAYER, LAYER_ORDER, ANCESTOR_OF, SAME_BRANCH)
- LayerConstraint: L4↔L4 제한 등 레이어 수준 사전 검증

### Rule Corpus / Evidence-Based Judgment
- RuleCorpus.from_kernel_spec(): 팩토리 메서드
- judge() → JudgmentReport: 증거 목록 + 승자 규칙 + confidence
- RuleMetadata 자동 추론 (관계 계층 → 도메인 분류)

### Profile Rule Compiler
- @Category/#Layer → 커널 엔티티명으로 확장
- 확장된 규칙에 __c{seq} 접미사 ID 부여
- ProfileRuleCompilationStats로 확장 통계 추적
