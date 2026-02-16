# ea-needs — Coding Conventions & Module Rules

> **공통 구현 컨벤션**: `docs/ea-sys-conventions.md` 참조.
> 본 문서는 니즈 레이어 고유 사항(N1/N2/N3 추상화, NeedStatement 불변성, 상태 전이, 프로세스 유닛)만 기술한다.

니즈 레이어. 이해관계자의 순수한 니즈를 의사결정(ea-decision) 이전에 구조적으로 표현. ea-kernel에 단방향 의존.

## Design Philosophy

3-layer Narrative Abstraction:
- **N1 Vocabulary**: 불변 타입 정의 — Stakeholder, Desire, Justification, NeedStatement 등 frozen 데이터
- **N2 Catalog**: 집합 루트 — NeedCatalog가 stakeholders + needs + relations 관리, Need만 mutable
- **N3 Integration**: Kernel bridge와 파일 기반 영속화 (kernel_bridge.py, repository.py)

핵심 원칙: **니즈는 의사결정의 입력 — 모든 Need은 Stakeholder의 Desire와 Justification으로 정당화되고, NeedStatement는 표현 후 불변**

## Core Sentence Patterns

```
"A는 B를 하고 싶다, C가 좋기 때문에"
 → Stakeholder + Desire(action, subject) + Justification(BECAUSE)

"A는 B를 C에 옮기고 싶다, D를 얻기 위해서"
 → Stakeholder + Desire(action, subject, target) + Justification(IN_ORDER_TO)
```

## Module Structure (flat)

```
src/ea_needs/
├── __init__.py          # 패키지 docstring + __version__
├── types.py             # N1: frozen vocabulary (Stakeholder, Desire, Justification, NeedStatement, enums)
├── catalog.py           # N2: NeedCatalog aggregate root + Need mutable wrapper + NeedRelation
├── needs_schema.py      # N2.5: NeedsSchema (SchemaPort 만족) + NEEDS_SCHEMA 싱글턴
├── condition_registry.py # N2.5: needs_condition_registry() — kernel defaults + needs 4개 조건
├── needs_service.py     # N2.5: 순수 함수 쿼리 서비스 (list_stakeholders, describe_need, catalog_summary 등)
├── kernel_bridge.py     # N3: lazy kernel import (유일한 ea_kernel 참조점)
├── profile_bridge.py    # N3: load_needs_profile/load_needs_profile_from_content
├── repository.py        # N3: 파일 기반 영속화 (JSON)
├── needs_store.py       # S3: NeedStore (ABC → InMemory → SQLite) — 니즈 스냅샷 영속화
├── needs_analyzer.py    # S4: NeedsAnalyzer — 이해관계자 커버리지·우선순위 분포 분석
├── needs_simulator.py   # S5: NeedsSimulator — 이해관계자/니즈 변경 What-If 시뮬레이션
└── needs_promotion.py   # S5: NeedPromotionEngine — 니즈 승격/폐기 워크플로
```

N1 타입 전부 `frozen=True`. N2 Need만 mutable (status/priority 상태 전이). NeedStatement은 frozen.

## Need Status Transitions

```
DRAFT → EXPRESSED → ACKNOWLEDGED → ADDRESSED
                 ↘              ↘
               WITHDRAWN      WITHDRAWN
```

## Import Convention

공통 import 규율은 `docs/ea-sys-conventions.md` §9 참조. ea-needs 고유 예시:

```python
# N1 Vocabulary
from ea_needs.types import Stakeholder, Desire, Justification, NeedStatement

# N2 Catalog
from ea_needs.catalog import NeedCatalog, Need

# N3 Integration (kernel bridge — lazy import 내부)
from ea_needs.kernel_bridge import map_need_to_kernel
```

## Typing / File Size

공통: `docs/ea-sys-conventions.md` §1.5, §10.2, §10.3 참조.

## Module Rules

### Dependency Direction

```
types.py: 독립 (enums, Stakeholder, Desire, Justification, NeedStatement)
  ← catalog.py (모든 types import)
  ← needs_service.py (types + catalog)
  ← repository.py (NeedCatalog)
needs_schema.py: 독립 (NeedsSchema, NeedsEntity, NeedsRelation, NEEDS_SCHEMA)
condition_registry.py: ea_kernel.profile_types lazy import (ConditionRegistry)
kernel_bridge.py: ea_kernel.definition lazy import (유일한 Kernel core 참조점)
profile_bridge.py: needs_schema + condition_registry ← ea_kernel.profile_loader lazy import
```

types.py는 순수 어휘(N1)이므로 프로세스(N2)나 통합(N3) 모듈을 절대 import하지 않는다.
needs_schema.py는 독립 어휘(N2.5)이며 ea_kernel에 의존하지 않는다.
kernel_bridge.py, condition_registry.py, profile_bridge.py만 ea_kernel을 lazy import한다.
나머지 모듈은 Kernel 타입을 알지 못하며, string ID 기반 간접 참조만 사용한다.

```
[S3/S4/S5 Governance Lifecycle]
needs_store.py: 독립 (자체 도메인 타입 정의)
  ← needs_analyzer.py (NeedStore — TYPE_CHECKING import)
  ← needs_simulator.py (NeedStore — TYPE_CHECKING import)
needs_analyzer.py ← needs_promotion.py (NeedsAnalysisReport, StakeholderCoverage — TYPE_CHECKING import)
```

### Test Convention

공통: `docs/ea-sys-conventions.md` §8 참조. needs 전용:
- NeedCatalog 테스트는 self-contained (외부 파일 의존 없음)
- 상태 전이 테스트는 유효/무효 경로 모두 검증

## Needs-Specific Patterns

공통 컨벤션(`docs/ea-sys-conventions.md`)에 더해 니즈만 적용하는 패턴:

### N1/N2 분리: Frozen NeedStatement vs Mutable Need
- §1.1 의도적 확장. NeedStatement은 `frozen=True`, Need는 mutable (status/priority 상태 전이 + 의사결정 증거 상속)
- Need가 NeedStatement을 참조하되 상태 변경은 Need 레벨에서만 발생

### Frozen Dataclass 내 list 사용 (§1.2 편차)
- NeedStatement/UseCase가 `list[str]` 사용. 공통 컨벤션 §1.2는 `tuple` 권장
- 차후 tuple 마이그레이션 가능한 기술 부채

### Aggregate Root 패턴 (NeedCatalog)
- DDD aggregate 경량 적용. 모든 변경은 카탈로그 메서드를 통해야 함
- 외부에서 Need/NeedStatement을 직접 변경 금지

### Lineage 기반 버전 관리
- lineage_id + version으로 Need 이력 추적
- `revise_need()`로 신규 버전 생성 (기존 불변 유지)

### Decision Evidence 상속
- `inherit_decision_evidence()`로 needs→decision 역방향 추적성 확보
- 의사결정 근거가 어떤 Need에서 비롯되었는지 추적

### 프로세스 유닛 모델링
- IDENTIFY → QUERY → MODEL_DETAIL 3단계
- 니즈 수집 프로세스의 정형화된 워크플로

### needs_service.py (kernel_service.py 패턴 준수)
- 순수 함수, `dict[str, Any]` 반환, keyword-only 인자
- §3.1~§3.4 공통 서비스 패턴 그대로 적용
- NeedCatalog을 인자로 받아 쿼리 전용 서비스 제공 (list_stakeholders, list_needs, describe_need, need_lineage, catalog_summary 등)

### specs 디렉토리 (차후 작업)
- 스키마가 Python 인라인 (needs_schema.py). TOML 외부화 차후 예정
- §2.2 specs/ 디렉토리 구조는 차후 마이그레이션 시 적용

### Repository 패턴 (2-tier)
- `repository.py`: 단순 JSON 파일 기반 영속화 (N3 Integration)
- `needs_store.py`: S3 Recording — ABC → InMemory → SQLite 3-tier 스토어 (도메인 영속화를 needs 레이어가 직접 소유)
- 크로스 레이어 이력 관리는 ea_governance.needs_store가 담당

### 6-Phase Governance Lifecycle (S3/S4/S5)

Kernel의 6-phase governance lifecycle 패턴을 Needs 도메인 어휘로 번역:
- **S3 Recording** (needs_store.py) — 니즈 스냅샷 영속화 (ABC → InMemory → SQLite 3-tier)
- **S4 Analysis** (needs_analyzer.py) — 이해관계자 커버리지, 우선순위 분포, 해결 처리량 분석
- **S5 Evolution** (needs_simulator.py, needs_promotion.py) — What-If 시뮬레이션 + 니즈 승격/폐기 워크플로

Store 패턴은 ea-kernel/decision_store.py와 동일: `__slots__`, `@contextmanager _connection()`, `_init_schema()`.
Promotion 패턴은 ea-kernel/promotion_engine.py와 동일: in-memory proposal store, vote/approve/reject/apply 워크플로.
