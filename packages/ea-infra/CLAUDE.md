# ea-infra — Coding Conventions & Module Rules

> **공통 구현 컨벤션**: `docs/ea-sys-conventions.md` 참조.
> 본 문서는 인프라 레이어 고유 사항(row 데이터 설계, 저장소 포트, 인덱싱)만 기술한다.

인프라 레이어. Row 데이터 설계, 저장소/상태/인덱싱/입출력 데이터 관리 모델. ea-profile에 의존 (M1 파이프라인).

## Design Philosophy

Row-data 설계 레이어:
- **저장소 포트**: ProfileStoragePort, EventStoragePort 등 — 각 레이어에 물리 저장 계약 제공
- **데이터 스키마**: 크로스 레이어 데이터 형상 정의 (Governance/Decision/Needs/Kernel/Flow)
- **수명주기 관리**: 스키마 마이그레이션, 리텐션 정책, 인덱스 전략

핵심 원칙: **Infra는 데이터의 물리적 형상과 생명주기만 관리하고, 도메인 의미는 각 레이어가 소유**

## Module Structure (flat)

```
src/ea_infra/
├── __init__.py             # 패키지 docstring + __version__
├── indexer.py              # 리소스 인덱서 (디렉토리 스캔, 파일 메타데이터 수집)
├── infra_schema.py         # I2.5: InfraSchema (SchemaPort 호환) + INFRA_SCHEMA 싱글턴
├── condition_registry.py   # I2.5: infra_condition_registry() — kernel defaults + 3개 조건
└── profile_bridge.py       # I3: load_infra_profile() / load_infra_profile_from_content()
```

## Import Convention

```python
# Schema
from ea_infra.infra_schema import INFRA_SCHEMA, InfraSchema

# Profile bridge
from ea_infra.profile_bridge import load_infra_profile

# Resource indexing
from ea_infra.indexer import ResourceIndexer, Resource
```

## Module Rules

### Dependency Direction

```
infra_schema.py: 독립 (InfraSchema, InfraEntity, InfraRelation, INFRA_SCHEMA)
condition_registry.py: ea_profile.types lazy import (ConditionRegistry)
profile_bridge.py: infra_schema + condition_registry ← ea_profile.loader lazy import
indexer.py: 독립 (stdlib only)
```

infra_schema.py와 indexer.py는 외부 패키지 의존 없는 독립 모듈.
profile_bridge.py만 ea_profile을 사용한다.

### Test Convention

- 절대 경로 import
- self-contained 테스트 파일
