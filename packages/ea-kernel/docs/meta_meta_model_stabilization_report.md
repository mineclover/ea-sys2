# 메타-메타 모델 안정화 및 레이어 적용 계획

> 작성일: 2026-02-15
> 기준 문서: `packages/ea-kernel/docs/system_spec_layers.md`

## 1. 레이어 운영 원칙 (전제)

각 레이어는 자기 관점의 전문성과 검증 규칙을 가진 **독립 시스템**으로 동작한다.
각 레이어의 프로파일(TOML)은 자기 시스템의 요소만 정의하는 것이 아니라, **다른 레이어를 자기 관점에서 정의**한다.

예시 — `00-infra.toml`은 6개 `*ModelPort`를 모두 선언:
- `InfraModelPort` (자기 자신의 모델 인터페이스)
- `GovernanceModelPort` (infra 관점에서 governance에 제공하는 계약)
- `DecisionModelPort`, `NeedsModelPort`, `KernelModelPort`, `FlowModelPort` (동일)

이것이 6x6 포트의 존재 이유다 — 각 레이어가 다른 5개 레이어와의 계약을 **자기 전문성 관점에서** 정의.

---

## 2. 공통 문제 리포트

### 2.1 TOML 스펙 ↔ Python 구현 단절

모든 비-Kernel 레이어에서 TOML 스펙(`examples/ea-sys/*.toml`)과 Python 구현이 **두 개의 독립된 세계**로 존재한다.

| 레이어 | TOML 스펙 정의 | Python 구현 | 단절 지점 |
|--------|--------------|------------|----------|
| **Decision** | DecisionNodeTypeCatalog, DecisionRelationTypeCatalog, DecisionStateCatalog, 4단계 flow (Context→Option→Evaluate→Finalize) | Topic, DesignThinking, Pattern, Evidence | TOML 어휘가 Python 타입을 지배하지 않음. Topic.status는 문자열이고 DecisionStateCatalog와 무관 |
| **Needs** | NeedsCatalogService, UseCaseCatalog, ActorContextCatalog, ConstraintCatalog, PrioritizedNeedSet | NeedsCatalog, Need, Stakeholder, ProcessUnit | 카탈로그 구조가 유사하나 TOML 요소명과 Python 클래스명이 명시적으로 매핑되지 않음 |
| **Flow** | 8단계 (ContextIngest→Normalize→BuildKernelInput→Map→Execute→Verify→Persist→Publish), FlowLayerContractMatrix | FlowRuntime (순차 실행), StepImplementer (2개 mock) | TOML의 8단계가 구현에 반영 안 됨. P2 Coordination 계층 미연동 |
| **Governance** | GovernanceEntryPort, 5개 Policy, 4개 Endpoint, 등록/검증/활성/변경 통제 워크플로우 | GovernanceContainer facade (50+ 메서드) | TOML 워크플로우(Review→Check→Approve→Persist→Activate)와 구현 로직이 직접 매핑 안 됨 |
| **Infra** | DataPlatformService, StorageLifecycleService, 3개 Store, StoragePolicy | ResourceIndexer (파일 스캐너 82줄) | 사실상 무관. TOML 정의의 1% 미만 구현 |

**근본 원인**: Kernel만 "TOML → ProfileBuilder → 패턴 컴파일 → 규칙 판정" 파이프라인을 갖추고 있고, 나머지 레이어는 TOML을 문서용으로만 사용하고 Python은 직접 로직을 코딩하는 방식.

### 2.2 메타-메타 모델 미적용

각 레이어가 "메타-메타 모델로 구조를 먼저 정의하고 그 모델대로 운영"하는 설계 의도가 구현에 반영되지 않음.

**Kernel의 자기적용 패턴**:
```
40-kernel.toml (메타-메타: 커널의 요소/관계/규칙 선언)
    ↓ profile_loader.py
KernelProfile (파싱된 타입)
    ↓ KernelSchema.__post_init__()
인덱싱된 스키마 (O(1) 패턴 매칭)
    ↓ validate_relationship()
런타임 판정 (증거 기반)
```

**나머지 레이어의 현실**:
```
XX-layer.toml (문서로만 존재)
    ↓ (단절)
Python 클래스 (직접 코딩된 로직)
    ↓
런타임 실행 (TOML과 무관)
```

### 2.3 레이어 간 계약 미검증

- 6x6 계약이 `50-flow.toml`의 `FlowLayerContractMatrix`에 선언되어 있으나, 레이어 간 실제 인터페이스 정합성은 `validate_ea_sys_layers.py`에서만 정적 시뮬레이션
- 런타임에서 레이어 간 계약 위반을 감지하는 메커니즘 없음
- 피드백 흐름(`flow → kernel → governance → decision`)이 선언만 존재하고 구현 없음

### 2.4 정책/제약 모델 미분리

`system_spec_layers.md` 원칙: "정책/제약 모델은 중앙집중이 아니라 각 레이어 내부에서 독립적으로 관리"

현실:
- Kernel: `KernelValidityRule` + 우선순위 기반 판정 ✅
- Governance: 5개 Policy 요소가 TOML에 선언되었으나 Python에서 Policy 객체로 구현되지 않음
- Decision: `DecisionCriteriaModel`, `DecisionHeuristicModel`이 TOML에 선언되었으나 Python의 `evaluation.py`와 매핑 안 됨
- Needs/Flow/Infra: 정책 모델 미구현

---

## 3. Kernel 운영 패턴 추출

### 3.1 핵심 파이프라인 (5단계)

Kernel에서 검증된 메타-메타 모델 운영 패턴:

```
Stage 1: 선언 (TOML)
  ↓ profile_loader.py
Stage 2: 해석 (ProfileBuilder)
  ↓ build() + _validate()
Stage 3: 컴파일 (패턴 확장)
  ↓ profile_rule_compiler.py: @Category/#Layer → 구체 규칙
Stage 4: 자산화 (RuleAsset + 수명주기)
  ↓ governance_types.py: DRAFT → REVIEW → APPROVED → DEPRECATED
Stage 5: 거버넌스 카탈로그 (다중 레이어 합성)
  ↓ 충돌 해소, 폴백 통합, 커버리지 검증
```

### 3.2 핵심 설계 원칙

Kernel이 증명한 7가지 원칙:

1. **프로파일은 부작용 없는 불변 스냅샷** — `build()` → 완전한 `KernelProfile` 반환 또는 `ProfileBuildError`
2. **패턴은 컴파일 전까지 기호(symbolic)** — `@Category`, `#Layer`는 프로파일 정의에 유지, 런타임에 확장
3. **수명주기는 불변 이력** — 전이마다 새 인스턴스 생성, 감사 추적 보존
4. **출처(provenance)는 필수** — 모든 규칙이 author, source_type, decision_ref 추적
5. **검증은 계층적** — 빌드 시(구조) → 컴파일 시(패턴 확장) → 런타임(판정)
6. **폴백 규칙은 암시적·결정적** — 모든 관계에 정확히 1개 deny-by-default
7. **합성은 결정적** — `<layer>:` 접두사 네임스페이싱, ID 충돌 시 명시적 오류

### 3.3 재사용 가능한 모듈

| 모듈 | 줄수 | 역할 | Kernel 의존도 |
|------|-----|------|-------------|
| `profile_types.py` | 303 | ProfileElement, ProfileRelation, KernelProfile 타입 | None (ea_profile 추출) |
| `profile_builder.py` | 624 | 플루언트 빌더 + 카테고리 추론 + 자동검증 | None (ea_profile 추출) |
| `profile_loader.py` | 178 | TOML → ProfileBuilder → KernelProfile | None (ea_profile 추출) |
| `profile_rule_compiler.py` | 311 | @Category/#Layer → 구체 규칙 확장 | None (ea_profile 추출) |
| `profile_quality_gate.py` | 202 | 데드 규칙, 충돌, 커버리지 정적 분석 | None (ea_profile 추출) |
| `profile_serializer.py` | 167 | dict ↔ KernelProfile 라운드트립 | None (ea_profile 추출) |
| `profile_store.py` | 379 | SQLite 기반 버전 저장 + 태깅 | None (ea_profile 추출) |
| `profile_registry.py` | 125 | 인메모리 캐시 + 영속 스토어 연동 | None (ea_profile 추출) |
| `profile_query.py` | 111 | 체인 쿼리 빌더 | None (ea_profile 추출) |
| `profile_composer.py` | 96 | extend/subset 합성 | None (ea_profile 추출) |

> **비고**: 위 모듈은 `packages/ea-profile/`로 추출 완료. `ea_kernel.profile_*.py`는 re-export shim으로 전환. `ea_kernel.profile_builder`만 `build_with_corpus()` 커널 전용 확장을 보유.

---

## 4. Kernel 안정화 계획

다른 레이어에 패턴을 적용하기 전, Kernel 자체의 완성도를 높여야 할 영역:

### 4.1 Profile 타입의 Kernel 의존성 분리

**현재 문제**: `profile_types.py`가 `types.py`의 `KernelValidityRule`을 직접 import. 이로 인해 다른 레이어가 프로파일 프레임워크를 재사용하려면 ea-kernel 전체를 의존해야 함.

**안정화 방향**:
- `KernelValidityRule`에서 kernel-agnostic한 `ProfileRule` 추출
- `profile_types.py`가 `ProfileRule`만 사용하도록 분리
- `KernelValidityRule`은 `ProfileRule`을 확장하는 kernel-specific 타입으로 유지
- 다른 레이어가 `profile_types.py`, `profile_builder.py`, `profile_loader.py`를 kernel 의존 없이 사용 가능

### 4.2 Layer 열거형 일반화

**현재 문제**: `types.py`의 `Layer(StrEnum)`이 L1/L2/L3/L4 고정. 다른 레이어는 자체 레이어 분류를 가짐 (Decision: Analysis/Deliberation, Flow: Planning/Execution 등).

**안정화 방향**:
- 프로파일 프레임워크에서 Layer를 opaque string으로 처리 (이미 TOML에서는 문자열)
- `KernelSchema`만 L1-L4 해석, 프로파일 빌더/로더/컴파일러는 Layer를 string으로 전달

### 4.3 서비스 계층 프로토콜 정의

**현재**: `kernel_service.py`가 7개 함수를 직접 구현.

**안정화 방향**:
```python
class ProfileService(Protocol):
    def list_domains(self) -> dict[str, Any]: ...
    def describe_artifact(self, artifact_id: str) -> dict[str, Any] | None: ...
    def query(self, pattern: str, filters: dict) -> list[dict[str, Any]]: ...
    def judge(self, source: str, target: str, relation: str) -> dict[str, Any]: ...
```
- 각 레이어가 동일 프로토콜로 서비스 API 노출
- MCP 서버/REST API에서 레이어별 서비스를 동일 인터페이스로 접근

### 4.4 자기적용 검증 강화

**현재**: `40-kernel.toml`이 kernel 자신을 정의하고, `validate_ea_sys_layers.py`가 정적 시뮬레이션.

**안정화 방향**:
- kernel 부팅 시 `40-kernel.toml` 자동 로드 + 자기검증
- TOML 요소 ↔ Python 클래스 매핑 테이블 생성 및 검증
- 매핑 불일치 시 경고/실패 (구현이 스펙에서 벗어난 것을 감지)

---

## 5. 레이어 적용 계획

### Phase 0: Kernel 프로파일 프레임워크 분리 (선행 조건)

`profile_types.py`에서 kernel-agnostic 타입 추출:

```
ProfileRule (kernel-agnostic)
├── id, source_pattern, target_pattern, relation_name
├── valid, priority, conditions, notes
└── KernelValidityRule extends ProfileRule (kernel-specific)
```

완료 기준:
- [x] `ProfileRule` 타입이 `KernelValidityRule`과 분리
- [x] `profile_builder.py`가 `ProfileRule`로 동작 (KernelValidityRule은 kernel 전용 확장)
- [x] `profile_loader.py`가 kernel 없이도 TOML → KernelProfile 반환 가능
- [x] 기존 테스트 전체 통과

**완료 노트** (2026-02-15):
- `packages/ea-profile/` 독립 패키지로 추출 완료 (13개 모듈, zero dependency)
- ea-kernel의 `profile_*.py`는 ea_profile re-export shim으로 전환 (12개 파일)
- `profile_builder.py` shim만 `build_with_corpus()` 커널 전용 확장을 보유
- ea-kernel이 ea-profile을 pyproject.toml에서 의존

### Phase 1: Decision 레이어 메타-메타 모델 운영화

**목표**: `20-decision.toml`이 Python 구현을 지배하도록 전환

1. **TOML 검토**: `20-decision.toml`의 요소/관계/규칙이 현재 Python 타입과 어떻게 매핑되는지 분석
2. **매핑 테이블 작성**:
   | TOML 요소 | Python 타입 | 상태 |
   |----------|------------|------|
   | DecisionMetaModelRegistry | ? | 미매핑 |
   | DecisionNodeTypeCatalog | ? | 미매핑 |
   | CaptureDecisionContextStep | Topic.add_research? | 부분 매핑 |
3. **프로파일 기반 전환**: Python 타입을 TOML 프로파일에서 로드/검증하도록 재구성
4. **서비스 계층**: `DecisionProfileService` 구현 (ProfileService 프로토콜 준수)

완료 기준:
- [ ] `20-decision.toml` 로드 → KernelProfile 생성 → 자기검증 통과
- [ ] Python 타입 ↔ TOML 요소 매핑 100% 커버
- [ ] Decision 워크플로우(Context→Option→Evaluate→Finalize)가 TOML 규칙으로 제어됨
- [ ] `validate_ea_sys_layers.py`에서 decision 계층 정합성 검증 통과

### Phase 2: Needs 레이어 메타-메타 모델 운영화

**목표**: `30-needs.toml`이 Python 구현을 지배하도록 전환

1. **매핑 분석**: NeedsCatalogService ↔ NeedsCatalog, UseCaseCatalog ↔ UseCase 등
2. **프로파일 전환**: 기존 구현을 TOML 프로파일 기반으로 재구성
3. **서비스 계층**: `NeedsProfileService` 구현

완료 기준:
- [ ] `30-needs.toml` 로드 → 자기검증 통과
- [ ] Python 타입 ↔ TOML 요소 매핑 100% 커버
- [ ] Needs 수명주기(수집→정규화→버전화→발행)가 TOML 규칙으로 제어됨

### Phase 3: Flow 레이어 메타-메타 모델 운영화

**목표**: `50-flow.toml`이 Python 구현을 지배하도록 전환

1. **8단계 파이프라인 구현**: TOML에 정의된 ContextIngest→...→Publish를 FlowRuntime에 반영
2. **P2 Coordination 연동**: DataFlowEdge, LogicCondition을 런타임에 연동
3. **6x6 계약 런타임 검증**: FlowLayerContractMatrix를 런타임에서 강제
4. **서비스 계층**: `FlowProfileService` 구현

완료 기준:
- [ ] `50-flow.toml` 로드 → 자기검증 통과
- [ ] TOML 8단계가 FlowRuntime에서 실행 가능
- [ ] 6x6 계약이 런타임에서 검증됨

### Phase 4: Infra 레이어 메타-메타 모델 운영화

**목표**: `00-infra.toml`이 Python 구현을 지배하도록 전환

1. **영속 포트 인터페이스 설계**: TOML의 ProfileStoragePort, EventStoragePort를 Python ABC로
2. **스토어 구현**: LayerVersionStore, ValidationRunStore, EvidenceStore
3. **StoragePolicy 적용**: TOML 정책이 스토어 행위를 제어
4. **서비스 계층**: `InfraProfileService` 구현

완료 기준:
- [ ] `00-infra.toml` 로드 → 자기검증 통과
- [ ] 영속 포트가 Governance에서 사용됨
- [ ] StoragePolicy가 런타임에서 강제됨

### Phase 5: Governance 자기참조 완성

**목표**: Governance가 자기 운영 모델의 메타-메타 모델 설계를 따르도록 전환

1. **거버넌스 메타-메타 모델 검증**: `00-governance-meta-model.toml`이 거버넌스 운영 어휘 정의
2. **시스템별 프로파일 검증**: `10-governance.toml`이 메타-메타 모델 위에서 동작
3. **자기참조 루프 완성**: Governance가 자기 모델을 등록/검증/활성/통제
4. **다중 레이어 합성**: 5개 레이어 프로파일을 거버넌스 카탈로그로 합성

완료 기준:
- [ ] Governance 운영이 `00-governance-meta-model.toml`의 어휘/규칙으로 제어됨
- [ ] 5개 레이어 프로파일 합성 → 통합 거버넌스 카탈로그 생성
- [ ] 정적 시뮬레이션 4가지 검증 전체 통과:
  - Layer-local relation integrity
  - Decision coverage
  - Data availability
  - Sequence integrity

---

## 6. 실행 순서 요약

```
Phase 0: Kernel 프로파일 프레임워크 분리
    ↓ (선행 조건)
Phase 1: Decision 메타-메타 운영화
    ↓ (런타임 엔트리포인트 체인 시작점)
Phase 2: Needs 메타-메타 운영화
    ↓ (decision → needs 흐름 완성)
Phase 3: Flow 메타-메타 운영화
    ↓ (needs → kernel → flow 흐름 완성)
Phase 4: Infra 메타-메타 운영화
    ↓ (영속 계약 완성)
Phase 5: Governance 자기참조 완성
    ↓ (전체 거버넌스 루프 완성)
```

이 순서는 `system_spec_layers.md`의 런타임 엔트리포인트 체인(`decision → needs → kernel → flow`)을 따르며, infra는 영속 계약이므로 flow 이후, governance는 전체를 관리하므로 마지막.
