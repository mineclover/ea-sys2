# ea-kernel Profile Framework Specification

## 개요

Profile Framework는 커널 메타모델 위에 구축된 프로파일 생성 및 수명주기 관리 시스템이다.
flat 구조의 프로파일 모듈로 구성. 커널 코어(types.py, definition.py, spec.py)와 100% 하위 호환.

**핵심 수치**:
- 12 modules (profile_types.py + 11 functional modules)
- Phase 1: 프로파일 생성 (Builder, TOML Loader, Quality Gate, Test Harness)
- Phase 2: 수명주기 관리 (Serializer, Store, Registry, Diff, Schema, Query, Composer)
- 754 tests total, 97% coverage

**해결하는 문제**:

| 이전 | 이후 |
|------|------|
| 프로파일 ~500줄 수동 정의 | ProfileBuilder fluent API로 ~80줄 |
| TOML 정의 불가 | `profile_loader.py` |
| 직렬화 불가 | JSON round-trip + SHA256 content hash |
| 영속화 불가 | SQLite 저장/조회/버전 체인/태그 |
| 프로파일 간 비교 수동 | 구조적 diff |
| 내성(introspection) 없음 | ProfileSchema + ProfileQuery |
| 합성 불가 | extend + subset |

---

## 1. 모듈 구조

```
src/ea_kernel/
  profile_types.py        ← 순수 타입 — zero dependency
  profile_builder.py      ← 선언적 fluent 빌더
  profile_loader.py       ← TOML → KernelProfile
  profile_quality_gate.py ← 빌드타임 품질 게이트
  test_harness.py         ← 자동 테스트 생성
  profile_serializer.py   ← Dict/JSON round-trip + SHA256
  profile_store.py        ← StoragePort ABC + SQLiteProfileStore
  profile_registry.py     ← In-memory + persistence registry
  profile_diff.py         ← 구조적 diff
  profile_schema.py       ← 읽기 전용 내성
  profile_query.py        ← Chainable 쿼리
  profile_composer.py     ← extend / subset
```

### 의존성 방향

```
core: types.py, profile_types.py, definition.py
         ↑
profile_types.py  ← 모든 프로파일 모듈의 기반
         ↑
    ┌────┼────────────────┬──────────────┬──────────────┐
    │    │                │              │              │
  builder  serializer    diff         schema        query
    │         ↑            │              │              │
  loader    store        (독립)       (독립)        (독립)
    │         ↑
  quality   registry
    │
  harness                                          composer
```

---

## 2. Phase 1 — 프로파일 생성

### 2-A. ProfileBuilder

프로파일을 ~80줄의 fluent API로 선언적 구축. 빌드타임 검증 포함.

```python
from ea_kernel import ProfileBuilder

profile = (
    ProfileBuilder("MyFramework", version="1.0", kernel_version="2.5.0")
    .id_prefix("mf")
    .metadata(standard="MyFramework Spec", organization="ACME")
    .category_mapping({"ActiveStructure": "structure", "Behavior": "step"})
    .element("Widget", layer="Core", category="ActiveStructure")
    .element("Process", layer="Core", category="Behavior")
    .relation("uses", kernel_relation="association")
    .allow("@ActiveStructure", "@Behavior", "uses", priority=40)
    .build(auto_fallback=True, validate=True)
)
```

**빌드타임 검증 항목**:
1. 중복 이름 (elements, relations, rule IDs)
2. 커널 참조 유효성 (kernel_type, kernel_relation)
3. 패턴 참조 유효성 (@Category, #Layer, ElementName)
4. 카테고리 일관성 (category_mapping vs 실제 kernel_type)
5. 규칙 관계 참조 (relation name 존재 확인)

**편의 메서드**:

| 메서드 | 용도 |
|--------|------|
| `elements_bulk(list[dict])` | 다중 요소 일괄 추가 |
| `elements_from_matrix(layers, categories, naming)` | 레이어 × 카테고리 매트릭스 생성 |
| `relations(*tuples)` | 다중 관계 일괄 추가 |
| `allow_same_category(relation)` | SAME_CATEGORY 조건부 허용 |
| `allow_same_layer(relation)` | SAME_LAYER 조건부 허용 |
| `rule_group(relation, [(src, tgt), ...])` | 동일 관계 다중 규칙 |

### 2-B. TOML Loader

```python
from ea_kernel import load_profile, load_profile_from_content

profile = load_profile(Path("my_framework.toml"))
```

**TOML 포맷**:

```toml
[profile]
name = "MyFramework"
version = "1.0"
kernel_version = "2.5.0"
id_prefix = "mf"
standard = "MyFramework Spec"
organization = "ACME"

[categories]
ActiveStructure = "structure"
Behavior = "step"

[[elements]]
name = "Widget"
layer = "Core"
category = "ActiveStructure"

[[relations]]
name = "uses"
kernel_relation = "association"

[[rules]]
source = "@ActiveStructure"
target = "@Behavior"
relation = "uses"
priority = 40
```

### 2-C. Quality Gate

```python
from ea_kernel import check_profile_quality

report = check_profile_quality(profile, kernel)
assert report.passed
# report.dead_rules, report.conflicting_rules, report.missing_fallbacks
# report.invalid_patterns, report.invalid_kernel_refs, report.coverage
```

| 검사 항목 | 설명 |
|-----------|------|
| Dead rules | 어떤 요소 쌍에서도 이기지 못하는 규칙 |
| Conflicting rules | 동일 priority, 동일 패턴, 반대 validity |
| Missing fallbacks | deny-by-default fallback 없는 관계 |
| Invalid patterns | 해석 불가능한 @Category/#Layer/ElementName |
| Invalid kernel refs | 커널에 없는 type/relation 참조 |
| Coverage | 커널 타입/관계 사용 비율 |

### 2-D. Test Harness

```python
from ea_kernel import create_standard_tests

TestMyFramework = create_standard_tests(
    profile, kernel,
    expected_element_count=25,
    expected_relation_count=8,
)
```

24개 표준 테스트 자동 생성: 구조, 레이어 분포, 커널 매핑, 카테고리 일관성, 관계 매핑, 규칙 구조, 기본 건전성.

---

## 3. Phase 2 — 수명주기 관리

### 3-A. Profile Serializer

KernelProfile ↔ Dict/JSON 완전 round-trip. SHA256 content hash로 내용 동일성 판별.

```python
from ea_kernel import (
    profile_to_dict, dict_to_profile,
    profile_to_json, json_to_profile,
    compute_content_hash,
)

data = profile_to_dict(profile)
restored = dict_to_profile(data)
assert restored == profile  # 완전 round-trip 보장

hash_val = compute_content_hash(profile)
```

| 함수 | 입력 → 출력 |
|------|-------------|
| `profile_to_dict` | KernelProfile → dict |
| `dict_to_profile` | dict → KernelProfile |
| `profile_to_json` | KernelProfile → JSON str |
| `json_to_profile` | JSON str → KernelProfile |
| `compute_content_hash` | KernelProfile → SHA256 hex |

### 3-B. Profile Store (SQLite)

`StoragePort` ABC + `SQLiteProfileStore` 구현. RuleVersionStore 패턴 준수.

```python
from ea_kernel import SQLiteProfileStore, ProfileOrigin

with SQLiteProfileStore("profiles.db") as store:
    store.initialize()
    pv = store.store(profile, author="user", description="initial", origin=ProfileOrigin.BUILDER)
    # pv.id, pv.content_hash, pv.created_at, pv.parent_id
```

#### DB 스키마

```sql
profile_versions (
    id               TEXT PRIMARY KEY,        -- UUID4 hex
    profile_name     TEXT NOT NULL,
    version          TEXT NOT NULL,
    content_hash     TEXT NOT NULL,            -- SHA256
    profile_data     TEXT NOT NULL,            -- JSON
    element_count    INTEGER NOT NULL,
    relation_count   INTEGER NOT NULL,
    rule_count       INTEGER NOT NULL,
    author           TEXT NOT NULL DEFAULT '',
    description      TEXT NOT NULL DEFAULT '',
    origin           TEXT NOT NULL DEFAULT '', -- ProfileOrigin value
    created_at       TEXT NOT NULL,            -- ISO 8601 UTC
    parent_id        TEXT REFERENCES profile_versions(id),
    UNIQUE(profile_name, version)
)

profile_tags (
    name          TEXT NOT NULL,
    profile_name  TEXT NOT NULL,
    version_id    TEXT NOT NULL REFERENCES profile_versions(id) ON DELETE CASCADE,
    created_at    TEXT NOT NULL,
    PRIMARY KEY (profile_name, name)
)
```

설정: WAL mode, foreign keys ON, `:memory:` 지원

#### StoragePort API

| 카테고리 | 메서드 | 설명 |
|---------|--------|------|
| 수명주기 | `initialize()`, `close()` | DB 초기화/종료 |
| 저장 | `store(profile, *, author, description, parent_id, origin)` | 저장 + 자동 parent 연결 |
| 조회 | `get(version_id)` | ID로 조회 |
| | `get_latest(profile_name)` | 최신 버전 조회 |
| | `get_by_version(profile_name, version)` | 이름+버전으로 조회 |
| | `get_by_content_hash(hash)` | 해시로 조회 |
| 목록 | `list_versions(profile_name, *, ascending)` | 버전 목록 |
| | `list_profiles()` | 프로파일 이름 목록 |
| 태그 | `tag(version_id, tag_name)` | 태그 설정 (upsert) |
| | `get_by_tag(profile_name, tag_name)` | 태그로 조회 |
| | `list_tags(*, version_id, profile_name)` | 태그 목록 |
| 삭제 | `delete(version_id)` | 삭제 (parent_id 참조 정리) |
| 유틸 | `load_profile(version_id)` | 조회 + 역직렬화 → KernelProfile |

#### Version Chain

동일 `profile_name` 내에서 자동 parent 연결:

```
v1.0 (parent=None) → v2.0 (parent=v1.0) → v3.0 (parent=v2.0)
```

교차 프로파일 격리 — A의 parent chain은 B와 독립.

### 3-C. Profile Registry

In-memory 캐시 + 선택적 Store 영속화. 5개 builtin 프로파일 bootstrap.

```python
from ea_kernel import ProfileRegistry, SQLiteProfileStore

store = SQLiteProfileStore("profiles.db")
store.initialize()
reg = ProfileRegistry(store=store)
reg.bootstrap_all()  # 5 builtin + store에서 복원

reg.register(custom_profile, origin=ProfileOrigin.BUILDER)
profile = reg.get("ArchiMate 3.2")
```

#### 워크플로우

```
1. bootstrap()        — 5개 builtin 등록 + Store 영속화
2. load_from_store()  — Store에서 최신 버전 로드 (기존 등록 건너뜀)
3. bootstrap_all()    — 1 + 2 결합 (프로세스 재시작 복원)
4. register()         — 동적 프로파일 등록 (origin 추적, Store 영속화)
```

#### ProfileOrigin

| 값 | 의미 |
|----|------|
| `BUILTIN` | 5개 기본 프로파일 (ArchiMate, TOGAF, Zachman, SysML, BPMN) |
| `BUILDER` | ProfileBuilder로 생성 |
| `TOML` | TOML 파일에서 로드 |
| `STORE` | Store에서 로드 |
| `COMPOSED` | extend/subset으로 합성 |

#### 영속화 보장

| 시나리오 | 동작 |
|---------|------|
| `register()` + Store | Store에 저장. 이미 존재하면 건너뜀 (UNIQUE 충돌 방지) |
| `bootstrap()` + Store | Builtin을 Store에 저장. 이미 존재하면 건너뜀 |
| 프로세스 재시작 | `bootstrap_all()`로 builtin + 저장된 프로파일 모두 복원 |
| `unregister()` | 메모리에서만 제거. Store의 버전 이력은 보존 |

### 3-D. Profile Diff

두 프로파일의 구조적 차이를 계산.

```python
from ea_kernel import diff_profiles, diff_summary

diff = diff_profiles(old_profile, new_profile)
if not diff.identical:
    print(diff_summary(diff))
    # diff.element_changes, diff.relation_changes, diff.rule_changes
```

비교 기준:
- **Elements**: 이름 기준 매칭 → kernel_type, layer, category, description 비교
- **Relations**: 이름 기준 매칭 → kernel_relation, description 비교
- **Rules**: ID 기준 매칭 → 모든 필드 비교 (conditions 포함)

변경 유형: `ADDED`, `REMOVED`, `MODIFIED` (+ 변경된 field, old/new value)

### 3-E. Profile Schema (Introspection)

프로파일 구조의 읽기 전용 내성 뷰.

```python
from ea_kernel import ProfileSchema

schema = ProfileSchema(profile)
schema.layers          # ("Business", "Application", "Technology")
schema.categories      # ("ActiveStructure", "Behavior", ...)
schema.kernel_types_used     # ("structure", "step", "item", ...)
schema.kernel_relations_used # ("association", "flow", ...)
```

| 메서드 | 설명 |
|--------|------|
| `resolve_pattern(pattern)` | 패턴 → 매칭 요소 (`*`, `@Cat`, `#Layer`, `Name`) |
| `element_coverage(kernel)` | 커널 타입 사용 비율 |
| `relation_coverage(kernel)` | 커널 관계 사용 비율 |
| `rules_for_relation(name)` | 특정 관계의 규칙들 |
| `rules_between(src, tgt)` | 특정 source→target 쌍의 규칙들 (패턴 인식) |
| `effective_rule(src, tgt, rel)` | 최고 우선순위 규칙 (deny-first tiebreak) |

### 3-F. Profile Query (Chainable)

요소/규칙에 대한 chainable 필터 쿼리.

```python
from ea_kernel import ProfileQuery

q = ProfileQuery(profile)

# 요소 쿼리
names = q.elements().in_layer("Business").with_kernel_type("structure").names()
count = q.elements().in_category("Behavior").count()
first = q.elements().matching("@ActiveStructure").first()

# 규칙 쿼리
ids = q.rules().for_relation("association").allow_only().ids()
deny_rules = q.rules().deny_only().with_priority_above(50).all()
```

#### ElementQuery 체인

| 메서드 | 필터 |
|--------|------|
| `in_layer(layer)` | 레이어 필터 |
| `in_category(category)` | 카테고리 필터 |
| `with_kernel_type(type)` | 커널 타입 필터 |
| `matching(pattern)` | 패턴 필터 (`*`, `@Cat`, `#Layer`, `Name`) |
| **터미네이터** | |
| `all()` | tuple[ProfileElement, ...] |
| `names()` | tuple[str, ...] |
| `count()` | int |
| `first()` | ProfileElement \| None |

#### RuleQuery 체인

| 메서드 | 필터 |
|--------|------|
| `for_relation(name)` | 관계명 필터 |
| `allow_only()` | valid=True만 |
| `deny_only()` | valid=False만 |
| `with_priority_above(p)` | priority > p |
| `with_priority_below(p)` | priority < p |
| `with_source(pattern)` | source 패턴 필터 |
| `with_target(pattern)` | target 패턴 필터 |
| **터미네이터** | |
| `all()` | tuple[KernelValidityRule, ...] |
| `ids()` | tuple[str, ...] |
| `count()` | int |
| `first()` | KernelValidityRule \| None |

### 3-G. Profile Composer

기존 프로파일 기반으로 새 프로파일 합성.

```python
from ea_kernel import extend, subset

# 확장: 기존 프로파일에 요소/관계/규칙 추가
extended = extend(
    base_profile,
    name="Extended Framework",
    version="2.0",
    add_elements=(new_element,),
    add_rules=(new_rule,),
    override_rules=(replacement_rule,),  # 같은 ID의 규칙 교체
)

# 부분집합: 특정 레이어/카테고리/관계만 추출
business_only = subset(
    profile,
    name="Business Subset",
    version="1.0",
    layers={"Business"},
    categories={"ActiveStructure", "Behavior"},
    relations={"association", "flow"},
)
```

| 함수 | 동작 |
|------|------|
| `extend(base, *, name, version, add_elements, add_relations, add_rules, override_rules)` | 기존 + 추가. override_rules는 동일 ID 규칙 교체 |
| `subset(profile, *, name, version, layers, categories, relations)` | 필터 조건에 맞는 요소 + 관련 규칙만 유지 |

---

## 4. E2E 수명주기

전체 워크플로우 예시:

```
1. ProfileBuilder로 v1.0 생성
     ↓
2. check_profile_quality() — 품질 검증
     ↓
3. Registry.register(origin=BUILDER) — 등록 + Store 영속화
     ↓
4. 분석: ProfileSchema.effective_rule(), ProfileQuery.elements()...
     ↓
5. extend()로 v2.0 생성 — 요소 추가, 규칙 오버라이드
     ↓
6. diff_profiles(v1, v2) — 구조적 변경 분석
     ↓
7. register(v2) → Store에 자동 parent 연결 (v1.0 → v2.0)
     ↓
8. store.tag(v2_id, "stable") — 명명된 참조
     ↓
9. subset()로 Business 레이어만 추출 — 도메인 특화 뷰
     ↓
10. 프로세스 재시작 → bootstrap_all()로 전체 복원
```

---

## 5. 타입 시스템

### 핵심 타입 (`profile_types.py`)

| 타입 | 종류 | 용도 |
|------|------|------|
| `PatternType` | Enum | 패턴 분류 (WILDCARD, CATEGORY, LAYER, EXACT) |
| `ValidationCategory` | Enum | 검증 결과 분류 (6종) |
| `ProfileOrigin` | Enum | 프로파일 출처 (5종) |
| `DiffChangeType` | Enum | 변경 유형 (ADDED, REMOVED, MODIFIED) |
| `QualityReport` | frozen DC | 품질 게이트 결과 |
| `ProfileVersion` | frozen DC | 저장된 버전 스냅샷 |
| `ProfileDiff` | frozen DC | 구조적 diff 결과 |
| `ElementChange` | frozen DC | 요소 변경 내역 |
| `RelationChange` | frozen DC | 관계 변경 내역 |
| `RuleChange` | frozen DC | 규칙 변경 내역 |
| `ProfileTag` | frozen DC | 명명된 태그 |
| `ProfileBuildError` | Exception | 빌드 검증 실패 |
| `ProfileStoreError` | Exception | Store 운영 오류 |
| `ProfileRegistryError` | Exception | Registry 운영 오류 |

### ProfileVersion 필드

```python
@dataclass(frozen=True)
class ProfileVersion:
    id: str                # UUID4 hex
    profile_name: str
    version: str
    content_hash: str      # SHA256
    data: dict             # 직렬화된 프로파일
    created_at: str        # ISO 8601 UTC
    parent_id: str | None  # 이전 버전 링크
    author: str
    description: str
    origin: str            # ProfileOrigin value
```

---

## 6. 검증 체계

```bash
cd packages/ea-kernel && PYTHONPATH=src python -m pytest tests/ -v
# 754 tests, 97% coverage
```

| 테스트 영역 | 파일 | 테스트 수 |
|------------|------|:-:|
| Profile builder | test_profile_builder.py | ~30 |
| TOML loader | test_profile_loader.py | ~20 |
| Quality gate | test_quality_gate.py | ~15 |
| Test harness | test_test_harness.py | ~15 |
| Serializer (5 builtin round-trip) | test_profile_serializer.py | ~20 |
| Store (CRUD, tag, version chain, origin) | test_profile_store.py | ~40 |
| Registry (bootstrap, store sync, origin) | test_profile_registry.py | ~25 |
| Diff (identical, added/removed/modified) | test_profile_diff.py | ~15 |
| Schema (introspection, coverage, rule nav) | test_profile_schema.py | ~20 |
| Query (chainable filters, all builtins) | test_profile_query.py | ~25 |
| Composer (extend, subset, builtin comp) | test_profile_composer.py | ~20 |

### 검증된 보장 사항

| 보장 | 검증 방법 |
|------|----------|
| 직렬화 round-trip | 5개 builtin 프로파일 `dict_to_profile(profile_to_dict(p)) == p` |
| 버전 체인 무결성 | parent_id 자동 연결 + 교차 프로파일 격리 |
| 프로세스 재시작 복원 | bootstrap_all() → 동일 Store에서 전체 복원 |
| 태그 upsert | 동일 태그명 재할당 시 최신 버전으로 갱신 |
| 삭제 체인 정리 | 삭제 시 parent_id NULL 처리 + 태그 CASCADE |
| 콘텐츠 해시 일관성 | 동일 프로파일 → 동일 해시 (canonical JSON) |
| Origin 영속화 | Store ↔ Registry 간 origin 값 보존 |
