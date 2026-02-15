# ea-governance — Coding Conventions & Module Rules

5개 메인 레이어 전체를 관리하는 별도 관리 시스템. 모델 등록/버전/활성 상태 관리, 검증 실행 이력, 의사결정 추적, 트랜잭션 ACID를 담당. ea-kernel + ea-decision + ea-flow + ea-needs + ea-profile에 의존.

## Design Philosophy

3-tier 구조:
- **Facade**: `GovernanceContainer` — 단일 진입점. 외부에서 이 클래스만 사용
- **Ops**: `kernel_model_ops`, `kernel_rule_ops`, `decision_trace_ops`, `needs_ops` — 도메인별 로직 캡슐화
- **Store**: `layer_store`, `kernel_store`, `needs_store` — 레이어별 SQLite 영속화

핵심 원칙: **거버넌스는 다른 레이어의 관리자인 동시에 자기 운영 모델의 메타-메타 모델 설계**

## Module Structure (flat)

```
src/ea_governance/
├── __init__.py              # 패키지 docstring + __version__
├── facade.py                # GovernanceContainer — 단일 퍼블릭 진입점 (644줄)
├── governance_schema.py     # GovernanceSchema (SchemaPort 호환) + GOVERNANCE_SCHEMA 싱글턴
├── governance_service.py    # 순수 함수 쿼리 서비스 (list_managed_layers, governance_dashboard 등)
├── condition_registry.py    # governance_condition_registry() — kernel defaults + 거버넌스 4개 조건
├── profile_bridge.py        # load_governance_profile() — TOML 프로파일 로딩 브릿지
├── meta_model.py            # MetaGenerator — 의도 분석 → 온톨로지 제안 (실험적)
├── execution_service.py     # ExecutionService — DesignReport → Flow 워크플로 실행 브릿지
├── transaction.py           # TransactionManager — SQLite 기반 ACID 트랜잭션 + 이벤트 소싱
├── kernel_model_ops.py      # KernelModelOps — 모델 등록/검증/활성화 + 의사결정 추적 연동
├── kernel_rule_ops.py       # KernelRuleOps — 규칙 제출/승인/거부/폐기 + 평가 + 스냅샷
├── decision_trace_ops.py    # DecisionTraceOps — 의사결정 추적 읽기/쓰기
├── needs_ops.py             # NeedsOps — Needs 카탈로그 CRUD + 트랜잭션 제어
├── layer_store.py           # GovernanceLayerStore — 레이어별 SQLite 스토어 (범용)
├── kernel_store.py          # GovernanceKernelStore — 커널 규칙/코퍼스/판단 스냅샷 스토어
└── needs_store.py           # GovernanceNeedsStore — Needs 카탈로그 영속화 어댑터
```

## Storage Layout

```
{data_dir}/
├── layers/{layer}.db      # 레이어별 스냅샷 (6개: infra, governance, decision, needs, kernel, flow)
├── kernel/profiles.db     # 모델 등록 DB
└── transactions.db        # 트랜잭션 이벤트 DB
```

## Import Convention

**절대 경로 중심**.

```python
from ea_governance.facade import GovernanceContainer
from ea_governance.governance_schema import GOVERNANCE_SCHEMA
from ea_governance.governance_service import governance_dashboard
```

## Typing Convention

- Python 3.11+ 현대 문법: `list[]`, `dict[]`, `str | None`

## Module Rules

### File Size

목표 700줄, 경고 1000줄, 강제분할 1500줄.

### Dependency Direction

```
governance_schema.py: 독립 (GovernanceSchema, GOVERNANCE_SCHEMA)
condition_registry.py: ea_profile.types lazy import
profile_bridge.py: condition_registry + governance_schema ← ea_profile.loader lazy import

layer_store.py: 독립 (sqlite3)
  ← kernel_store.py (layer_store + ea_kernel.governance_types)
  ← needs_store.py (layer_store + ea_needs.catalog)

transaction.py: 독립 (sqlite3, uuid)

decision_trace_ops.py: ea_kernel.governance + layer_store
kernel_model_ops.py: ea_kernel.model_registration + decision_trace_ops
kernel_rule_ops.py: ea_kernel.governance_types + kernel_store
needs_ops.py: ea_needs.catalog + needs_store + execution_service

execution_service.py: ea_decision + ea_flow + transaction

facade.py: 모든 ops + store + service 모듈 통합
  ← __init__.py (public re-export 없음, docstring만)
```

governance_schema.py, layer_store.py, transaction.py는 외부 패키지 의존 없는 독립 모듈.
facade.py만 전체 모듈을 조합하며, ops 모듈은 자기 도메인 의존만 갖는다.

### Facade 사용 규칙

- 외부 소비자는 `GovernanceContainer`만 사용
- ops 모듈 직접 import 금지 (내부 구현)
- `governance_service.py` 순수 함수는 독립 사용 가능 (쿼리 전용)

### Transaction 모델

- 모든 mutation은 `TransactionUnit`으로 래핑
- 상태 전이: `PENDING → IN_PROGRESS → (COMMITTED | ROLLED_BACK | FAILED)`
- 도메인 이벤트는 `TransactionEvent`로 기록 (이벤트 소싱)

### Test Convention

- 절대 경로 import
- self-contained 테스트 파일
