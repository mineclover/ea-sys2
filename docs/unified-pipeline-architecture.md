# 통합 파이프라인 아키텍처

> Kernel 레퍼런스 구현 기반, 전 레이어 적용 공통 규격

## 1. 파이프라인 개요

모든 레이어는 동일한 5단계 파이프라인을 따라 **TOML 선언 → Python 타입 → 런타임 판정**을 수행한다. Kernel이 이 파이프라인의 레퍼런스 구현이며, 나머지 레이어는 동일 구조를 자기 도메인에 적용한다.

```
Stage 1: TOML 선언 (Meta-Meta Model)
  ↓ load_{layer}_schema()
Stage 2: 로더 + Frozen Types
  ↓ build() + _validate()
Stage 3: 패턴 컴파일 + 조건 레지스트리
  ↓ @Category/#Layer → 구체 규칙 확장
Stage 4: 자산 거버넌스 (라이프사이클)
  ↓ DRAFT → REVIEW → APPROVED → DEPRECATED
Stage 5: 카탈로그/코퍼스 합성
  ↓ 충돌 해소, 폴백 통합, 커버리지 검증
```

**각 단계의 산출물**:

| Stage | 입력 | 산출물 | 검증 |
|-------|------|--------|------|
| 1 | TOML 파일 | 원시 dict (tomllib) | `[meta]` 카운트 self-verification |
| 2 | 원시 dict | `{Layer}Schema` frozen 타입 | 구조 무결성 (필수 필드, 타입) |
| 3 | Schema + Profile | 확장된 규칙 목록 | 패턴 확장 통계, 데드 규칙 탐지 |
| 4 | 규칙 자산 | `RuleAsset` with lifecycle | 상태 전이 유효성 |
| 5 | 다중 소스 자산 | 통합 카탈로그/코퍼스 | 충돌 해소, 커버리지 100% |

---

## 2. Stage 1: TOML 선언 (Meta-Meta Model)

### 2.1 스펙 TOML 구조

각 레이어는 `specs/` 디렉토리에 정규 TOML 스펙을 보관한다.

```
src/{package}/specs/
├── {layer}_schema.toml           # 정규 스키마 (엔티티/관계/속성)
├── {layer}_schema.{lang}.toml    # i18n 패치
└── {layer}_rules.toml            # 유효성 규칙 (해당 시)
```

**필수 구조 — `{layer}_schema.toml`**:

```toml
[meta]
kernel_version = "2.5.0"
total_entities = 15
total_relations = 14
total_attributes = 20    # 해당 시

[[entities]]
name = "EntityName"
layer = "L1"              # 레이어 고유 분류
parent = "ParentEntity"   # 선택: 상속
is_abstract = false
description = "..."

[[relations]]
name = "RelationName"
layer = "L2"
roles = [
  { name = "source_role", player = "EntityA" },
  { name = "target_role", player = "EntityB" },
]
description = "..."
```

**필수 구조 — `{layer}_rules.toml`**:

```toml
[meta]
kernel_version = "2.5.0"
total_rules = 81

[rules.rule_id]
source = "SourcePattern"
target = "TargetPattern"
relation = "relation_name"
valid = true
priority = 50
notes = "허용/금지 사유"

[rules.rule_id.metadata]
domain = "domain_name"
tags = ["tag1", "tag2"]
category = "structural"
confidence = "established"
source = "spec"
rationale = "..."
```

### 2.2 프로파일 TOML 구조

프로파일은 TOML 선언의 런타임 인스턴스다. Kernel 스키마 위에 도메인 요소와 규칙을 정의한다.

```toml
[profile]
name = "ProfileName"
version = "1.0.0"
kernel_version = "2.5.0"
id_prefix = "prefix"
standard = "Standard Name"
organization = "org"

[categories]
Composite = "package"
ActiveStructure = "structure"
Interface = "port"
# ... 카테고리 → 커널 타입 매핑

[[elements]]
name = "ElementName"
layer = "LayerName"
category = "CategoryName"
description = "..."

[[relations]]
name = "relation_name"
kernel_relation = "kernel_relation_type"
description = "..."

[[rules]]
source = "SourcePattern"
target = "TargetPattern"
relation = "relation_name"
valid = true
priority = 60
```

### 2.3 Self-Verification 패턴

모든 스펙 TOML은 `[meta]` 섹션에 집계 메타데이터를 포함한다. 로더가 파싱 후 실제 카운트와 비교하여 불일치 시 `SchemaLoadError`를 발생시킨다.

```python
# schema_loader.py — self-verification 패턴
expected = meta.get("total_entities")
if expected is not None and len(entities) != expected:
    raise SchemaLoadError(
        f"Expected {expected} entities, got {len(entities)}"
    )
```

### 2.4 EA-Sys 프로파일 (7개 프로파일)

`packages/ea-kernel/src/ea_kernel/profiles/ea_sys/` 디렉토리에 7개 레이어 프로파일이 존재한다. 6개 EA-sys 레이어 + 1개 시각화 레이어. 모든 프로파일은 공통 관계 세트(10개)와 카테고리 매핑(12개)을 공유한다.

```
00-infra.toml           # Infra — row 데이터 설계
10-governance.toml      # Governance — 5개 레이어 관리 시스템
20-decision.toml        # Decision — 의사결정 메타-메타 모델
30-needs.toml           # Needs — 요구 모델 정의
40-kernel.toml          # Kernel — 도메인 핵심 모델
50-flow.toml            # Flow — 실행/데이터 흐름 모델
60-web-kernel-viz.toml  # Web Kernel Viz — 시각화 레이어
```

**공통 관계 (10개)**:

| 관계 | 커널 매핑 | 의미 |
|------|----------|------|
| `contains` | ownership | 네임스페이스/컴포넌트 포함 |
| `registers` | membership | 레지스트리 등록 |
| `coordinates` | association | 런타임 조율 |
| `depends_on` | association | 구조적 의존 |
| `produces` | flow (out) | 산출물 생산 |
| `consumes` | flow (in) | 입력 소비 |
| `next` | succession | 실행 순서 |
| `triggers` | triggering | 이벤트 트리거 |
| `constrains` | association | 정책/가드 제약 |
| `available_in` | association | 컨텍스트 접근 |

---

## 3. Stage 2: 로더 + Frozen Types

### 3.1 Schema 로더 함수

각 레이어는 순수 파싱 함수로 TOML → Frozen Schema를 생성한다.

```python
def load_{layer}_schema(path: Path | None = None) -> {Layer}Schema:
    """TOML 스펙을 파싱하여 불변 스키마 타입을 반환한다."""
    path = path or (SPECS_DIR / "{layer}_schema.toml")
    raw = tomllib.loads(path.read_bytes().decode())
    # parse + self-verify + return typed schema
```

**Kernel 레퍼런스** — `schema_loader.py`:
- `load_kernel_schema()` → `(version, KernelSchema, attributes, l1_entities, l2_relations, l3_relations, l4_entities)`
- Self-verification: `[meta]` 카운트 vs 실제 파싱 결과

### 3.2 Frozen Schema 타입

모든 Schema 타입은 SchemaPort 프로토콜을 준수한다.

```python
@dataclass(frozen=True)
class {Layer}Schema:
    """레이어 스키마 정의 — 불변."""
    entities: tuple[{Layer}Entity, ...]
    relations: tuple[{Layer}Relation, ...]

    def get_entity(self, name: str) -> {Layer}Entity | None: ...
    def get_relation(self, name: str) -> {Layer}Relation | None: ...
```

**핵심 인터페이스 요구사항**:
- `entities` — 전체 엔티티 목록 (tuple)
- `relations` — 전체 릴레이션 목록 (tuple)
- `get_entity(name)` — 이름으로 엔티티 조회
- `get_relation(name)` — 이름으로 릴레이션 조회

**Kernel 레퍼런스 — 확장 인터페이스**:
- `entities_in_layer(layer)` — 레이어별 엔티티 필터
- `relations_in_layer(layer)` — 레이어별 릴레이션 필터
- `validate_relationship(source, target, relation)` — 유효성 판정
- `effective_roles(relation_name)` — 상속 포함 역할 합산

### 3.3 Frozen Entity/Relation 타입

```python
@dataclass(frozen=True)
class {Layer}Entity:
    name: str
    is_abstract: bool = False
    description: str = ""

@dataclass(frozen=True)
class {Layer}Relation:
    name: str
    description: str = ""
```

**Kernel 확장**: `KernelEntity`는 `layer`, `parent`, `owns`, `plays` 등 L1-L4 온톨로지 속성을 추가.

### 3.4 Vocabulary 타입 불변 원칙

모든 Vocabulary 타입은 `frozen=True`를 준수한다:
- 컬렉션은 `tuple`, `list` 금지 (frozen 호환)
- `__post_init__`은 O(1) 인덱스 캐싱에만 사용
- 상태 변경은 새 인스턴스 반환 (immutable transition)

---

## 4. Stage 3: 패턴 컴파일 + 조건 레지스트리

### 4.1 패턴 해석

프로파일 규칙의 `source`/`target` 필드는 4가지 패턴을 지원한다:

| 패턴 | 문법 | 의미 | 확장 결과 |
|------|------|------|----------|
| Category | `@CategoryName` | 해당 카테고리의 모든 요소 | N개 구체 규칙 |
| Layer | `#LayerName` | 해당 레이어의 모든 요소 | N개 구체 규칙 |
| Wildcard | `*` | 모든 요소 | 전체 요소 수만큼 |
| Literal | `ElementName` | 특정 요소 | 1개 (확장 없음) |

**Kernel 레퍼런스** — `profile_rule_compiler.py`:
```python
def compile_profile_rules_for_runtime(profile: KernelProfile) -> ProfileRuleCompilationResult:
    # @Category → profile 카테고리 내 요소 매핑
    # #Layer → profile 레이어 필터링
    # * → 전체 요소
    # 확장된 규칙에 __c{seq:04d} 접미사 ID 부여
```

### 4.2 조건 레지스트리 (ConditionRegistry)

각 레이어는 커널 기본 조건을 확장하여 도메인 특화 조건을 등록한다.

**커널 기본 조건 (5개)**:
- `SAME_LAYER` — 동일 레이어 소속
- `LAYER_ORDER` — source layer ≤ target layer
- `SAME_BRANCH` — 동일 상속 분기
- `ANCESTOR_OF` — 상속 관계
- `SAME_CATEGORY` — 동일 카테고리

**레이어별 확장 패턴**:

| 레이어 | 추가 조건 |
|--------|----------|
| Needs | `SAME_STATUS`, `SAME_PRIORITY`, `SAME_USE_CASE`, `SAME_STAKEHOLDER` |
| Governance | `SAME_LAYER`, `SAME_LIFECYCLE`, `SAME_POLICY_SCOPE`, `SAME_TRANSACTION` |
| Decision | (미구현 — 설계 필요) |
| Flow | (미구현 — 설계 필요) |
| Infra | (미구현 — 설계 필요) |

```python
def {layer}_condition_registry() -> ConditionRegistry:
    """커널 기본 + 레이어 특화 조건 레지스트리."""
    reg = ConditionRegistry.kernel_default()
    reg.register("LAYER_SPECIFIC_CONDITION", "handler_key")
    return reg
```

---

## 5. Stage 4: 자산 거버넌스 (라이프사이클)

### 5.1 상태 전이 모델

모든 레이어의 자산(규칙, 모델, 카탈로그)은 동일한 4-state 라이프사이클을 따른다.

```
DRAFT ──→ REVIEW ──→ APPROVED ──→ DEPRECATED
  ↑          │
  └──────────┘  (rejected → back to draft)
```

**Kernel 레퍼런스** — `governance_types.py`:
```python
class RuleLifecycleState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"

VALID_TRANSITIONS = {
    DRAFT: (REVIEW,),
    REVIEW: (APPROVED, DRAFT),
    APPROVED: (DEPRECATED,),
    DEPRECATED: (),
}
```

### 5.2 불변 전이 원칙

상태 전이는 기존 인스턴스를 변경하지 않고 새 인스턴스를 반환한다.

```python
@dataclass(frozen=True)
class RuleLifecycle:
    current_state: RuleLifecycleState = RuleLifecycleState.DRAFT
    state_history: tuple[tuple[str, str, str, str, str], ...] = ()
    # 각 항목: (timestamp, from_state, to_state, actor, reason)

    def transition(self, to_state: RuleLifecycleState, actor: str, reason: str = "") -> RuleLifecycle:
        if not is_valid_transition(self.current_state, to_state):
            raise ValueError(f"Invalid transition: {self.current_state.value} → {to_state.value}")
        entry = (timestamp, self.current_state.value, to_state.value, actor, reason)
        return RuleLifecycle(current_state=to_state, state_history=(*self.state_history, entry))
```

### 5.3 Governance 연동 계약

- **RuleAsset**: 규칙 + 출처(Provenance) + 수명주기(Lifecycle) 번들
- **RuleProvenance**: 작성자, 소스 타입, 결정 참조, 타임스탬프
- **TransactionUnit**: 모든 상태 변경은 트랜잭션으로 감싸임 (PENDING → IN_PROGRESS → COMMITTED/ROLLED_BACK/FAILED)
- **TransactionEvent**: 불변 이벤트 소싱 — 모든 변경 이력 기록

---

## 6. Stage 5: 카탈로그/코퍼스 합성

### 6.1 Aggregate Root 패턴

각 레이어는 도메인 자산을 관리하는 Aggregate Root를 정의한다.

| 레이어 | Aggregate Root | 관리 자산 |
|--------|---------------|----------|
| Kernel | `RuleCorpus` | 규칙 코퍼스 (판정 + 증거 기반 진화) |
| Needs | `NeedCatalog` | 요구 카탈로그 (이해관계자 + 요구 + 관계) |
| Decision | `Topic` | 의사결정 토픽 (연구 + 옵션 + 보고서) |
| Flow | `ProcessSpec` | 프로세스 스펙 (단계 + 데이터 흐름) |
| Governance | `GovernanceContainer` | 퍼사드 (5개 레이어 통합 관리) |
| Infra | (미정의) | 저장소 계약 카탈로그 |

### 6.2 서비스 레이어 계약

서비스 함수는 순수 함수로 구현하며, JSON 직렬화 가능한 `dict[str, Any]`를 반환한다.

```python
def list_{domain}(*, lang: str | None = None) -> dict[str, Any]:
    """도메인 요소 목록 조회."""
    ...

def describe_{artifact}(*, artifact_id: str) -> dict[str, Any] | None:
    """개별 자산 상세 조회."""
    ...

def judge(*, source: str, target: str, relation: str) -> dict[str, Any]:
    """유효성 판정 (해당 시)."""
    ...
```

**규칙**:
- 모든 인자는 keyword-only (`*` 이후)
- 반환 타입은 `dict[str, Any]` (CLI/MCP/API 소비자 호환)
- 에러는 `{"error": "..."}` 딕셔너리로 반환 (예외 발생 금지, 추가 컨텍스트 키 포함 가능)
- Lazy init 헬퍼 (`_get_*` 패턴)로 무거운 초기화 지연

### 6.3 합성 규칙

다중 레이어 자산을 합성할 때:
- **ID 네임스페이싱**: `<layer>:<rule_id>` 접두사로 충돌 방지
- **폴백 규칙**: 관계당 정확히 1개 deny-by-default
- **우선순위 체계**: 1 (fallback) → 50 (metatype) → 70 (behavioral) → 90 (explicit)
- **결정적 합성**: 동일 조건의 합성 결과는 항상 동일

---

## 7. 현재 레이어별 파이프라인 달성도

### 갭 분석 매트릭스

| Stage | Kernel | Needs | Decision | Flow | Governance | Infra |
|-------|--------|-------|----------|------|------------|-------|
| **S1: TOML 스펙** | ✅ schema+rules | ❌ 미존재 | ❌ 미존재 | ❌ 미존재 | ❌ 미존재 | ❌ 미존재 |
| **S2: Schema 로더** | ✅ schema_loader | ✅ NeedsSchema | ❌ 미존재 | ❌ 미존재 | ✅ GovernanceSchema | ❌ 미존재 |
| **S3: 패턴 컴파일** | ✅ rule_compiler | ✅ condition_registry | ❌ 미존재 | ❌ 미존재 | ✅ condition_registry | ❌ 미존재 |
| **S4: 라이프사이클** | ✅ RuleAsset+Store | △ 상태 전이만 | ✅ DecisionLifecycle | ❌ 미존재 | ✅ TransactionManager | ❌ 미존재 |
| **S5: 카탈로그** | ✅ RuleCorpus | ✅ NeedCatalog | ✅ Topic aggregate | △ FlowRuntime | ✅ GovernanceContainer | ❌ 미존재 |
| **Profile 로딩** | ✅ TOML→Profile | ✅ profile_bridge | ❌ 미존재 | ❌ 미존재 | ✅ profile_bridge | ❌ 미존재 |
| **서비스 레이어** | ✅ kernel_service | ✅ needs_service | ❌ 미존재 | ❌ 미존재 | ✅ governance_service | ❌ 미존재 |

### 범례

- ✅ 완전 구현
- △ 부분 구현
- ❌ 미구현

### 우선순위별 갭 해소 순서

1. **Needs** — S1(TOML 외부화)만 부족, 나머지 파이프라인 완성도 높음
2. **Decision** — S2(Schema), S3(조건), S1(TOML) 순서로 보강
3. **Flow** — S1-S4 전체 필요, S5(런타임)는 부분 존재
4. **Governance** — S1(TOML 외부화) 필요, 나머지 완성도 높음
5. **Infra** — 전체 파이프라인 설계부터 필요

---

## 핵심 원칙 요약

1. **TOML은 source of truth** — Python 인라인 정의 → TOML 외부화
2. **모든 Schema는 SchemaPort 프로토콜 준수** — `entities`, `relations`, `get_entity()`, `get_relation()`
3. **모든 Vocabulary 타입은 `frozen=True`** — 불변성, 해시 가능, 비교 가능
4. **서비스 레이어는 순수 함수** — side-effect 없음, `dict[str, Any]` 반환
5. **검증은 계층적** — 빌드 시(구조) → 컴파일 시(패턴) → 런타임(판정)
6. **출처(Provenance)는 필수** — 모든 자산이 author, source_type, decision_ref 추적
7. **합성은 결정적** — `<layer>:` 접두사 네임스페이싱, 충돌 시 명시적 오류
