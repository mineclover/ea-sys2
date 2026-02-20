# ea-governance — Coding Conventions & Module Rules

> **공통 구현 컨벤션**: `docs/ea-sys-conventions.md` 참조.
> 본 문서는 거버넌스 고유 사항(3-tier Facade/Ops/Store, 트랜잭션 ACID, 크로스 레이어 관리)만 기술한다.

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
├── facade.py                # GovernanceContainer — 단일 퍼블릭 진입점
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
├── lifecycle_ops.py         # LifecycleOps — S4/S5/S6 크로스 레이어 피드백 루프 (분석→제안→전파 환류)
├── layer_store.py           # GovernanceLayerStore ABC + InMemory + SQLite 3중 구현
├── kernel_store.py          # GovernanceKernelStore — 커널 규칙/코퍼스/판단 스냅샷 스토어
├── needs_store.py           # GovernanceNeedsStore — Needs 카탈로그 영속화 어댑터
└── api_router.py            # §3.5 API Router: governance_router + layer_schema_router (FastAPI)
```

## Storage Layout

```
{data_dir}/
├── layers/{layer}.db      # 레이어별 스냅샷 (6개: infra, governance, decision, needs, kernel, flow)
├── kernel/profiles.db     # 모델 등록 DB
└── transactions.db        # 트랜잭션 이벤트 DB
```

## Import Convention

공통 import 규율은 `docs/ea-sys-conventions.md` §9 참조. ea-governance 고유 예시:

```python
# Facade (외부 소비자 권장)
from ea_governance.facade import GovernanceContainer

# Schema / Service (독립 사용 가능)
from ea_governance.governance_schema import GOVERNANCE_SCHEMA
from ea_governance.governance_service import governance_dashboard
```

## Typing / File Size

공통: `docs/ea-sys-conventions.md` §1.5, §10.2, §10.3 참조.

## Module Rules

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
lifecycle_ops.py: execution_service + layer_store (S4/S5/S6 lazy imports: ea_kernel.promotion_engine, ea_decision.pattern_promotion, ea_flow.workflow_promotion, ea_needs.needs_promotion)

execution_service.py: ea_decision + ea_flow + transaction

facade.py: 모든 ops + store + service 모듈 통합
  ← __init__.py (public re-export 없음, docstring만)

api_router.py: governance_service (FastAPI APIRouter, §3.5 플러그인 패턴)
```

governance_schema.py, layer_store.py, transaction.py는 외부 패키지 의존 없는 독립 모듈 (stdlib only).
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

공통: `docs/ea-sys-conventions.md` §8 참조. governance 전용:
- Store 테스트는 `tempfile.TemporaryDirectory`로 SQLite 격리
- Facade 테스트는 GovernanceContainer 생성 → 조작 → 검증 패턴

## Governance-Specific Patterns

공통 컨벤션(`docs/ea-sys-conventions.md`)에 더해 거버넌스만 적용하는 패턴:

### GovernanceContainer Facade (OO 컨테이너)
- §3 의도적 확장. 상태를 가진 OO 컨테이너 (순수 함수 서비스 레이어와 공존)
- 순수 함수 쿼리는 governance_service.py가 별도 담당

### governance_service.py (kernel_service.py 패턴 준수)
- 순수 함수, `dict[str, Any]` 반환, `_get_*` lazy init
- §3.1~§3.4 공통 서비스 패턴 그대로 적용

### Ops 모듈 캡슐화
- 도메인별 로직 클래스 (KernelModelOps, KernelRuleOps, DecisionTraceOps, NeedsOps)
- 외부 직접 import 금지 — facade.py를 통해서만 접근

### Transaction ACID + Event Sourcing
- §6 거버넌스 전용 확장. TransactionStatus `StrEnum`, TransactionEvent 이벤트 소싱
- 모든 상태 변경은 트랜잭션 단위로 원자적 실행

### Cross-Layer Store 조율
- 6개 레이어 독립 LayerStore + kernel/needs 특화 스토어
- 각 레이어가 자체 특화 스토어를 갖는 방향 (§5.4). 메타-메타 기반 프로파일 버전 관리는 레이어 자체가 소유
- Governance는 크로스 레이어 이력 조율·검증 실행 이력·진화(승격/폐기) 관리에 집중

### Store 패턴 (§5 준수)
- GovernanceLayerStore ABC + InMemoryGovernanceLayerStore + SQLiteGovernanceLayerStore 3중 구현
- kernel_store, needs_store는 ABC를 생성자로 수신 (DI)

### GovernanceSchema (SchemaPort 호환)
- frozen dataclass + tuple + GOVERNANCE_SCHEMA 싱글턴
- §1.1, §1.2 공통 패턴 준수

### specs 디렉토리 (차후 작업)
- 스키마가 Python 인라인 (governance_schema.py). TOML 외부화 차후 예정
- §2.2 specs/ 디렉토리 구조는 차후 마이그레이션 시 적용
