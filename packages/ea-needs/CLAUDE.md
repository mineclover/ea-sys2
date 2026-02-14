# ea-needs — Coding Conventions & Module Rules

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
├── kernel_bridge.py     # N3: lazy kernel import (유일한 ea_kernel 참조점)
└── repository.py        # N3: 파일 기반 영속화 (JSON)
```

N1 타입 전부 `frozen=True`. N2 Need만 mutable (status/priority 상태 전이). NeedStatement은 frozen.

## Need Status Transitions

```
DRAFT → EXPRESSED → ACKNOWLEDGED → ADDRESSED
                 ↘              ↘
               WITHDRAWN      WITHDRAWN
```

## Import Convention

**절대 경로 중심**.

```python
from ea_needs.types import Stakeholder, Desire, Justification, NeedStatement
from ea_needs.catalog import NeedCatalog, Need
```

## Typing Convention

- Python 3.11+ 현대 문법: `list[]`, `dict[]`, `str | None`

## Module Rules

### File Size

목표 700줄, 경고 1000줄, 강제분할 1500줄.

### Dependency Direction

```
types.py: 독립 (enums, Stakeholder, Desire, Justification, NeedStatement)
  ← catalog.py (모든 types import)
  ← repository.py (NeedCatalog)
kernel_bridge.py: ea_kernel.definition lazy import (유일한 Kernel 참조점)
```

types.py는 순수 어휘(N1)이므로 프로세스(N2)나 통합(N3) 모듈을 절대 import하지 않는다.
kernel_bridge.py만 ea_kernel을 lazy import한다. 나머지 모듈은 Kernel 타입을 알지 못하며, string ID 기반 간접 참조만 사용한다.

### Test Convention

- 절대 경로 import
- self-contained 테스트 파일
