# ea-sys 공통 구현 컨벤션

> 본 문서는 모든 ea-* 패키지(kernel, needs, decision, flow, governance, infra)가 따르는 구현 표준이다.
> ea-kernel에서 검증된 패턴을 정규화한 것이며, 새 레이어 구현 시 이 문서를 권위 출처(source of truth)로 참조한다.
>
> 번역(M1/M2) 및 번역 API 요청 규약은 `docs/i18n-m1-m2-api-standard.md`를 함께 참조한다.
> M1 표현 계층(Projection Layer, M1P) 규약은 `docs/projection-layer-standard.md`를 함께 참조한다.

### Rule Ownership 규약 (필수)

- 모든 rule은 반드시 **소속 프로파일**과 **소속 레이어**를 함께 노출해야 한다.
  - M2 rule: `profile_name`, `profile_layer_key`, `profile_rule_id`, `profile_rule_identifier`
- M2 digest identifier(`m2::{layer}::rule::{digest}`)는 조회 키이고, 의미적 소유권은 `profile_rule_identifier`가 담당한다.
- M1 edge는 rule provenance 대신 `edge_origin`(`explicit|expanded|mixed`)과 `explicit_count`, `expanded_count`를 제공한다.
- M1 edge는 의미 노출을 위해 `semantic_axis`, `semantic_intent`, `surface_exposed`를 함께 제공한다.
- semantic 분류는 global 기본 사전을 가지며, `kernel|infra|needs`는 레이어 override를 우선 적용한다.
- 프로파일 단위 탐색 시 domain 표현은 `domain_scope=all|owned|bridge`를 표준으로 사용한다.
- 프로파일 단위 탐색에서 표층 관계만 확인할 때는 `surface_only=true`를 사용한다.
  - 적용 대상: `GET /profiles/{name}/topology`, `GET /profiles/{name}/composed`
  - 의미: 상속/메타/자기설명 관계를 기본 렌즈에서 제외하고 구조/인과 중심 관계를 우선 노출

---

## 1. 타입 시스템

### 1.1 Frozen Dataclass

모든 도메인 타입은 `@dataclass(frozen=True)`로 정의한다. 불변성은 해시 안전, 동시성 안전, 디버그 추적 용이를 보장한다.

```python
@dataclass(frozen=True)
class LayerEntity:
    name: str
    layer: str
    parent: str | None = None
```

안티패턴:

```python
# ❌ frozen 누락 — 의도치 않은 변경 허용
@dataclass
class MutableEntity:
    name: str
```

### 1.2 Collection은 tuple

가변 컬렉션(`list`)은 frozen dataclass의 불변 보장을 깨뜨린다. 모든 컬렉션 필드는 `tuple`을 사용한다.

```python
@dataclass(frozen=True)
class KernelEntity:
    name: str
    owns: tuple[str, ...] = ()          # ✅ tuple
    plays: tuple[str, ...] = ()         # ✅ tuple
```

안티패턴:

```python
# ❌ list 사용, mutable default
@dataclass(frozen=True)
class BadEntity:
    items: list[str] = []
```

### 1.3 __post_init__ 인덱싱 캐시

frozen dataclass에서 O(1) 조회가 필요할 때, `__post_init__`에서 `object.__setattr__`로 캐시 dict를 구축한다. 캐시 필드는 `init=False, repr=False, compare=False`로 선언하여 생성자/비교/출력에서 제외한다.

```python
@dataclass(frozen=True)
class KernelSchema:
    entities: tuple[KernelEntity, ...]
    relations: tuple[KernelRelation, ...]
    _entity_by_name: dict[str, KernelEntity] = field(
        default_factory=dict, init=False, repr=False, compare=False,
    )

    def __post_init__(self) -> None:
        entity_idx: dict[str, KernelEntity] = {}
        for e in self.entities:
            entity_idx[e.name] = e
        object.__setattr__(self, '_entity_by_name', entity_idx)
```

### 1.4 I18nString

다국어 지원이 필요한 문자열 필드는 `I18nString` 타입 별칭을 사용한다.

```python
I18nString = str | dict[str, str]

@dataclass(frozen=True)
class KernelEntity:
    description: I18nString = ""
    display_name: I18nString = ""
```

- 단일 언어: `str` 그대로
- 다국어: `{"en": "Element", "ko": "요소"}`

### 1.5 StrEnum

상태, 분류, 조건 타입 등 유한 값 집합은 `StrEnum`으로 정의한다. 문자열 직렬화가 자동으로 보장된다.

```python
from enum import StrEnum

class Layer(StrEnum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"

class RuleLifecycleState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
```

---

## 2. Design-First Pipeline

### 2.1 5단계 개요

모든 레이어가 동일한 "TOML 선언 → 런타임 판정" 파이프라인을 따른다.

```
Stage 1: 선언 (TOML)         — specs/ 디렉토리에 스키마/규칙 선언
  ↓ loader.py
Stage 2: 파싱 (Builder)       — TOML → 불변 타입 변환
  ↓ build() + _validate()
Stage 3: 패턴 컴파일          — @Category/#Layer → 구체 규칙 확장
  ↓
Stage 4: 자산 거버넌스         — DRAFT → REVIEW → APPROVED → DEPRECATED
  ↓
Stage 5: 카탈로그 합성         — 충돌 해소, 폴백 통합, 커버리지 검증
```

### 2.2 TOML 스펙 구조 (`specs/` 디렉토리)

각 레이어는 `specs/` 디렉토리에 정규 TOML 스펙을 보관한다.

```
src/{package}/specs/
├── {layer}_schema.toml           # 정규 스키마 (엔티티/관계/속성)
├── {layer}_schema.{lang}.toml    # i18n 패치
└── {layer}_rules.toml            # 유효성 규칙 (해당 시)
```

### 2.3 Self-Verification (TOML meta 카운트 검증)

모든 스펙 TOML은 `[meta]` 섹션에 집계 메타데이터를 포함한다. 로더가 파싱 후 실제 카운트와 비교하여 불일치 시 `LoadError`를 발생시킨다.

```toml
[meta]
kernel_version = "0.7.0"
total_attributes = 20
total_entities = 15
total_relations = 14
```

```python
# schema_loader.py — self-verification 패턴
expected_attrs = meta.get("total_attributes")
if expected_attrs is not None and len(attributes) != expected_attrs:
    raise SchemaLoadError(
        f"Expected {expected_attrs} attributes, got {len(attributes)}"
    )
```

### 2.4 Schema Loader 패턴

스키마 로더는 순수 파싱 함수로 구현한다. 예외는 커스텀 `LoadError`로 래핑한다.

```python
class SchemaLoadError(Exception):
    """Raised when a schema TOML file cannot be parsed or validated."""

def load_layer_schema(path: Path | None = None) -> LayerSchema:
    path = path or (SPECS_DIR / "layer_schema.toml")
    try:
        raw = path.read_bytes()
    except FileNotFoundError as err:
        raise SchemaLoadError(f"Schema file not found: {path}") from err
    doc = tomllib.loads(raw.decode())
    # ... parse + self-verify + return typed schema
```

### 2.5 M1 파이프라인 3모듈 패턴

M2(메타모델)는 레이어별 단일 시스템(`{layer}_schema.py`)으로 정의되지만, M1(프로파일)부터는 `ea-profile` 공통 인터페이스를 통해 profile 단위로 관리된다. 모든 레이어는 M2 → M0 파이프라인을 제공하기 위해 다음 3모듈을 반드시 구현한다.

각 레이어의 M2 설계(엔티티/관계 어휘)는 목적에 따라 다르고, M1·M0의 적재 방식이나 도메인 개념도 레이어마다 다르다. 그러나 프로파일 접근의 공통 인터페이스는 `ea-profile` 패키지가 제공하므로, 3모듈의 구조적 패턴은 동일하다.

| 모듈 | 네이밍 규칙 | 역할 |
|------|-----------|------|
| `{layer}_schema.py` | `{Layer}Schema` 클래스 + `{LAYER}_SCHEMA` 싱글턴 | M2 스키마 (SchemaPort 호환) |
| `condition_registry.py` | `{layer}_condition_registry()` 팩토리 함수 | kernel defaults + 레이어 전용 조건 |
| `profile_bridge.py` | `load_{layer}_profile()` + `_from_content()` | TOML → KernelProfile 로딩 브릿지 |

**스키마 모듈** (`{layer}_schema.py`):

```python
# 독립 모듈 — 외부 의존 없음
@dataclass(frozen=True)
class LayerEntity:
    name: str
    is_abstract: bool = False
    description: str = ""

@dataclass(frozen=True)
class LayerRelation:
    name: str
    description: str = ""

@dataclass(frozen=True)
class LayerSchema:                    # SchemaPort 호환
    entities: tuple[LayerEntity, ...] = ()
    relations: tuple[LayerRelation, ...] = ()
    def get_entity(self, name: str) -> LayerEntity | None: ...
    def get_relation(self, name: str) -> LayerRelation | None: ...

LAYER_SCHEMA = LayerSchema(entities=(...), relations=(...))
```

**조건 레지스트리** (`condition_registry.py`):

```python
def layer_condition_registry():
    from ea_profile.types import ConditionRegistry
    reg = ConditionRegistry.kernel_default()  # 5 kernel defaults
    reg.register("SAME_DOMAIN_CONCEPT", "same_domain_concept")
    return reg
```

**프로파일 브릿지** (`profile_bridge.py`):

```python
from my_layer.condition_registry import layer_condition_registry
from my_layer.layer_schema import LAYER_SCHEMA

def load_layer_profile(path: Path, *, validate: bool = True):
    from ea_profile.loader import load_profile
    schema = LAYER_SCHEMA if validate else None
    return load_profile(path, kernel=schema, condition_registry=layer_condition_registry())

def load_layer_profile_from_content(content: str, *, validate: bool = True):
    from ea_profile.loader import load_profile_from_content
    schema = LAYER_SCHEMA if validate else None
    return load_profile_from_content(content, schema, layer_condition_registry())
```

### 2.6 Projection Policy (M1P) 규약

탐색/표현 정책은 다음 2단계로 분리한다.

- `M2(계약)`: 정책 필드/타입/허용값 정의
- `M1(값)`: 레이어별 탐색 정책 값(관계 allow-list, 카테고리, edge budget)

표준 정책 파일:

`packages/ea-kernel/src/ea_kernel/profiles/ea_sys/projection_policy.toml`

필수 구조:

- `[m2.schema]`, `[m2.schema.lens_to_level]`, `[m2.defaults]`
- `[m1.global.levels.<l0..l4>]`
- `[m1.layers.<layer_key>.levels.<l0..l4>]` (선택 override)

---

## 3. 서비스 레이어

### 3.1 순수 함수 + dict[str, Any] 반환

서비스 함수는 순수 함수(부작용 없음)로 구현하며, JSON 직렬화 가능한 `dict[str, Any]`를 반환한다. CLI, MCP, API 등 어떤 소비자도 동일하게 사용할 수 있다.

```python
def list_entities(*, lang: str | None = None) -> dict[str, Any]:
    """UC1: List all kernel entities grouped by layer."""
    spec = _get_localized_spec(lang)
    # ... build result dict
    return {"total": len(spec.entities), "layers": layers}
```

### 3.2 Keyword-only 인자

서비스 함수의 모든 인자는 keyword-only(`*` 이후)로 선언한다. 위치 인자 오용을 방지한다.

```python
def list_entities(*, lang: str | None = None) -> dict[str, Any]: ...
def describe_rule(*, rule_id: str, lang: str | None = None) -> dict[str, Any]: ...
def judge(*, source: str, target: str, relationship: str) -> dict[str, Any]: ...
```

### 3.3 에러 딕셔너리 (서비스 레벨)

서비스 레벨에서는 예외를 발생시키지 않고, 에러 정보를 딕셔너리로 반환한다. 소비자(CLI/MCP/API)가 에러 처리를 자유롭게 결정할 수 있다.

```python
def describe_rule(*, rule_id: str) -> dict[str, Any]:
    rule = corpus.get(rule_id)
    if rule is None:
        return {"error": f"Unknown rule: {rule_id}", "valid_rules": [...]}
    return {"id": rule.id, "description": rule.description, ...}
```

### 3.4 Lazy Init 헬퍼 (`_get_*` 패턴)

무거운 초기화(스펙 로딩, 코퍼스 빌드)는 모듈 레벨 `_get_*` 함수로 지연 로딩한다. 순환 import를 회피하고 필요할 때만 초기화한다.

```python
def _get_schema() -> LayerSchema:
    from my_layer.spec import LAYER_SCHEMA
    return LAYER_SCHEMA

def _get_corpus() -> RuleCorpus:
    from my_layer.rule_corpus import RuleCorpus
    from my_layer.spec import LAYER_SCHEMA
    return RuleCorpus.from_spec(LAYER_SCHEMA)
```

### 3.5 API Router 플러그인 패턴

레이어가 HTTP 엔드포인트를 제공할 때, 엔드포인트 정의는 해당 레이어 패키지 내부에 `api_router.py`로 작성한다. 서버(ea-kernel)는 `try/except ImportError`로 플러그인 방식으로 마운트한다. 이를 통해 역방향 의존(kernel → 하위 레이어) 없이 API를 확장할 수 있다.

**레이어 측** (`ea_governance/api_router.py`):

```python
from fastapi import APIRouter, HTTPException
from ea_governance.governance_service import list_managed_layers, ...

governance_router = APIRouter(prefix="/governance", tags=["governance"])

@governance_router.get("/layers")
def list_governance_layers() -> dict[str, Any]:
    return list_managed_layers()
```

**서버 측** (`ea_kernel/api/server.py`):

```python
try:
    from ea_governance.api_router import governance_router
    app.include_router(governance_router)
except ImportError:
    pass  # ea-governance not installed; endpoints disabled
```

레이어 패키지의 `pyproject.toml`에 `[project.optional-dependencies] api = ["fastapi>=0.100"]`를 선언하여 FastAPI 의존을 선택적으로 관리한다.

---

## 4. 에러 처리 전략

### 4.1 3계층: Parse(예외) → Validate(결과객체) → Service(에러딕셔너리)

| 계층 | 전략 | 예시 |
|------|------|------|
| TOML 파싱 | 커스텀 예외 즉시 발생 | `SchemaLoadError`, `ProfileLoadError` |
| 빌드/검증 | 에러 리스트 수집 → 일괄 발생 | `ProfileBuildError(errors: list[str])` |
| 서비스 | 에러 딕셔너리 반환 | `{"error": "...", "context": [...]}` |

### 4.2 에러 수집 후 일괄 발생 (fail-late)

빌드/검증 단계에서는 첫 에러에서 멈추지 않고 모든 에러를 수집한 뒤 일괄 보고한다.

```python
errors: list[str] = []
for rule in rules:
    if not is_valid(rule):
        errors.append(f"Invalid rule: {rule.id}")
if errors:
    raise ProfileBuildError(errors)
```

### 4.3 unknown 필드는 warnings.warn

TOML 파싱 시 알 수 없는 필드는 예외가 아니라 `warnings.warn`으로 경고만 발생시킨다. 전방 호환성을 보장한다.

---

## 5. Store 패턴

### 5.1 ABC 인터페이스 정의

각 저장소는 ABC로 인터페이스를 먼저 정의한다. 구현체(SQLite, InMemory)는 이를 상속한다.

```python
from abc import ABC, abstractmethod

class I18nStore(ABC):
    @abstractmethod
    def upsert(self, entry: TranslationEntry) -> TranslationEntry: ...
    @abstractmethod
    def get(self, kind: str, name: str, lang: str, field: str) -> TranslationEntry | None: ...
    @abstractmethod
    def list_translations(self, lang: str) -> tuple[TranslationEntry, ...]: ...
```

### 5.2 SQLite 구현 (contextmanager, __slots__, _init_schema)

SQLite 구현체는 다음 패턴을 따른다:
- `__slots__`로 메모리 절약
- `_init_schema()`로 테이블 자동 생성
- `@contextmanager`로 연결 관리

```python
class SQLiteI18nStore(I18nStore):
    __slots__ = ("_db_path",)

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._init_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS translations (...)
            """)
```

### 5.3 InMemory 구현 (테스트용)

테스트용 인메모리 구현체는 dict 기반으로 동일 ABC를 구현한다. 프로덕션 코드와 테스트가 동일 인터페이스로 동작함을 보장한다.

### 5.4 레이어별 특화 스토어

각 레이어는 자체 특화 스토어를 갖는다. 모든 레이어가 메타-메타 모델 기반으로 생성되는 프로파일을 지속 관리하며, 기본적인 버전 관리가 필요하기 때문이다.

- **커널**: ea-kernel(i18n_store, rule_asset_store, decision_store, corpus_version_store)
- **거버넌스**: ea-governance(layer_store, kernel_store, needs_store)
- **도메인 레이어**: ea-decision(topic_store), ea-needs(needs_store), ea-flow(execution_store)
- 원칙: Governance는 크로스 레이어 조율·이력 관리를 담당하되, 각 레이어의 도메인 영속화는 레이어 자체가 소유

---

## 6. Lifecycle / State Machine

### 6.1 StrEnum 상태 + VALID_TRANSITIONS dict

상태 머신의 상태는 `StrEnum`, 유효 전이는 `dict[State, tuple[State, ...]]`로 선언한다.

```python
class RuleLifecycleState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"

VALID_TRANSITIONS: dict[RuleLifecycleState, tuple[RuleLifecycleState, ...]] = {
    RuleLifecycleState.DRAFT: (RuleLifecycleState.REVIEW,),
    RuleLifecycleState.REVIEW: (RuleLifecycleState.APPROVED, RuleLifecycleState.DRAFT),
    RuleLifecycleState.APPROVED: (RuleLifecycleState.DEPRECATED,),
    RuleLifecycleState.DEPRECATED: (),
}

def is_valid_transition(from_state: RuleLifecycleState, to_state: RuleLifecycleState) -> bool:
    return to_state in VALID_TRANSITIONS.get(from_state, ())
```

### 6.2 불변 전이 (새 인스턴스 반환)

상태 전이는 기존 인스턴스를 변경하지 않고 새 인스턴스를 반환한다 (frozen dataclass 원칙).

```python
def transition(self, to: RuleLifecycleState, actor: str) -> RuleLifecycle:
    if not is_valid_transition(self.current, to):
        raise ValueError(f"Invalid transition: {self.current} → {to}")
    entry = LifecycleEntry(from_state=self.current, to_state=to, actor=actor, ...)
    return RuleLifecycle(current=to, history=(*self.history, entry))
```

### 6.3 이력 추적 (state_history tuple)

모든 전이 이력은 `tuple`로 누적하여 불변 감사 추적(audit trail)을 제공한다.

---

## 7. Event Bus

### 7.1 Subscribe in __init__

이벤트 구독은 컨트롤러의 `__init__`에서 수행한다. 구독/핸들러 관계를 생성 시점에 확정한다.

```python
class LifecycleController:
    def __init__(self, event_bus: LifecycleEventPort, ...) -> None:
        self.bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        self.bus.subscribe(TriggerEventType.RULE_SUBMITTED, self.on_rule_submitted)
        self.bus.subscribe(TriggerEventType.RULE_APPROVED, self.on_rule_approved)
        self.bus.subscribe(TriggerEventType.CORPUS_UPDATED, self.on_corpus_updated)
```

### 7.2 핸들러 메서드 (`on_*` 네이밍)

이벤트 핸들러는 `on_{event_name}` 네이밍 컨벤션을 따른다.

```python
def on_rule_submitted(self, event: LifecycleEvent) -> None:
    """Handle RULE_SUBMITTED: notify reviewers."""
    ...

def on_rule_approved(self, event: LifecycleEvent) -> None:
    """Handle RULE_APPROVED: update corpus."""
    ...
```

---

## 8. 테스트 컨벤션

### 8.1 클래스 기반 그루핑 (TestXxx)

관련 테스트를 `TestXxx` 클래스로 그루핑한다. 각 클래스는 하나의 기능/유스케이스를 다룬다.

```python
class TestListEntities:
    """UC1: list_entities()."""

    def test_returns_total_and_layers(self):
        result = list_entities()
        assert "total" in result
        assert "layers" in result

    def test_total_matches_sum_of_layers(self):
        result = list_entities()
        total_from_layers = sum(layer["count"] for layer in result["layers"])
        assert result["total"] == total_from_layers
```

### 8.2 팩토리 함수 (`_make_*` 패턴)

테스트 데이터 생성은 모듈 레벨 `_make_*` 팩토리 함수를 사용한다. 기본값을 제공하되 개별 필드 오버라이드를 허용한다.

```python
def _make_entry(
    kind: str = "entity",
    name: str = "element",
    lang: str = "ko",
    field: str = "display_name",
    value: str = "요소",
    en_source: str = "Element",
) -> TranslationEntry:
    return TranslationEntry(
        target_kind=kind, target_name=name, lang=lang,
        field=field, value=value, en_source=en_source,
        version=1, created_by="test", created_at="", updated_at="",
    )
```

### 8.3 tempfile.TemporaryDirectory (Store 테스트)

SQLite Store 테스트는 `tempfile.TemporaryDirectory`로 격리된 DB를 사용한다.

```python
import tempfile

class TestSQLiteStore:
    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteThingStore(Path(tmpdir) / "thing.db")
            store.upsert(entry)
            got = store.get(...)
            assert got is not None
```

### 8.4 Self-verification 테스트 (TOML meta 카운트)

TOML 스펙의 `[meta]` 카운트가 실제 파싱 결과와 일치하는지 검증하는 테스트를 포함한다.

```python
class TestLoadKernelSchema:
    def test_self_verification_counts(self):
        version, schema, attributes, *_ = load_kernel_schema()
        assert len(attributes) == 20
        assert len(schema.entities) == 15
        assert len(schema.relations) == 14
```

---

## 9. Import 규율

### 9.1 절대 경로 only

모든 import는 절대 경로를 사용한다. 상대 경로 import 금지.

```python
# ✅
from ea_kernel.types import KernelEntity, KernelSchema
from ea_profile.builder import ProfileBuilder

# ❌
from .types import KernelEntity
from ..profile.builder import ProfileBuilder
```

### 9.2 Lazy import (순환 회피)

순환 의존 위험이 있거나 무거운 모듈은 함수 내부에서 지연 import한다.

```python
def _get_corpus() -> RuleCorpus:
    from ea_kernel.rule_corpus import RuleCorpus
    from ea_kernel.spec import KERNEL_SPEC
    return RuleCorpus.from_kernel_spec(KERNEL_SPEC)
```

### 9.3 TYPE_CHECKING 블록

타입 힌트에만 필요한 import는 `TYPE_CHECKING` 블록에 넣어 런타임 순환을 방지한다.

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_kernel.rule_corpus import RuleCorpus
    from ea_kernel.evidence_analyzer import AnalysisReport
```

### 9.4 Import 순서

```python
from __future__ import annotations          # 1. __future__

import sqlite3                              # 2. stdlib
import tomllib
from abc import ABC, abstractmethod
from pathlib import Path

import pytest                               # 3. 3rd-party (있을 경우)

from ea_kernel.types import KernelSchema    # 4. local (절대 경로)
from ea_profile.builder import ProfileBuilder

if TYPE_CHECKING:                           # 5. TYPE_CHECKING
    from ea_kernel.rule_corpus import RuleCorpus
```

---

## 10. 파일/모듈 규칙

### 10.1 Flat 구조

패키지 내부는 flat 구조를 유지한다. 하위 디렉토리/서브패키지를 만들지 않는다.

```
src/ea_kernel/
├── types.py
├── schema_loader.py
├── kernel_service.py
└── ...                    # 모두 같은 레벨
```

### 10.2 파일 크기

| 기준 | 줄 수 |
|------|------|
| 목표 | 700줄 |
| 경고 | 1000줄 |
| 강제 분할 | 1500줄 |

Schema data 파일(순수 데이터 선언)은 예외.

### 10.3 Python 3.11+ 타입 문법

현대 타입 문법을 사용한다:

```python
# ✅ Python 3.11+
list[str]
dict[str, Any]
str | None
tuple[str, ...]

# ❌ Legacy
List[str]
Dict[str, Any]
Optional[str]
Tuple[str, ...]
```

---

## 11. M2 > M1 > M0 레이어 스택 표준

`kernel`을 기준 레퍼런스로 하되, **모든 레이어(`infra/governance/decision/needs/kernel/flow`)는 동일한 3단 구조**로 조회한다.

### 11.1 공통 조회 API

- `GET /layers/{layer_key}/m2?lang={lang}` (M2 전용)
- `GET /layers/{layer_key}/stack?lang={lang}&m0_limit={n}`
- `GET /profiles/{profile_name}/topology?lang={lang}&view_mode={raw|summary}&max_edges={n}` (M1 토폴로지)
- `GET /profiles/{profile_name}/composed?lang={lang}&domain_scope={all|owned|bridge}&max_edges={n}&focus={core|relation|layer|actor}` (M1 cross-profile 합성)
- `lang` 기본값: `en`
- `m0_limit` 기본값: `20` (`<=0` 금지)
- `view_mode` 기본값: `raw`
  - `raw`: rule-edge 원본
  - `summary`: `(source,target,relation)` 집약 edge (`rule_count`, `priority max`, `edge_origin` 포함)
  - `composed`: anchor profile 기준 다중 프로파일 합성 view (edge `edge_origin`, node `profile_owners` 포함)

레이어 키 규칙:

- 허용값: `infra|governance|decision|needs|kernel|flow`
- 스키마 UI 라우트(`/schema/:layerKey`)는 입력 layerKey를 정규화한다.
  - 소문자화, URL decode, 공백/쉼표/구두점 제거
  - 복합 문자열(예: `infra,`, `needs%20`)은 첫 유효 layer key로 해석
  - 유효하지 않으면 `kernel`로 폴백 후 리다이렉트

응답 표준 구조:

```json
{
  "layer_key": "infra",
  "profile_name": "EASystem-Infra",
  "version": "...",
  "lang": "ko",
  "m2": { "...": "layer schema payload" },
  "m1": { "...": "profile topology payload" },
  "m0": {
    "snapshot_total": 0,
    "snapshots": [],
    "model_candidate_total": 0,
    "model_candidates": []
  }
}
```

### 11.2 식별 체계 단일화

식별자는 **도메인별 native 식별 + 계층 공통 식별**을 함께 유지한다.

- Layer M2 object 식별자 (API payload):
  - `element`: `m2::{layer_key}::element::{name}`
  - `relation`: `m2::{layer_key}::relation::{name}`
  - `category`: `m2::{layer_key}::category::{name}`
  - `rule`: `m2::{layer_key}::rule::{sha1(source|relation|target|valid|priority)[:12]}`
- Kernel native 식별자:
  - `entity_id = entity.name`
  - `relation_id = relation.name`
  - `rule_id = rule.id` (rule corpus 원본 식별자)
- 번역 슬롯 식별자(패치/감사)는 별도 규약 사용:
  - M2: `m2:{kind}:{name}:{field}`
  - M1: `m1:{profile}:{kind}:{name}:{field}`

규칙:

- `layer_key`: `infra|governance|decision|needs|kernel|flow`
- `kind`: `element|relation|category|rule|node|edge|model|snapshot`
- `field`: 번역/동기화 대상 필드(`display_name`, `description` 등)
- Layer M2 object 식별자는 구분자 `::`를 사용하고, 번역 슬롯 식별자는 구분자 `:`를 사용한다.

Flow start-condition 식별자(패치/영향 분석):

- 패턴: `start::{workflow_or_*}::{source_or___entry__}->{target}::{kind}[:{source_field}>{target_field}]`
- `kind`: `control_edge|data_edge|event_trigger`
- `source`가 없으면 `__entry__`를 사용한다.
- `workflow`가 전역이면 `*`를 사용한다.
- 해당 식별자는 `ea_flow.flow_simulator.StartConditionSpec.identifier` 계산식과 동일해야 한다.

### 11.3 lang 파라미터 컨벤션

모든 번역 가능 조회 API는 `lang` 단일 파라미터를 사용한다.

- 허용값: `en`, `ko` (확장 가능)
- 미지정 시 `en`
- 서버는 `lang` 기준으로 M2/M1 로컬라이즈 결과를 구성하고, M0는 원문 데이터(스냅샷/모델 메타)를 반환한다.

### 11.4 작업 컨벤션: 식별 계산 시스템 노출 우선

정합성 검증과 언어 패치 안정성을 위해, 설계 설명은 추상 용어보다 **실제 계산식**을 우선 노출한다.

- MUST: API 응답에 식별자 계산 계약(`identifier_system` 등)을 포함한다.
- MUST: UI는 식별자 예시가 아니라 계산 패턴(문자열 템플릿/해시 입력식)을 그대로 표시한다.
- MUST: rule 식별자는 해시 알고리즘/입력 템플릿/잘림 길이를 명시한다.
- SHOULD: 시스템별 native 식별자(`entity.name`, `rule.id` 등)와 layer 공통 식별자를 함께 노출한다.
- MUST NOT: `semantic/behavior/runtime` 같은 표현을 식별 계산 계약보다 우선 규약으로 사용하지 않는다.

검증 체크리스트:

- `/kernel/entities`, `/kernel/relations`, `/kernel/rules`가 canonical kernel M2를 반환하는가
- `/layers/{layer_key}/m2`가 `identifier_system`과 object identifiers를 반환하는가
- `/profiles/{name}/topology`가 `view_mode`, `edge_total_raw`, `edge_total_before_cap`, `edge_truncated`를 반환하는가
- `/schema/kernel`와 `/schema/{non-kernel}` 화면에서 식별 계산 규칙이 시각적으로 노출되는가

### 11.5 스키마 UI 노출 규칙

M2 화면은 레이어별 native 설계를 보존하면서, 계산 규칙을 직접 노출한다.

- `/schema/kernel`:
  - `FlowGraph`를 사용한다.
  - 데이터 소스: `/kernel/entities`, `/kernel/relations`, `/kernel/rules`
  - 식별 규칙은 kernel native(`entity.name`, `relation.name`, `rule.id`)를 노출한다.
- `/schema/infra`, `/schema/needs`:
  - `LayerSchemaView` 기본 모드를 `blueprint`로 사용한다.
  - `identifier_system` 계산식과 `m2_blueprint.layer_responsibilities`를 패널에 노출한다.
- `/schema/{decision|governance|flow}`:
  - `LayerSchemaView` 기본 모드는 `elements`이며, 필요 시 `blueprint` 전환을 제공한다.

### 11.6 Needs API 완성도 규칙

Needs 레이어는 단순 조회가 아니라, M2 설계를 따라 모델링 변경(write)도 API로 완결되어야 한다.

- 필수 write endpoint:
  - `POST /needs/catalogs/{catalog_id}/use-cases`
  - `POST /needs/catalogs/{catalog_id}/needs`
  - `POST /needs/catalogs/{catalog_id}/needs/{need_id}/revise`
  - `POST /needs/catalogs/{catalog_id}/needs/{need_id}/process-units`
  - `POST /needs/catalogs/{catalog_id}/needs/{need_id}/inherit-decision-evidence`
- `priority`, `purpose`, `complexity`, `cause_types`는 도메인 canonical 값으로 정규화되어야 한다.
- `GET /needs/catalogs/{catalog_id}/needs`는 최소 아래 필드를 포함해야 한다.
  - `purpose`, `cause_types`, `complexity`, `use_case_id`

### 11.7 M1 품질 가드레일 표준

`/schema/{layer}`의 M1 뷰는 `raw`/`summary`/`focus`를 지원하되, `summary`를 기본으로 하고 품질 진단을 함께 노출한다.

- 진단 지표:
  - dominant relation share
  - relation kind count
  - cross-layer edge share
  - API/UI edge cap 여부
- 품질 상태:
  - `healthy` | `attention` | `critical`
- 공통 기본 임계치:
  - summary: `dominant <= 40%`, `relation kinds >= 4`, `cross-layer <= 55%`
  - focus: `dominant <= 42%`, `relation kinds >= 3`, `cross-layer <= 60%`
  - raw: `dominant <= 55%`, `relation kinds >= 5`, `cross-layer <= 70%`
- 레이어별 허용 편차:
  - `kernel`은 dominant/cross 허용치를 더 낮게 둔다.
  - `governance`는 cross-layer 허용치를 더 높게 둔다.
  - `infra`는 relation 다양성 최소치(`relation kinds >= 5`)를 유지한다.
  - `needs`는 `contains` relation이 구조적으로 우세할 수 있으므로 relation-specific dominant 임계치를 적용한다.

UI 노출 규칙:

- M1 패널은 현재 품질 상태와 임계치, 탐지된 이슈(최대 3개)를 함께 표시한다.
- `api_edge_cap`은 `critical`로 분류해 “평가 신뢰도 제한”을 명시한다.
- 품질 경고는 구조 축약을 강제하는 정책이 아니라, 설계 적절성 점검 신호로만 사용한다.
- `focus` 모드는 `core|relation|layer` 전략을 지원하며, relation/layer 후보를 함께 노출한다.
  - `focus=core`는 빈도 기반이 아니라 고정 표층 규칙을 사용한다.
  - 기본 노출(구조/인과): `contains`, `depends_on`, `next`, `triggers`, `constrains`
  - 기본 숨김(운영/자기표현/상속계열): `produces`, `consumes`, `coordinates`, `registers`, `available_in`, `specialization`, `redefinition`, `subsetting`, `feature_typing`

### 11.8 Decision Trace 목적/계약

Decision 레이어의 1차 목적은 "무엇을 바꿨는가"가 아니라
"왜 그 변경을 선택했는가 + 어떤 근거로 + 어떤 시스템 변경이 발생했는가"를
프로젝트 수명주기 전체에서 추적 가능하게 만드는 것이다.

핵심 목적:

- 프로젝트 의사결정의 과정(대안/판단/선택)을 기록한다.
- 커널/모델 변경 연산을 decision과 연결해 변경 이유를 역추적 가능하게 만든다.
- 결과적으로 시스템이 어떻게 바뀌었는지(영향 범위/결과 상태)를 조회 가능하게 만든다.

필수 규약(MUST):

- 모델 변경(write) 연산은 `decision_id`와 `evidence_refs[]`를 함께 처리해야 한다.
  - 전달되지 않으면 경고를 남기고, 전달되면 decision trace에 연동 기록한다.
- 외부 모델 변경 API(`POST /models/register|validate|activate`)는 `decision_id`를 필수로 요구해야 한다.
  - 직접 원인은 항상 `decision`이며, `needs`는 decision 아티팩트를 통해서만 간접 원인으로 연결한다.
- decision trace는 최소 아래 의미 필드를 유지해야 한다.
  - `decision_id`, `rationale`, `evidence_refs[]`
  - `operations[]` (어떤 변경 연산이 수행되었는가)
  - `impact[]` (어떤 노드/엣지/레이어에 영향이 있었는가)
  - `history[]` (언제 어떤 상태 변화가 있었는가)
- `operations[]` 항목은 최소 아래를 포함해야 한다.
  - `model_id`, `model_version`, `operation`, `operation_ref`
  - `actor`, `recorded_at`
  - `cause_type` (`decision|need`), `cause_id`
  - `change_phase` (`planned|applied|superseded|rolled_back`)
- decision과 연결된 변경 응답에는 trace 연결 정보를 포함해야 한다.
  - 예: `decision_trace.decision_id`, `decision_trace.trace_model_id`, `decision_trace.evidence_refs`
  - 예: `decision_trace.cause_type`, `decision_trace.cause_id`, `decision_trace.change_phase`

Needs 연동 규약(MUST):

- need는 커널 반영 단계를 `kernel_change_phase`로 노출해야 한다.
  - 허용 값: `planned|applied|superseded|rolled_back`
- decision 근거를 needs로 상속할 때(`inherit-decision-evidence`) 단계 업데이트를 함께 처리할 수 있어야 한다.
- needs 조회 API는 `kernel_change_phase` 필터/응답 필드를 지원해야 한다.

조회 가능성 규약(SHOULD):

- decision 단위 탐색 API는 evidence/impact/history 프로젝션을 제공해야 한다.
- L4(trace) 탐색에서 decision 기반 필터링(특정 `decision_id`)을 지원해야 한다.

비목표(MUST NOT):

- 단순 결과 요약만 저장하고 판단 근거를 누락하는 구현
- 커널 변경 이력과 decision 이력을 분리 저장해 상호 참조가 끊기는 구현
