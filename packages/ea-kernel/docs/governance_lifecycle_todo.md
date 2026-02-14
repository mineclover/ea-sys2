# Governance Lifecycle — 구현 TODO

## 최종 목적

ea-kernel의 Governance Lifecycle 시스템을 **실제 코드로 구현**한다.
설계 문서(`docs/governance_lifecycle.md`)에 정의된 6단계 순환 루프를 5-Phase에 걸쳐 점진적으로 구현하되,
각 Phase가 독립적으로 가치를 전달하도록 한다.

**목표 모델**: `src/ea_kernel/profiles/governance_lifecycle.toml` (37 elements, 12 relations, ~50 rules)
이 TOML 프로파일이 구현 전체의 **구조적 청사진** 역할을 하며, 각 Phase에서 만드는 모듈이
이 모델의 어떤 영역을 활성화하는지 추적한다.

---

## 참조 문서

| 문서 | 경로 | 역할 |
|------|------|------|
| 설계 문서 | `docs/governance_lifecycle.md` | 6단계 아키텍처, 데이터 흐름, 구현 로드맵 |
| 표현력 검토 | `docs/expressiveness_review.md` | FruitRetail 예제 기반 커널 표현력 평가 |
| 사용 경험 | `docs/usage_experience.md` | 프로파일 실사용 후기 |
| 규칙 분석 | `docs/validity_rules_corrected_analysis.md` | Validity Rules 형식 분석 |
| 프로파일 설계 원칙 | `src/ea_kernel/docs/profile_design.md` | 2-Stage Validation, Package Exposure, **Hosted Flow Pattern** |
| 프로파일 프레임워크 | `src/ea_kernel/docs/profile-framework.md` | Builder/TOML/Store/Registry/Diff/Composer 프레임워크 |
| 커널 로드맵 | `src/ea_kernel/docs/roadmap.md` | Phase 0→4.5 완료 이력, AI 의사결정 인터페이스까지 |
| 커널 스펙 | `src/ea_kernel/docs/spec.md` | L1-L4 엔티티/관계 정의 |

## 참조 코드

| 모듈 | 경로 | 역할 |
|------|------|------|
| 목표 모델 (TOML) | `src/ea_kernel/profiles/governance_lifecycle.toml` | 37 elements, 12 relations — 구현 청사진 |
| 모델 검증 테스트 | `tests/test_governance_lifecycle_model.py` | 구조·품질·데이터흐름·표현한계 검증 |
| 커널 타입 | `src/ea_kernel/types.py` | KernelSchema, KernelValidityRule, RuleCorpus 타입 |
| 프로파일 타입 | `src/ea_kernel/profile_types.py` | ProfileRelation.direction, KernelProfile |
| 프로파일 빌더 | `src/ea_kernel/profile_builder.py` | hosted_flow() 헬퍼, direction 지원 |
| 프로파일 감사 | `src/ea_kernel/profile_auditor.py` | direction 일관성 검증 |
| 의사결정 원장 | `src/ea_kernel/decision_ledger.py` | 기존 M0 의사결정 기록 (Phase 1에서 확장) |
| AI 인터페이스 | `src/ea_kernel/ai_interface.py` | AI 에이전트 의사결정 인터페이스 |
| 규칙 코퍼스 | `src/ea_kernel/rule_corpus.py` | RuleCorpus.judge() — 증거 기반 판단 |
| 그래프 뷰 | `src/ea_kernel/graph_view.py` | 토폴로지 그래프 탐색 |
| 생명주기 컨트롤러 | `src/ea_kernel/lifecycle_controller.py` | Automation 이벤트 처리 및 워크플로우 제어 |
| 거버넌스 파사드 | `src/ea_kernel/governance.py` | GovernanceSystem 통합 진입점 |

---

## 완료된 사전 작업

### Pre-Phase: 자체 모델링 검증 ✅

governance_lifecycle.toml로 커널 자신을 모델링하여 표현 경계를 발견하고, 프로파일 프레임워크를 보강.

| 작업 | 상태 | 커밋 |
|------|------|------|
| governance_lifecycle.toml 작성 (37 elem, 12 rel, ~50 rules) | ✅ | `c11ded7` |
| test_governance_lifecycle_model.py — 7개 테스트 클래스 | ✅ | `c11ded7` |
| 5가지 표현 경계 발견 및 문서화 | ✅ | `c11ded7` |
| Hosted Flow Pattern 문서화 (profile_design.md) | ✅ | 현재 세션 |
| ProfileRelation.direction 필드 추가 | ✅ | 현재 세션 |
| ProfileBuilder.hosted_flow() 헬퍼 | ✅ | 현재 세션 |
| ProfileAuditor direction 일관성 검증 | ✅ | 현재 세션 |
| governance_lifecycle.toml direction 반영 | ✅ | 현재 세션 |

### 발견된 표현 경계 (5가지)

1. **Flow는 feature 계통만 참여**: structure/item은 직접 flow 불가 → **Hosted Flow Pattern**으로 해결
2. **Flow 방향 미구분**: produces/consumes 모두 kernel flow → **ProfileRelation.direction**으로 해결
3. **특정 state 간 전이 구분 불가**: 커널은 state→state만 봄 → 프로파일 규칙으로 해결 (이미 TOML에 반영)
4. **특정 step 간 순서 구분 불가**: 커널은 step→step succession만 봄 → 프로파일 규칙으로 해결
5. **Instance-level 제약 불가**: 커널은 type-level만 → M0 instance_validator 영역 (기존 Phase 3 완료)

---

## 구현 Phase

> 참조: `docs/governance_lifecycle.md` §12 Implementation Roadmap

### Phase 1: Foundation (S3 + Versioning)

> "판단 기록이 사라지지 않는다"

**활성화 모델 영역**: Recording 레이어 (DecisionStore, DecisionRecord, JudgmentStat)

| # | 작업 | 신규 모듈 | 모델 매핑 | 상태 |
|---|------|----------|----------|------|
| 1.1 | `governance_types.py` 생성 — 공통 타입 정의 | governance_types.py | RuleAsset, RuleProvenance, RuleLifecycle 등 | ✅ |
| 1.2 | `DecisionStore` ABC + SQLite 구현 | decision_store.py | DecisionStore(structure), DecisionRecord(item) | ✅ |
| 1.3 | `CorpusVersionStore` 구현 | corpus_version_store.py | CorpusVersion(item), RuleCorpus(package) | ✅ |
| 1.4 | `DecisionLedger._store` 포트 연결 | decision_ledger.py (확장) | RecordDecision(step) 행위 활성화 | ✅ |
| 1.5 | 기존 테스트 호환 유지 확인 (47개 통과) | — | — | ✅ |

| 1.6 | Phase 1 통합 테스트 (34개 테스트) | tests/test_governance_phase1.py | S3 데이터 흐름 end-to-end | ✅ |
| 1.7 | **ea-decision (Support Layer)** | ea-decision package | Topic, DesignReport, Timeline, Revision | ✅ |

**커널 호환 원칙**: 기존 `RuleCorpus.judge()`, `KernelSchema.validate_relationship()` 시그니처 불변.

### Phase 2: Insight (S4)

> "축적된 판단에서 의미가 나온다"

**활성화 모델 영역**: Analysis 레이어 (EvidenceAnalyzer, RuleEffectiveness, ConflictHotspot, UsageProfile, AnalysisReport)

| # | 작업 | 신규 모듈 | 모델 매핑 | 상태 |
|---|------|----------|----------|------|
| 2.1 | `EvidenceAnalyzer` 구현 | evidence_analyzer.py | EvidenceAnalyzer(structure) | ✅ |
| 2.2 | `RuleEffectiveness` 계산 로직 | evidence_analyzer.py | RuleEffectiveness(item) | ✅ |
| 2.3 | `ConflictHotspot` 탐지 | evidence_analyzer.py | ConflictHotspot(item) | ✅ |
| 2.4 | `UsageProfile` 통계 | evidence_analyzer.py | UsageProfile(item) | ✅ |
| 2.5 | `AnalysisReport` 집계 | evidence_analyzer.py | AnalysisReport(item) | ✅ |
| 2.6 | Phase 2 통합 테스트 | tests/test_governance_phase2.py | S4 분석 파이프라인 | ✅ |

**의존**: Phase 1 (DecisionStore에서 판단 이력 읽기)

### Phase 3: Governance (S1 + S5)

> "규칙이 관리되고 진화한다"

**활성화 모델 영역**: Authoring 레이어 + Evolution 레이어 + Lifecycle 상태 전이

| # | 작업 | 신규 모듈 | 모델 매핑 | 상태 |
|---|------|----------|----------|------|
| 3.1 | `RuleAsset` + `RuleProvenance` + `RuleLifecycle` 타입 | governance_types.py (확장) | RuleAsset(item), RuleAuthor(structure) | ✅ |
| 3.2 | `RuleAssetStore` ABC + SQLite 구현 | rule_asset_store.py | AuthorRule(step) 행위 활성화 | ✅ |
| 3.3 | 상태 전이 엔진 (Draft→Review→Approved→Deprecated) | rule_asset_store.py | LifecycleState 4종, TriggerEvent 3종 | ✅ |
| 3.4 | `PromotionEngine` + `PromotionCriteria` | promotion_engine.py | PromotionEngine(structure), PromotionCriteria(expression) | ✅ |
| 3.5 | `WhatIfSimulator` | what_if_simulator.py | WhatIfSimulator(structure), ProposeEvolution(step) | ✅ |
| 3.6 | `RuleChangeProposal` 관리 | promotion_engine.py | RuleChangeProposal(item) | ✅ |
| 3.7 | Phase 3 통합 테스트 | tests/test_governance_phase3.py | S1+S5 규칙 생명주기 | ✅ |

**의존**: Phase 2 (AnalysisReport 기반 승격 판단)

### Phase 4: Propagation (S6 + S2 보강)

> "변경의 영향을 알 수 있다"

**활성화 모델 영역**: Propagation 레이어 + Judgment 레이어 보강

| # | 작업 | 신규 모듈 | 모델 매핑 | 상태 |
|---|------|----------|----------|------|
| 4.1 | `ImpactEvaluator` 구현 | impact_evaluator.py | ImpactEvaluator(structure), EvaluateImpact(step) | ✅ |
| 4.2 | `RuleChangeSet` diff | impact_evaluator.py | RuleChangeSet(item), ImpactReport(item) | ✅ |
| 4.3 | `JudgmentService` (S2 래핑 + S3 자동 연결) | judgment_service.py | JudgmentEngine(structure), ExecuteJudgment(step) | ✅ |
| 4.4 | `ReferenceStats` 첨부 | judgment_service.py | ReferenceStats(item), JudgmentReport(item) | ✅ |
| 4.5 | `LifecycleEventPort` ABC | lifecycle_events.py | TriggerEvent 3종의 실행 포트 | ✅ |
| 4.6 | Phase 4 통합 테스트 | tests/test_governance_phase4.py | S6+S2 영향 전파 | ✅ |

**의존**: Phase 2 (DecisionStore), Phase 3 (RuleAssetStore)

### Phase 5: Automation (Controller)

> "거버넌스가 자동으로 돈다"

**활성화 모델 영역**: Automation 레이어 + Workflow 연결

| # | 작업 | 신규 모듈 | 모델 매핑 | 상태 |
|---|------|----------|----------|------|
| 5.1 | `LifecycleController` 구현 | lifecycle_controller.py | LifecycleController(structure), ExecuteLifecycle(step) | ✅ |
| 5.2 | Event-Driven Workflow | lifecycle_controller.py | TriggerEvent 3종 처리 | ✅ |
| 5.3 | Auto-Promotion Logic | lifecycle_controller.py | ProposeEvolution(step) | ✅ |
| 5.4 | Notification Service (Mock) | notification_service.py | Notifier(structure) | ✅ |
| 5.5 | Phase 5 통합 테스트 | tests/test_governance_phase5.py | Automation 시나리오 | ✅ |

**의존**: Phase 4 (LifecycleEventPort)

### Phase 6: Scale (Multi-tenancy) — Future Work

> "여러 조직이 함께 사용한다"

| # | 작업 | 모델 매핑 | 상태 |
|---|------|----------|------|
| 6.1 | Tenant isolation | RuleCorpus(package) 테넌트별 인스턴스 | ✅ |
| 6.2 | Corpus 합성 (overlay) | Shared Base + Profile + Tenant Custom | ✅ |
| 6.3 | Cross-tenant analysis | EvidenceAnalyzer 교차 집계 | ✅ |
| 6.4 | Shared Reference Catalog | 공유 레퍼런스 카탈로그 (find_common_patterns) | ✅ |
| 6.5 | Phase 6 통합 테스트 | 다중 테넌트 시나리오 | ✅ |

**의존**: Phase 1-5 전부

---

## 📅 Operational Extensions (Implemented)

Governance Lifecycle 구현이 완료되었으며, 운영 및 데이터 이동성을 위한 확장이 구현되었습니다.

### 1. Model I/O (Export/Import) ✅
- **Goal**: 서로 다른 `GovernanceSystem` 간 규칙 자산 이동 및 백업.
- **Status**: `ModelIOManager` 구현 및 API 연동 완료. JSON 포맷 지원.

### 2. API Gateway ✅
- **Goal**: 외부 시스템(웹 프론트엔드)에서 접근 가능한 REST 인터페이스.
- **Status**: `ea_kernel.api.server` (FastAPI) 구현 완료. 생명주기/판단/버전관리 API 제공.
- **Features**:
  - Rule Lifecycle Management (Submit/Approve)
  - Judgment Execution
  - Model Export/Import
  - Version Management & Snapshot
  - Topology Visualization (Mermaid)

### 3. Visualization & Experience ✅
- **Goal**: 시스템 토폴로지 및 프로세스 시각화.
- **Status**: `DiagramExporter` (Mermaid.js) 및 `TopologyGraph` 필터링(Profile/Version) 구현 완료.


---

## Phase 의존 그래프 (Completed)

```
Pre-Phase (자체 모델링 검증) ✅
    │
    ▼
Phase 1: Foundation (S3 + Versioning) ✅
    │
    ▼
Phase 2: Insight (S4) ✅
    │         │
    ▼         ▼
Phase 3: Governance (S1 + S5) ✅
    │
    ▼
Phase 4: Propagation (S6 + S2 보강) ✅
    │
    ▼
Phase 5: Automation (Controller) ✅
    │
    ▼
Phase 6: Scale (Multi-tenancy) ✅
```

## 신규 모듈 의존 방향

> 참조: `docs/governance_lifecycle.md` Appendix B

```
types.py + governance_types.py (신규)
    ← decision_store.py         (Phase 1)
    ← corpus_version_store.py   (Phase 1)
    ← rule_asset_store.py       (Phase 3)
    ← evidence_analyzer.py      (Phase 2)
    ← promotion_engine.py       (Phase 3)
    ← what_if_simulator.py      (Phase 3)
    ← impact_evaluator.py       (Phase 4)
    ← judgment_service.py       (Phase 4)
    ← lifecycle_events.py       (Phase 4)
    ← multi_tenancy.py          (Phase 6)
```

기존 `types.py ← definition.py ← ...` 의존 방향과 동일 패턴 유지.
신규 모듈은 기존 모듈을 import하되, 기존 모듈은 신규 모듈을 모름.

## 불변 원칙

| 원칙 | 설명 |
|------|------|
| 기존 API 불변 | `RuleCorpus.judge()`, `KernelSchema.validate_relationship()` 시그니처 변경 없음 |
| 포트 기반 확장 | 새 기능은 ABC 포트로 정의, 기존 모듈은 포트 없이도 동작 |
| 선택적 의존 | `DecisionStore`, `RuleAssetStore`는 `None`이면 기존 동작 |
| 테스트 호환 | 기존 테스트 전부 통과 유지 |
| 커널 스펙 불변 | `specs/kernel_schema.toml`, `specs/kernel_rules.toml` 변경 없음 |
