# Governance Layer -- Role Specialization

> **ea-governance**: 5개 메인 레이어 전체를 관리하는 별도 관리 시스템.

---

## 1. 레이어 정체성

Governance는 5개 메인 레이어(Infra, Decision, Needs, Kernel, Flow)와 **동등 계층이 아닌 별도 관리 시스템**이다. 레이어 체인에 참여하지 않고, 전체 레이어의 모델 등록/버전/활성 상태 관리, 검증 실행 이력 및 진화(승격/폐기) 관리를 담당한다.

### 2단계 분리 설계

| 단계 | 프로파일 | 역할 |
|------|---------|------|
| **거버넌스 운영 메타-메타 모델** | `governance_profile_stack/00-governance-meta-model.toml` | 내부/외부 시스템이 공통으로 따르는 거버넌스 계약 어휘 정의 |
| **시스템별 운영 프로파일** | `ea_sys/10-governance.toml`, `governance_profile_stack/20-external-governance.toml` | 메타-메타 모델을 구체 시스템에 맞게 인스턴스화 |

- 메타-메타 모델이 거버넌스 어휘(GovernanceMetaModel)를 정의하고, 시스템 프로파일(EASystemLayerModel)이 그 어휘대로 구체 요소를 배치한다.
- 즉 **거버넌스는 다른 레이어의 관리자인 동시에 자기 운영 모델의 메타-메타 모델 설계**이기도 하다.

### GovernanceEntryPort -- 시스템 진입점

`GovernanceEntryPort`는 외부에서 거버넌스 시스템에 접근하는 단일 진입점이다. 모든 레이어 핸들링은 이 포트를 통해 이루어진다.

```
외부 요청 → GovernanceEntryPort → {Model*, KernelRule, KernelEvaluate, KernelSnapshot, NeedsCatalog, LayerSnapshot, Dashboard} Endpoint
```

### ACID 트랜잭션 + 이벤트 소싱

모든 mutation은 `TransactionUnit`으로 래핑되며, 상태 변경마다 `TransactionEvent`가 불변 로그로 기록된다.

```
TransactionStatus: PENDING → IN_PROGRESS → (COMMITTED | ROLLED_BACK | FAILED)
```

- `TransactionManager`가 SQLite 기반으로 트랜잭션 ACID를 보장한다.
- 각 도메인 이벤트는 `transaction_events` 테이블에 이벤트 소싱 패턴으로 영속화된다.

---

## 2. 메타-메타 모델 설계

### GovernanceSchema (14 엔티티, 10 릴레이션)

`governance_schema.py`에 정의된 `GOVERNANCE_SCHEMA` 싱글턴은 SchemaPort 프로토콜을 만족한다.

#### 엔티티

| 엔티티 | abstract | 설명 |
|--------|----------|------|
| `governance_boundary` | yes | 거버넌스 제어 경계 |
| `layer_registry` | | 모델 등록 및 인덱싱 |
| `lifecycle_manager` | | 버전 수명주기 제어 |
| `coordinator` | | 오케스트레이션 및 조율 |
| `policy` | | 정책 제약 |
| `governance_goal` | | 거버넌스 목적 목표 |
| `governance_step` | | 워크플로 행위 단계 |
| `governance_action` | | 실행 가능 거버넌스 액션 |
| `governance_record` | | 수동 데이터 레코드 |
| `entry_port` | | 시스템 진입점 인터페이스 |
| `model_port` | | 레이어 모델 포트 인터페이스 |
| `model_endpoint` | | 모델 연산 엔드포인트 |
| `governance_event` | | 수명주기 이벤트 |
| `feedback_loop` | | 반복 교정 행위 |

#### 릴레이션

| 릴레이션 | 설명 |
|---------|------|
| `contains` | 포함(namespace/component) |
| `registers` | 등록(registry membership) |
| `coordinates` | 조율(runtime orchestration) |
| `depends_on` | 의존(데이터/정책) |
| `produces` | 생산(행위 → 산출물) |
| `consumes` | 소비(행위 ← 입력) |
| `next` | 순서(실행 시퀀스) |
| `triggers` | 트리거(이벤트 → 행위) |
| `constrains` | 제약(정책/가드) |
| `available_in` | 가용성(컨텍스트 접근) |

### 10-governance.toml 구조 (~2845줄)

시스템 프로파일은 메타-메타 모델 어휘를 구체화한 대규모 프로파일이다.

#### 6 Policies (정책)

| 정책 | 역할 |
|------|------|
| `RegistrationPolicy` | 모델 등록 제약 |
| `VersionPolicy` | 버전 관리 규칙 |
| `CompatibilityPolicy` | 호환성 검증 규칙 |
| `ApprovalPolicy` | 승인 프로세스 규칙 |
| `BoundaryPolicy` | 경계 제어 규칙 |
| `TransactionPolicy` | 트랜잭션 ACID 규칙 |

#### 4 Goals (목표)

| 목표 | 역할 |
|------|------|
| `GovernanceTransparencyGoal` | 변경 투명성 보장 |
| `GovernanceConsistencyGoal` | 레이어 간 일관성 보장 |
| `GovernanceTraceabilityGoal` | 의사결정 추적 가능성 보장 |
| `GovernanceEvolvabilityGoal` | 모델 진화 가능성 보장 |

#### 5 Coordinators (조율자)

| 조율자 | 역할 |
|--------|------|
| `LayerModelRegistry` | 레이어 모델 정의 등록/인덱싱 |
| `VersionLifecycleManager` | 모델 버전 수명주기 + 활성 포인터 제어 |
| `ValidationCoordinator` | 호환성/무결성 검증 워크플로 실행 |
| `AgreementCoordinator` | 소유자 합의/변경 동의 프로세스 조율 |
| `ActivationCoordinator` | 릴리스 게이트 + 버전 활성화 조율 |

#### Ops 서비스 (구현 계층)

| 서비스 | 역할 |
|--------|------|
| `GovernanceContainer` | 단일 퍼블릭 진입점 (Facade) |
| `KernelModelOps` | 모델 등록/검증/활성화 + 의사결정 추적 연동 |
| `KernelRuleOps` | 규칙 제출/승인/거부/폐기 + 평가 + 스냅샷 |
| `DecisionTraceOps` | 의사결정 추적 읽기/쓰기 |
| `NeedsOps` | Needs 카탈로그 CRUD + 트랜잭션 제어 |
| `TransactionManager` | SQLite 기반 ACID 트랜잭션 + 이벤트 소싱 |
| `ExecutionService` | DesignReport → Flow 워크플로 실행 브릿지 |
| `MetaGenerator` | 의도 분석 → 온톨로지 제안 (실험적) |
| `ProfileBridge` | TOML 프로파일 로딩 + GovernanceSchema 검증 바인딩 |
| `ConditionRegistryService` | 커널 기본 조건 + 4개 거버넌스 조건 확장 |

#### 스토어 계층

| 스토어 | 역할 |
|--------|------|
| `GovernanceLayerStore` (ABC) | 레이어 스코프 스토어 추상화 (InMemory + SQLite 구현) |
| `GovernanceKernelStore` | 커널 규칙/코퍼스/판단 스냅샷 스토어 |
| `GovernanceNeedsStore` | Needs 카탈로그 영속화 어댑터 |

#### 5 ModelEndpoints

| 엔드포인트 | 역할 |
|-----------|------|
| `ModelRegisterEndpoint` | 모델 등록 연산 |
| `ModelValidateEndpoint` | 모델 검증 연산 |
| `ModelActivateEndpoint` | 모델 활성화 연산 |
| `ModelStateEndpoint` | 모델 상태 조회 연산 |
| `ModelDecisionTraceEndpoint` | 의사결정 추적 연산 |

#### 6 추가 Endpoints

| 엔드포인트 | 역할 |
|-----------|------|
| `KernelRuleEndpoint` | 커널 규칙 수명주기 연산 (submit/approve/reject/deprecate) |
| `KernelEvaluateEndpoint` | 커널 판정 평가 연산 |
| `KernelSnapshotEndpoint` | 커널 코퍼스 스냅샷 생성/조회 연산 |
| `NeedsCatalogEndpoint` | Needs 카탈로그 CRUD 연산 |
| `LayerSnapshotEndpoint` | 범용 레이어 스냅샷 save/get/list 연산 |
| `GovernanceDashboardEndpoint` | governance_service.py 순수 함수 쿼리 연산 |

추가로 `GovernanceEntryPort`(시스템 진입), `GovernanceModelPort`(자체 모델 인터페이스), `GovernanceDbPort`(DB 연산) 3개 포트, 30종 Record 타입, 11개 Behavior Step, 7개 Executable Action, 17개 Event, 5개 레이어 크로스 거버넌스 요소(21개)가 정의되어 있다.

### 커스텀 조건 (condition_registry.py)

커널 기본 조건에 거버넌스 전용 4개 조건을 추가 등록한다.

| 조건 | 설명 |
|------|------|
| `SAME_LAYER` | 동일 레이어 내 요소 제약 |
| `SAME_LIFECYCLE` | 동일 수명주기 상태 제약 |
| `SAME_POLICY_SCOPE` | 동일 정책 범위 제약 |
| `SAME_TRANSACTION` | 동일 트랜잭션 내 제약 |

---

## 3. 파이프라인 구현 명세

### Stage 진행 현황

| Stage | 내용 | 상태 | 비고 |
|-------|------|------|------|
| **Stage 1** TOML 외부화 | `specs/` 디렉토리로 스키마 TOML 외부화 | 미완료 | GovernanceSchema가 Python 인라인 (`governance_schema.py`) |
| **Stage 2** Schema | GovernanceSchema 정의 (14 엔티티, 10 릴레이션) | 완료 | SchemaPort 프로토콜 호환, frozen dataclass + tuple |
| **Stage 3** Pattern | 조건 레지스트리 구축 | 완료 | `governance_condition_registry()`: 커널 기본 + 4개 거버넌스 조건 |
| **Stage 4** Lifecycle | 트랜잭션 매니저 + 수명주기 통합 | 완료 | `TransactionManager` ACID, RuleLifecycle 커널 위임 통합 |
| **Stage 5** Catalog | GovernanceContainer Facade 구축 | 완료 | 50+ 메서드, 3-tier Facade/Ops/Store |
| **Profile Loading** | 프로파일 로딩 브릿지 | 완료 | `profile_bridge.py`: TOML 로딩 + 스키마 검증 |
| **Service Layer** | 순수 함수 쿼리 서비스 | 완료 | GS1-GS5 (list_managed_layers, layer_profile_detail, cross_layer_summary, governance_dashboard, layer_schema) |

### Stage 1 미완료 세부

현재 `GovernanceSchema`는 `governance_schema.py`에 Python 코드로 인라인 정의되어 있다. 커널의 `specs/kernel_schema.toml` 패턴처럼 `specs/governance_schema.toml`로 외부화하는 작업이 필요하다. 외부화 시:

- `[meta]` 섹션에 `kernel_version`, `total_entities`, `total_relations` 등 집계 메타데이터 포함
- `schema_loader.py` 패턴으로 TOML → GovernanceSchema 파싱 구현
- 기존 `GOVERNANCE_SCHEMA` 싱글턴은 TOML 로드 결과로 교체

---

## 4. 고유 전문성

### 3-Tier Store 아키텍처

```
Tier 1: Facade (GovernanceContainer)
   └── 단일 진입점. 외부 소비자는 이 클래스만 사용
       │
Tier 2: Ops Modules
   ├── KernelModelOps    — 모델 등록/검증/활성화 + 의사결정 추적
   ├── KernelRuleOps     — 규칙 제출/승인/거부/폐기 + 평가 + 스냅샷
   ├── DecisionTraceOps  — 의사결정 추적 읽기/쓰기
   └── NeedsOps          — Needs 카탈로그 CRUD + 트랜잭션 제어
       │
Tier 3: Store Modules
   ├── GovernanceLayerStore (ABC + InMemory + SQLite)  — 레이어별 영속화
   ├── GovernanceKernelStore                           — 커널 규칙/코퍼스/판단 스냅샷
   ├── GovernanceNeedsStore                            — Needs 카탈로그 영속화
   └── TransactionManager                             — 트랜잭션 + 이벤트 DB
```

- **Facade**는 모든 Ops 모듈을 조합하며, 외부에서 ops 모듈 직접 import는 금지된다.
- **Ops 모듈**은 자기 도메인 의존만 갖는다 (예: `KernelModelOps`는 `ea_kernel.model_registration` + `DecisionTraceOps`만 의존).
- **Store 모듈**은 stdlib만 의존하는 독립 모듈이다 (`layer_store.py`, `transaction.py`는 외부 패키지 무의존).

### 트랜잭션 래핑

모든 mutation은 `TransactionUnit`으로 래핑된다.

```python
# facade.py 내 패턴 (save_layer_snapshot 예시)
tx = self.execution_service.tx_manager.begin_transaction(
    f"{layer}_snapshot_{model_id}",
    tx_type=f"{layer}_layer_write",
    payload={"layer": layer, "model_id": model_id, "actor": actor},
)
try:
    saved_id = store.save_payload(model_id=model_id, payload=payload)
    self.execution_service.tx_manager.add_event(tx.id, "layer_snapshot_saved", ...)
    self.execution_service.tx_manager.commit(tx.id)
except Exception as exc:
    self.execution_service.tx_manager.fail(tx.id, str(exc))
    raise
```

### 이벤트 소싱

`TransactionEvent`는 불변 로그로, 모든 상태 변경의 감사 추적을 제공한다.

```
transactions 테이블:    id, name, tx_type, status, created_at, updated_at, payload_json, logs_json
transaction_events 테이블: id, tx_id, event_type, message, payload_json, created_at
```

### S1-S6 수명주기 통합 (커널 위임)

거버넌스는 커널의 6단계 수명주기와 통합되어, 규칙 자산의 상태 전이를 관리한다.

```
S1 DRAFT → S2 REVIEW → S3 APPROVED → S5 DEPRECATED
```

- `KernelRuleOps.submit_kernel_rule()` → S1 DRAFT 진입
- `KernelRuleOps.approve_kernel_rule()` → S3 APPROVED 전이
- `KernelRuleOps.reject_kernel_rule()` → S2 REVIEW 거부
- `KernelRuleOps.deprecate_kernel_rule()` → S5 DEPRECATED 전이

### 크로스 레이어 버전 관리

6개 레이어 각각 독립 SQLite DB를 소유한다.

```
{data_dir}/
├── layers/infra.db        # Infra 레이어 스냅샷
├── layers/governance.db   # Governance 자체 스냅샷
├── layers/decision.db     # Decision 레이어 스냅샷
├── layers/needs.db        # Needs 레이어 스냅샷
├── layers/kernel.db       # Kernel 레이어 스냅샷
├── layers/flow.db         # Flow 레이어 스냅샷
├── kernel/profiles.db     # 모델 등록 DB
└── transactions.db        # 트랜잭션 이벤트 DB
```

### 의사결정 추적 계약

모델 연산은 의사결정과 연결된다. `decision_id`와 `evidence_refs`가 모든 주요 연산에 선택적으로 전달되며, `DecisionTraceOps`가 추적 기록을 관리한다.

```python
# register_kernel_model 시그니처 (의사결정 추적 파라미터)
def register_kernel_model(
    self,
    profile_toml: str,
    *,
    decision_id: str | None = None,          # 의사결정 ID 연결
    evidence_refs: list[str] | None = None,  # 증거 참조 연결
    return_transaction: bool = False,
    ...
) -> dict[str, Any]: ...
```

---

## 5. 포트 계약 상세

### 자체 포트 (Governance 내부)

| 포트 | 유형 | 역할 |
|------|------|------|
| `GovernanceEntryPort` | entry_port | 시스템 진입점. 외부 요청을 엔드포인트로 라우팅 |
| `GovernanceModelPort` | model_port | 거버넌스 자체 모델 인터페이스 |
| `GovernanceDbPort` | Interface | DB 연산 포트 (LayerStore, TransactionManager 연결) |

### 5 ModelEndpoints (GovernanceEntryPort 하위)

| 엔드포인트 | 구현 매핑 | 역할 |
|-----------|----------|------|
| `ModelRegisterEndpoint` | `GovernanceContainer.register_kernel_model()` | 프로파일 TOML 수신 → 모델 등록 + 검증 |
| `ModelValidateEndpoint` | `GovernanceContainer.validate_kernel_model()` | 등록된 모델의 호환성/무결성 검증 실행 |
| `ModelActivateEndpoint` | `GovernanceContainer.activate_kernel_model()` | 검증 통과 모델을 활성 버전으로 전환 |
| `ModelStateEndpoint` | `GovernanceContainer.get_kernel_model_state()` | 모델 현재 상태 + 최근 검증 이력 조회 |
| `ModelDecisionTraceEndpoint` | `GovernanceContainer.get_model_decision_trace()` | 의사결정 추적 기록 조회/탐색 |

### 6 추가 Endpoints (GovernanceEntryPort 하위)

| 엔드포인트 | 구현 매핑 | 역할 |
|-----------|----------|------|
| `KernelRuleEndpoint` | `GovernanceContainer.submit/approve/reject/deprecate_kernel_rule()` | 커널 규칙 수명주기 연산 |
| `KernelEvaluateEndpoint` | `GovernanceContainer.evaluate_kernel()` | 커널 판정 평가 연산 |
| `KernelSnapshotEndpoint` | `GovernanceContainer.create_kernel_snapshot()` | 커널 코퍼스 스냅샷 생성/조회 |
| `NeedsCatalogEndpoint` | `GovernanceContainer.create/express/revise_needs_*()` | Needs 카탈로그 CRUD |
| `LayerSnapshotEndpoint` | `GovernanceContainer.save/get/list_layer_snapshot()` | 범용 레이어 스냅샷 연산 |
| `GovernanceDashboardEndpoint` | `governance_service.governance_dashboard()` 등 | 순수 함수 쿼리 (대시보드/레이어 상세/크로스 레이어) |

### Governance → Infra (거버넌스가 보는 Infra)

| 요소 | 카테고리 | 역할 |
|------|---------|------|
| `InfraSchemaGovernance` | Behavior | Infra 스키마 변경에 대한 거버넌스 리뷰 단계 |
| `InfraCapacityAudit` | Behavior | 스토리지 용량/건강도 감사 단계 |
| `InfraCompliancePolicy` | Governance | Infra 데이터 처리 준수 정책 |
| `InfraChangeRecord` | PassiveStructure | Infra 스키마 진화 변경 이력 |

### Governance → Decision (거버넌스가 보는 Decision)

| 요소 | 카테고리 | 역할 |
|------|---------|------|
| `DecisionProcessAudit` | Behavior | 의사결정 프로세스 준수 감사 단계 |
| `DecisionModelApproval` | Behavior | 의사결정 메타-모델 변경 승인 게이트 |
| `DecisionGovernancePolicy` | Governance | 의사결정 모델 등록/버전 관리 정책 |
| `DecisionComplianceRecord` | PassiveStructure | 의사결정 프로세스 준수 기록 |

### Governance → Needs (거버넌스가 보는 Needs)

| 요소 | 카테고리 | 역할 |
|------|---------|------|
| `NeedsRegistrationGate` | Behavior | Needs 카탈로그 변경 등록 게이트 |
| `NeedsPriorityAudit` | Behavior | 우선순위 변경/백로그 수정 감사 단계 |
| `NeedsGovernancePolicy` | Governance | Needs 등록/변경 승인 정책 |
| `NeedsChangeRecord` | PassiveStructure | Needs 카탈로그 진화 변경 이력 |

### Governance → Kernel (거버넌스가 보는 Kernel)

| 요소 | 카테고리 | 역할 |
|------|---------|------|
| `KernelContractApproval` | Behavior | 커널 계약 공개 승인 게이트 |
| `KernelRulePromotionGate` | Behavior | 커널 규칙 승격/폐기 게이트 |
| `KernelGovernancePolicy` | Governance | 커널 모델 수명주기 정책 |
| `KernelEvolutionRecord` | PassiveStructure | 커널 스펙 버전 진화 이력 |
| `KernelQualityGate` | Behavior | 커널 프로파일 검증 품질 게이트 |

### Governance → Flow (거버넌스가 보는 Flow)

| 요소 | 카테고리 | 역할 |
|------|---------|------|
| `FlowExecutionAudit` | Behavior | Flow 실행 준수 감사 단계 |
| `FlowContractComplianceCheck` | Behavior | 6x6 계약 매트릭스 준수 검사 |
| `FlowGovernancePolicy` | Governance | Flow 모델 변경/실행 감사 정책 |
| `FlowComplianceRecord` | PassiveStructure | Flow 실행 준수 기록 |

### 크로스 레이어 패턴 요약

거버넌스가 각 레이어를 바라보는 관점은 일관된 4요소 패턴을 따른다:

| 패턴 역할 | 카테고리 | 설명 |
|----------|---------|------|
| **Audit/Gate** (1-2개) | Behavior | 변경 감사 또는 승인 게이트 |
| **Policy** (1개) | Governance | 해당 레이어의 거버넌스 정책 |
| **Record** (1개) | PassiveStructure | 변경/준수 이력 기록 |

Kernel만 예외적으로 `KernelQualityGate`가 추가되어 5개 요소를 갖는다. 이는 커널이 전체 시스템의 의미 체계 기반이므로 프로파일 검증에 별도 품질 게이트가 필요하기 때문이다.

---

## 6. 구현 로드맵

### [HIGH] 거버넌스 메타-메타 모델 TOML 외부화

`GovernanceSchema`를 `specs/governance_schema.toml`로 외부화한다.

- 현재 상태: `governance_schema.py`에 14 엔티티 + 10 릴레이션이 Python 코드로 인라인 정의
- 목표: `specs/governance_schema.toml` 파일에 `[meta]` 메타데이터 + `[[entities]]` + `[[relations]]` 구조로 정의
- `GOVERNANCE_SCHEMA` 싱글턴은 TOML 로드 결과로 교체
- 커널의 `schema_loader.py` 패턴을 거버넌스용으로 확장

### [HIGH] 레이어별 스토어 분리

각 레이어가 자기 도메인 영속화를 소유하는 방향으로 분리한다.

- 현재 상태: `GovernanceKernelStore`, `GovernanceNeedsStore` 2개만 특화 스토어 존재
- 목표: Infra, Decision, Flow 레이어에 대해서도 도메인 특화 스토어 추가
- `GovernanceLayerStore` ABC 위에 각 레이어 도메인 로직 캡슐화

### [MEDIUM] 자기 참조 완성

거버넌스가 자체 모델도 메타-메타 모델을 통해 관리하도록 완성한다.

- 현재 상태: `GovernanceModelPort` 정의는 있으나, 거버넌스 자체 모델의 등록/버전/수명주기는 미구현
- 목표: 거버넌스 프로파일 자체를 `register_governance_model()` → `validate_governance_model()` → `activate_governance_model()` 파이프라인으로 관리
- 메타-메타 모델(`00-governance-meta-model.toml`)이 자기 운영 프로파일(`10-governance.toml`)을 검증하는 순환 구조 완성

### [MEDIUM] 5레이어 프로파일 합성

모든 레이어 프로파일을 조합하여 거버넌스 카탈로그를 구성한다.

- 현재 상태: `governance_service.py`의 GS1-GS5가 개별 레이어 프로파일을 읽기 전용으로 조회
- 목표: 6개 레이어 프로파일의 크로스 레이어 의존성/호환성을 정적으로 검증하는 합성 검증 파이프라인 구현
- `ProfileComposer`를 활용하여 전체 레이어 프로파일 합성 + 충돌 탐지

### [LOW] 전체 정적 시뮬레이션 검증

런타임 실행 이전에 모델 자체의 정합성을 4가지 정적 시뮬레이션으로 검증한다.

| 검증 항목 | 설명 |
|----------|------|
| **Layer-local relation integrity** | 각 레이어 규칙이 내부 relation 정의와 일치하는지 |
| **Decision coverage** | Flow 주요 단계가 Decision 메타-메타 규칙으로 통제되는지 |
| **Data availability** | `consumes` 입력이 `produces`/초기 데이터로 충족되는지 |
| **Sequence integrity** | `next` 체인이 단절되지 않는지 |

- 현재 상태: 시뮬레이션 프레임워크 미구현
- 목표: 각 검증 항목을 독립 검증기로 구현하고, 거버넌스 대시보드(`governance_dashboard`)에 검증 결과를 통합
