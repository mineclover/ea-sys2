# ea-profile — Coding Conventions & Module Rules

> **공통 구현 컨벤션**: `docs/ea-sys-conventions.md` 참조.
> 본 문서는 ea-profile 고유 사항(프로파일 타입, TOML 포맷, ID 체계)만 기술한다.

Kernel-agnostic 프로파일 프레임워크. 프로파일 타입, 빌더, 로더, 시리얼라이저, 품질 게이트, 쿼리, 합성, diff, 저장소, 레지스트리, 스키마, 감사를 제공한다. Python >=3.11, **zero dependency**.

## Design-First Development Pipeline (5-Stage)

모든 레이어가 동일한 "TOML 선언 → 런타임 판정" 파이프라인을 따른다.

```
Stage 1: 선언 (TOML)
  ↓ loader.py
Stage 2: 파싱 (ProfileBuilder)
  ↓ build() + _validate()
Stage 3: 패턴 컴파일
  ↓ @Category/#Layer → 구체 규칙 확장
Stage 4: 자산 거버넌스
  ↓ DRAFT → REVIEW → APPROVED → DEPRECATED
Stage 5: 카탈로그 합성
  ↓ 충돌 해소, 폴백 통합, 커버리지 검증
```

- **Stage 1**: TOML에 요소/관계/규칙을 선언. 프로파일이 진실의 원천(source of truth).
- **Stage 2**: `ProfileBuilder`가 TOML을 파싱하여 불변 `KernelProfile` 스냅샷 생성.
- **Stage 3**: `@Category`, `#Layer` 같은 기호 패턴을 구체 엔티티 조합으로 확장.
- **Stage 4**: 규칙에 수명주기(DRAFT→APPROVED→DEPRECATED)를 부여하고 출처(provenance) 추적.
- **Stage 5**: 다중 레이어 프로파일을 네임스페이싱으로 합성, 충돌 시 명시적 오류.

## Core Types

| Type | 역할 |
|------|------|
| `SchemaPort` | Protocol — 프로파일 검증용 최소 스키마 인터페이스 (`entities`, `relations`) |
| `ProfileRule` | Kernel-agnostic 유효성 규칙 (id, source/target_pattern, relationship_name, valid, priority, conditions) |
| `RuleCondition` | Kernel-agnostic 규칙 조건 (condition_type + parameters) |
| `ProfileElement` | 도메인 요소 → 커널 엔티티 타입 매핑 (name, kernel_type, layer, category) |
| `ProfileRelation` | 도메인 관계 → 커널 관계 매핑 (name, kernel_relation) |
| `KernelProfile` | 프로파일 스냅샷 (elements, relations, validity_rules, metadata) |
| `PatternType` | StrEnum — WILDCARD / CATEGORY / LAYER / EXACT |
| `ConditionRegistry` | 레이어별 TOML 조건 키 → condition_type 매핑 (커널 기본값 제공) |

## Pattern Syntax

프로파일 규칙의 source/target 패턴:

| 패턴 | 의미 | 예시 |
|------|------|------|
| `*` | 모든 요소 | `source_pattern = "*"` |
| `@Category` | 해당 카테고리의 모든 요소 | `source_pattern = "@Behavior"` |
| `#Layer` | 해당 레이어의 모든 요소 | `source_pattern = "#Business"` |
| `ElementName` | 정확한 요소 이름 | `source_pattern = "BusinessProcess"` |

## ID & Naming Conventions

### 프레임워크 프로파일 ID

```
{prefix}-{tag}-{nn}
```

- `prefix`: 프레임워크 약어 (예: `am` ArchiMate, `tg` TOGAF, `zf` Zachman, `sm` SysML2, `bp` BPMN)
- `tag`: 의미 태그 (예: `allow`, `deny`, `fwd`, `fb`)
- `nn`: 2자리 순번

예시: `am-allow-01`, `tg-deny-03`, `bp-fwd-01`

### EA-sys 프로파일 ID

```
eas-{tag}-{nn}
```

- `eas`: EA-system 접두사
- `tag`: 규칙 종류 (예: `allow`, `deny`, `restrict`, `layer`)
- `nn`: 2자리 순번

예시: `eas-allow-01`, `eas-deny-05`

### Fallback ID

각 관계(relation)당 정확히 1개의 deny-by-default 폴백:

```
fb-{relation_name}-deny
```

예시: `fb-association-deny`, `fb-connector-deny`

### Layer Namespace

다중 프로파일 합성 시 충돌 방지를 위해 레이어 접두사 사용:

```
{layer}:{original_id}
```

예시: `kernel:am-allow-01`, `decision:eas-deny-03`

## Profile TOML Format

```toml
[profile]
name = "ArchiMate 3.2"
version = "1.0"
kernel_version = "0.7.0"

[profile.metadata]
standard = "ArchiMate 3.2"
organization = "The Open Group"

[categories]
Behavior = ["step", "action", "event"]
Structure = ["structure", "item"]

[[elements]]
name = "BusinessProcess"
kernel_type = "step"
layer = "Business"
category = "Behavior"
description = "A sequence of business behaviors"

[[relations]]
name = "Serving"
kernel_relation = "association"

[[rules]]
id = "am-allow-01"
source_pattern = "@Behavior"
target_pattern = "@Behavior"
relationship_name = "association"
valid = true
priority = 50
description = "Behavior elements can associate"
```

## i18n Patch Convention

- 네이밍: `{name}.{lang}.patch.toml` (예: `systemselfmodel.ko.patch.toml`, `easystem-kernel.ko.patch.toml`)
- 패치 파일은 `description`/`display_name` 필드만 오버라이드
- `_en_*` 접두사 패턴은 stale i18n 감지용 (원본 영문 변경 시 패치 재검토 필요)

## Module Structure (flat)

```
src/ea_profile/
├── __init__.py       # 패키지 초기화, 버전
├── types.py          # Core 타입 — SchemaPort, ProfileRule, KernelProfile, PatternType 등
├── builder.py        # 플루언트 빌더 + 카테고리 추론 + 자동검증
├── loader.py         # TOML → ProfileBuilder → KernelProfile
├── serializer.py     # dict ↔ KernelProfile 라운드트립
├── quality_gate.py   # 데드 규칙, 충돌, 커버리지 정적 분석
├── schema.py         # 스키마 검증
├── query.py          # 체인 쿼리 빌더
├── composer.py       # extend/subset 합성
├── diff.py           # 프로파일 diff/비교
├── store.py          # SQLite 기반 버전 저장 + 태깅
├── registry.py       # 인메모리 캐시 + 영속 스토어 연동
└── auditor.py        # 프로파일 감사 + 드리프트 감지
```

## Import Convention

공통 import 규율은 `docs/ea-sys-conventions.md` §9 참조. ea-profile 고유 예시:

```python
# ea-profile direct import (권장)
from ea_profile.types import KernelProfile, ProfileRule, ProfileElement
from ea_profile.builder import ProfileBuilder
from ea_profile.loader import load_profile

# Backward compat via ea-kernel shim (기존 코드 호환)
from ea_kernel.profile_types import KernelProfile, ProfileRule
from ea_kernel.profile_builder import ProfileBuilder
```

## Typing / File Size

공통: `docs/ea-sys-conventions.md` §1.5, §10.2, §10.3 참조.

## Module Rules

### Dependency Direction

```
types.py ← builder.py ← loader.py
         ← quality_gate.py
         ← serializer.py
         ← schema.py
         ← query.py
         ← composer.py
         ← diff.py
         ← store.py ← registry.py
         ← auditor.py (quality_gate import)
```

모든 모듈은 `types.py`만 import. 순환 의존 금지.

### Test Convention

- 절대 경로 import
- self-contained 테스트 파일
