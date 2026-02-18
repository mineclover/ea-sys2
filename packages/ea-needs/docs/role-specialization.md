# Needs 레이어 역할 전문화 문서

> EA-Sys2 거버넌스 모델링 프레임워크 — Needs 레이어의 정체성, 메타-메타 모델, 파이프라인 현황, 고유 전문성, 포트 계약, 구현 로드맵을 정의한다.

---

## 1. 레이어 정체성

### 핵심 책임

이해관계자 요구를 정형 표현으로 수집하고 관리한다. 의사결정(Decision) 이전에 순수한 니즈를 구조적으로 표현하는 것이 존재 이유다.

### 핵심 문장 패턴

```
"A는 B를 하고 싶다, C이기 때문에"
 → Stakeholder + Desire(action, subject) + Justification(BECAUSE)

"A는 B를 C에 옮기고 싶다, D를 얻기 위해서"
 → Stakeholder + Desire(action, subject, target) + Justification(IN_ORDER_TO)
```

모든 Need는 이 3자 관계(Stakeholder-Desire-Justification triad)로 정당화된다.

### 체인 내 위치

런타임 엔트리포인트 체인의 중간 단계에 위치한다.

```
decision → **needs** → kernel → flow
```

- Decision이 메타-메타 구조를 정형화한 후, Needs가 요구를 정형화하고, Kernel이 도메인 핵심 모델로 고정한다.
- Infra/Governance는 체인 노드가 아니라 각각 데이터 설계/시스템 진입점 설계를 담당한다.

### 3계층 내부 추상화

| 계층 | 명칭 | 책임 |
|:-----|:-----|:-----|
| **N1** | Vocabulary (동결 타입) | 불변 어휘 정의 — Stakeholder, Desire, Justification, NeedStatement, UseCase, NeedProcessUnit + StrEnum 8종 |
| **N2** | Catalog (집합 루트) | NeedCatalog 집합 루트가 use_cases + stakeholders + needs + relations + process_units 관리. Need만 mutable |
| **N3** | Integration (커널 브릿지) | kernel_bridge.py, profile_bridge.py, repository.py — ea-kernel과의 유일한 접점 |

---

## 2. 메타-메타 모델 설계

### 2.1 needs_schema.toml 엔티티 (현재 Python 인라인)

현재 `needs_schema.py`에 Python `NEEDS_SCHEMA` 싱글턴으로 인라인 정의되어 있다. TOML 외부화는 로드맵 1순위.

| # | 엔티티 | abstract | 설명 |
|---|--------|----------|------|
| 1 | `need_catalog` | Y | 니즈 컨테이너 추상 루트 |
| 2 | `stakeholder` | N | 니즈의 주체 |
| 3 | `desire` | N | 이해관계자가 원하는 것 (action + subject + target) |
| 4 | `justification` | N | 이해관계자가 그것을 원하는 이유 (BECAUSE / IN_ORDER_TO) |
| 5 | `need_statement` | N | 이해관계자 니즈의 완전한 불변 표현 |
| 6 | `use_case` | N | 유스케이스 어휘 (actor, situation, purpose, outcome) |
| 7 | `process_unit` | N | 니즈 프로세스 모델링 단위 (IDENTIFY / QUERY / MODEL_DETAIL) |
| 8 | `need` | N | 생명주기 관리 가변 래퍼 (status, priority, version, lineage) |
| 9 | `need_relation` | N | 니즈 간 방향성 관계 |

### 2.2 needs_schema.toml 관계

| # | 관계 | 설명 |
|---|------|------|
| 1 | `depends_on` | 니즈가 다른 니즈에 의존 |
| 2 | `conflicts_with` | 니즈가 다른 니즈와 충돌 |
| 3 | `supports` | 니즈가 다른 니즈를 지원 |
| 4 | `refines` | 니즈가 다른 니즈를 정제 |
| 5 | `supersedes` | 니즈가 다른 니즈를 대체 |
| 6 | `contains` | 카탈로그가 니즈/이해관계자를 포함 |
| 7 | `expresses` | 이해관계자가 욕구를 표현 |
| 8 | `justifies` | 정당화가 욕구를 정당화 |

### 2.3 needs_rules.toml 규칙 (설계 대상)

#### 상태 전이 규칙

```
DRAFT → EXPRESSED → ACKNOWLEDGED → ADDRESSED
                  ↘              ↘
                WITHDRAWN      WITHDRAWN
```

- DRAFT에서 EXPRESSED, WITHDRAWN으로만 전이 가능
- EXPRESSED에서 ACKNOWLEDGED, WITHDRAWN으로만 전이 가능
- ACKNOWLEDGED에서 ADDRESSED, WITHDRAWN으로만 전이 가능
- ADDRESSED, WITHDRAWN은 종단 상태 (전이 불가)

#### 우선순위 정렬 규칙

CRITICAL > HIGH > MEDIUM > LOW 순서를 강제한다. 우선순위 변경은 NeedCatalog 집합 루트 메서드를 통해서만 수행된다.

#### 이해관계자-니즈 관계 제약

- 모든 NeedStatement은 유효한 stakeholder_id를 참조해야 한다.
- 한 Stakeholder는 복수의 Need를 표현할 수 있다.
- NeedStatement은 표현(express) 후 불변이다 — 변경이 필요하면 Need를 revise하여 새 버전을 생성한다.

### 2.4 커스텀 조건 (condition_registry.py)

커널 기본 5개 조건(SAME_LAYER, LAYER_ORDER, ANCESTOR_OF, SAME_BRANCH, SAME_CATEGORY)에 니즈 전용 4개 조건을 추가한다.

| 조건 | 식별자 | 의미 |
|:-----|:-------|:-----|
| `SAME_STATUS` | `same_status` | 두 니즈의 생명주기 상태가 동일한지 검사 |
| `SAME_PRIORITY` | `same_priority` | 두 니즈의 우선순위가 동일한지 검사 |
| `SAME_USE_CASE` | `same_use_case` | 두 니즈가 동일 유스케이스에 속하는지 검사 |
| `SAME_STAKEHOLDER` | `same_stakeholder` | 두 니즈가 동일 이해관계자로부터 표현되었는지 검사 |

---

## 3. 파이프라인 구현 명세

ea-sys 공통 컨벤션(§2 Design-First Pipeline)의 5단계를 Needs 레이어에 대입한 현황이다.

| 단계 | 설명 | 상태 | 비고 |
|:-----|:-----|:-----|:-----|
| **Stage 1** | TOML 선언 (specs/) | 미완료 | TOML 스펙 미외부화, 엔티티가 Python 인라인(`needs_schema.py`)으로 정의됨 |
| **Stage 2** | 파싱 (Builder) | 완료 | `NeedsSchema` (frozen, `SchemaPort` 호환), `NEEDS_SCHEMA` 싱글턴 |
| **Stage 3** | 패턴 컴파일 | 완료 | `needs_condition_registry()` — 커널 기본 5개 + 니즈 전용 4개 = 9개 조건 |
| **Stage 4** | 자산 거버넌스 | 부분 완료 | Need 상태 전이(DRAFT→EXPRESSED→ACKNOWLEDGED→ADDRESSED) 존재, RuleAsset 스타일 거버넌스 통합 미완 |
| **Stage 5** | 카탈로그 합성 | 완료 | `NeedCatalog` 집합 루트 — 전체 CRUD, 버전 관리, 관계 관리 |

### 추가 구현 현황

| 항목 | 상태 | 구현체 |
|:-----|:-----|:-------|
| 프로파일 로딩 | 완료 | `profile_bridge.py` — `load_needs_profile()`, `load_needs_profile_from_content()` |
| 서비스 레이어 | 완료 | `needs_service.py` — 6개 순수 함수 |

#### needs_service.py 함수 목록

| 함수 | 설명 |
|:-----|:-----|
| `list_stakeholders(*, catalog)` | 카탈로그 내 모든 이해관계자 목록 반환 |
| `list_use_cases(*, catalog)` | 카탈로그 내 모든 유스케이스 목록 반환 |
| `list_needs(*, catalog, status=None)` | 니즈 목록 반환, 상태 필터 옵션 |
| `describe_need(*, catalog, need_id)` | 단일 니즈의 statement, process_units, decision evidence 상세 반환 |
| `need_lineage(*, catalog, lineage_id)` | 특정 lineage의 전체 버전 이력 반환 |
| `catalog_summary(*, catalog)` | 카탈로그 개요 — 이해관계자 수, 니즈 수, 상태 분포 |

---

## 4. 고유 전문성

### 4.1 Stakeholder-Desire-Justification 3자 관계

모든 니즈 표현의 기본 구조. Stakeholder가 Desire를 갖고, Justification이 그 이유를 설명한다. NeedStatement이 이 세 요소를 하나의 불변 레코드로 통합한다.

### 4.2 니즈 상태 전이

```
DRAFT → EXPRESSED → ACKNOWLEDGED → ADDRESSED
                  ↘              ↘
                WITHDRAWN      WITHDRAWN
```

- `NeedStatus(StrEnum)` 5개 상태로 관리
- DRAFT에서 시작하여 순방향 진행하거나 중간에 WITHDRAWN으로 분기
- ADDRESSED, WITHDRAWN은 종단 상태

### 4.3 Lineage 기반 버전 관리

- `lineage_id` + `version`으로 니즈 진화 이력을 추적한다.
- `revise_need()`로 새 버전을 생성하되 기존 버전은 불변으로 유지한다.
- `need_lineage()` 서비스 함수로 특정 lineage의 전체 버전 이력을 조회한다.

### 4.4 프로세스 유닛 모델링

3단계 워크플로로 니즈 수집 프로세스를 정형화한다.

```
IDENTIFY → QUERY → MODEL_DETAIL
```

| 단계 | 설명 |
|:-----|:-----|
| `IDENTIFY` | 니즈의 초기 인식 및 포착 |
| `QUERY` | 식별된 니즈의 탐구 및 정교화 |
| `MODEL_DETAIL` | 니즈의 상세 모델링 및 구조화 |

`NeedProcessUnit(frozen=True)` — need_id, stage, label, description, sequence, metadata 필드.

### 4.5 의사결정 증거 상속

`inherit_decision_evidence()` 메서드로 needs → decision 역방향 추적성을 확보한다. 의사결정 근거가 어떤 Need에서 비롯되었는지 추적 가능하다.

### 4.6 유스케이스 바운드 니즈와 원인 유형

- UseCase에 바인딩된 니즈를 `use_case_id`로 관리한다.
- 니즈 발생 원인을 6가지 `NeedCauseType`으로 분류한다: EMOTIONAL, SITUATIONAL, PHYSICAL, LOGICAL, MENTAL, PHILOSOPHICAL.
- 니즈 목적은 `NeedPurpose` 분류로 표준화한다: SAFETY, EFFICIENCY, USABILITY, COMPLIANCE, GROWTH, TRUST, UNSPECIFIED.

### 4.7 해결 복잡도 분류

`NeedResolutionComplexity`로 니즈 해결의 예상 복잡도를 3단계로 분류한다.

| 복잡도 | 설명 |
|:-------|:-----|
| `SIMPLE` | 단순, 직접 해결 가능 |
| `PROCEDURAL` | 정의된 절차가 필요 (기본값) |
| `COMPLEX` | 다면적 접근이 필요 |

### 4.8 집합 루트: NeedCatalog

DDD Aggregate Root 패턴의 경량 적용. 모든 변경(mutation)은 NeedCatalog 메서드를 통해서만 수행된다. 외부에서 Need/NeedStatement을 직접 변경하는 것은 금지된다.

### 4.9 동결 어휘 타입 (7종)

| 타입 | 모듈 | frozen | 설명 |
|:-----|:-----|:-------|:-----|
| `Stakeholder` | types.py | Y | 니즈의 주체 (id, name, role, context) |
| `Desire` | types.py | Y | 이해관계자가 원하는 것 (action, subject, target) |
| `Justification` | types.py | Y | 이유 (type, description) |
| `NeedStatement` | types.py | Y | 완전한 불변 니즈 표현 |
| `UseCase` | types.py | Y | 유스케이스 어휘 (actor, situation, purpose, outcome) |
| `NeedProcessUnit` | types.py | Y | 프로세스 모델링 단위 |
| `Need` | catalog.py | N | 생명주기 관리 가변 래퍼 (상태/우선순위 전이) |

### 4.10 StrEnum 타입 (8종)

| 타입 | 값 |
|:-----|:---|
| `JustificationType` | BECAUSE, IN_ORDER_TO |
| `NeedPriority` | CRITICAL, HIGH, MEDIUM, LOW |
| `NeedStatus` | DRAFT, EXPRESSED, ACKNOWLEDGED, ADDRESSED, WITHDRAWN |
| `NeedRelationType` | DEPENDS_ON, CONFLICTS_WITH, SUPPORTS, REFINES, SUPERSEDES |
| `NeedCauseType` | EMOTIONAL, SITUATIONAL, PHYSICAL, LOGICAL, MENTAL, PHILOSOPHICAL |
| `NeedPurpose` | SAFETY, EFFICIENCY, USABILITY, COMPLIANCE, GROWTH, TRUST, UNSPECIFIED |
| `NeedResolutionComplexity` | SIMPLE, PROCEDURAL, COMPLEX |
| `NeedProcessStage` | IDENTIFY, QUERY, MODEL_DETAIL |

---

## 5. 포트 계약 상세

### 5.1 NeedsModelPort (자기 모델)

Needs 레이어가 자기 자신을 정의하는 인터페이스. 6x6 포트 구조에서 Needs 관점의 자기 표현이다.

### 5.2 교차 레이어 포트 (6x6)

`30-needs.toml` 프로파일에서 Needs 관점으로 다른 5개 레이어를 정의한다.

#### Needs → Infra (요구 카탈로그 영속화)

| 포트 요소 | 카테고리 | 설명 |
|:----------|:---------|:-----|
| `NeedsStorageContract` | Interface | 니즈 카탈로그 영속화를 위한 저장소 포트 계약 |
| `NeedsContextDataSource` | PassiveStructure | 액터/환경 컨텍스트 수집을 위한 데이터 소스 |
| `NeedsBacklogStore` | PassiveStructure | 우선순위 상태 영속화를 위한 백로그 저장소 |

#### Needs → Governance (요구 모델 거버넌스)

| 포트 요소 | 카테고리 | 설명 |
|:----------|:---------|:-----|
| `NeedsApprovalGate` | Behavior | 니즈 등록 변경에 대한 거버넌스 승인 게이트 |
| `NeedsChangePolicy` | Governance | 니즈 변경 통제를 위한 거버넌스 정책 |
| `NeedsAuditPort` | Interface | 거버넌스 컴플라이언스를 위한 감사 제출 포트 |
| `NeedsVersionRecord` | PassiveStructure | 니즈 카탈로그 진화를 위한 버전 메타데이터 |

#### Needs → Decision (의사결정 결과 해석)

| 포트 요소 | 카테고리 | 설명 |
|:----------|:---------|:-----|
| `DecisionOutcomeInput` | PassiveStructure | 니즈 우선순위 입력으로 소비되는 의사결정 결과 |
| `DecisionContextReference` | PassiveStructure | 니즈 추적성을 위한 의사결정 컨텍스트 참조 |
| `DecisionTriggerPort` | Interface | 니즈 변경으로부터 의사결정 인스턴스를 트리거하는 포트 |

#### Needs → Kernel (커널 도메인 매핑)

| 포트 요소 | 카테고리 | 설명 |
|:----------|:---------|:-----|
| `KernelDomainReference` | PassiveStructure | 니즈를 도메인에 매핑하기 위한 커널 도메인 요소 참조 |
| `KernelConstraintInput` | PassiveStructure | 니즈 실현 가능성을 검증하는 커널 제약 |
| `KernelValidationPort` | Interface | 커널 규칙에 대한 니즈 검증 포트 |
| `KernelCoverageTarget` | PassiveStructure | 니즈가 만족해야 하는 커널 커버리지 대상 |

#### Needs → Flow (실행 흐름 충족 추적)

| 포트 요소 | 카테고리 | 설명 |
|:----------|:---------|:-----|
| `FlowFulfillmentStatus` | PassiveStructure | 니즈 충족 추적을 위한 흐름 실행 상태 |
| `FlowProgressFeedback` | PassiveStructure | 백로그 갱신을 위한 흐름 실행 진행 피드백 |
| `FlowCompletionEvent` | Event | 니즈 연계 실행 완료 시 발생하는 이벤트 |

### 5.3 교차 레이어 규칙 구조

각 교차 레이어 포트는 2단계 규칙으로 구성된다.

| 규칙 유형 | priority | 패턴 | 예시 |
|:----------|:---------|:-----|:-----|
| 포트 포함 | 65 | `{Layer}ModelPort` → 포트 요소 `contains` | `InfraModelPort` contains `NeedsStorageContract` |
| 행위 연결 | 72 | 내부 요소 → 포트 요소 `depends_on/consumes/coordinates/constrains` | `NeedsCatalogService` depends_on `NeedsStorageContract` |

---

## 6. 구현 로드맵

| 우선순위 | 항목 | 설명 |
|:---------|:-----|:-----|
| **[HIGH]** | TOML 외부화 | `specs/needs_schema.toml`, `specs/needs_rules.toml` 생성. `needs_schema.py` 인라인 정의를 TOML로 이관. `[meta]` 섹션 포함(entity_count=9, relation_count=8). 로더는 `schema_loader.py` 패턴을 따라 구현 |
| **[HIGH]** | 전용 NeedsStore ABC | 현재 ea-governance가 소유한 `NeedsStore`를 니즈 레이어 자체 소유 스토어로 대체. ABC 인터페이스 + InMemory + SQLite 3중 구현(§5 Store 패턴 준수). 거버넌스 스토어는 크로스 레이어 조율/이력만 담당하고, 도메인 영속화는 니즈 레이어가 직접 소유 |
| **[MEDIUM]** | ConditionRegistry 통합 | `SAME_STATUS`, `SAME_PRIORITY`, `SAME_USE_CASE`, `SAME_STAKEHOLDER` 4개 커스텀 조건을 실제 평가 로직에 바인딩. 현재는 레지스트리 등록만 완료된 상태 |
| **[MEDIUM]** | 거버넌스 라이프사이클 통합 | Need 검증에 RuleAsset 스타일 라이프사이클(DRAFT→REVIEW→APPROVED→DEPRECATED) 적용. 이벤트 버스 연동으로 `NeedExpressedEvent`, `NeedRevisedEvent`, `NeedStatusTransitionEvent`, `DecisionEvidenceInheritedEvent` 발행 |
| **[LOW]** | 기술 부채 해소 | frozen dataclass 내 `list` → `tuple` 마이그레이션. 대상: `UseCase.tags`, `NeedStatement.justifications`, `NeedStatement.kernel_refs`, `NeedStatement.tags`, `NeedStatement.cause_types`. 공통 컨벤션 §1.2 준수를 위한 정리 |
