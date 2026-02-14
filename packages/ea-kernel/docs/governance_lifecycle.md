# Governance Lifecycle System

> **Implementation Note**: 
> This document outlines the architectural design. For the current implementation status and features, please refer to:
> - [Implementation Status](governance_lifecycle_todo.md)
> - [Modeling Features & API](modeling_features.md)


비즈니스 로직의 구조적 형태를 정의하는 ea-kernel을 엔터프라이즈 서비스로 확장하기 위한 설계 문서.

## 1. Overview

### 1.1 Core Identity

ea-kernel은 **비즈니스 로직의 구조적 형태(shape)를 정의**한다.

- "무엇이 존재하고, 어떻게 연결되며, 어떤 순서가 허용되는가" — 타입 수준 통제
- 런타임 로직(비즈니스 규칙, 값 제약, 시간)은 범위 밖 — 외부 시스템의 책임

### 1.2 Service Vision

단발성 판단 엔진에서, **판단이 자산으로 축적되고 규칙이 진화하는 순환 시스템**으로 확장.

```
Rule 정의 → 판단 → 결과 축적 → 패턴 탐지 → 규칙 개선 → 재판단
↑                                                        ↓
└────────── 레퍼런스로 자산화 ←──────────────────────────┘
```

핵심 가치:
- **안정성·신뢰도**: deny-by-default + 증거 기반 판단 + 감사 추적
- **레퍼런스 축적**: 프로파일·판단 이력이 쌓일수록 진입장벽
- **모범사례 제공**: 검증된 프로파일 + 규칙 조합을 산업별·도메인별로 제공

### 1.3 Design Principles

| 원칙 | 설명 |
|------|------|
| **Structure over Runtime** | 구조 정의에 집중, 실행 로직은 외부 위임 |
| **Evidence over Opinion** | 모든 판단에 근거(evidence) 첨부 |
| **Immutable Records** | 판단·의사결정은 append-only, 수정 불가 |
| **Deny by Default** | 명시적 허용 없으면 거부 |
| **Progressive Confidence** | 규칙 신뢰도는 증거 축적에 따라 단계적 승격 |
| **Backward Compatible Extension** | 새 요소/규칙 추가 시 기존 모델 보존 |

---

## 2. System Architecture

### 2.1 Six-Stage Lifecycle

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ S1       │     │ S2       │     │ S3       │
│ Rule     │────→│ Judgment │────→│ Decision │
│ Authoring│     │ Execution│     │ Recording│
└──────────┘     └──────────┘     └──────────┘
     ↑                                 │
     │                                 ↓
┌──────────┐     ┌──────────┐     ┌──────────┐
│ S6       │     │ S5       │     │ S4       │
│ Impact   │←────│ Rule     │←────│ Evidence │
│Propagation     │ Evolution│     │ Analysis │
└──────────┘     └──────────┘     └──────────┘
```

| Stage | 책임 | 핵심 산출물 |
|-------|------|-----------|
| S1 Rule Authoring | 규칙을 정의·검토·승인하여 자산으로 등록 | Approved RuleAsset |
| S2 Judgment Execution | 모델링 질문에 근거 기반 판단 | JudgmentReport |
| S3 Decision Recording | 모든 판단을 추적 가능한 형태로 영속화 | Persisted DecisionRecord |
| S4 Evidence Analysis | 축적된 판단에서 패턴과 실효성 분석 | AnalysisReport |
| S5 Rule Evolution | 분석 근거로 규칙 개선·신뢰도 승격 | Evolved Corpus |
| S6 Impact Propagation | 규칙 변경의 기존 모델 영향 평가·전파 | ImpactReport |

### 2.2 Cross-cutting Concerns

| 관심사 | 역할 |
|--------|------|
| **Versioning** | Corpus·Rule·Decision에 버전 부여, 판단 재현 가능 |
| **Provenance** | 모든 자산에 구조화된 출처 체인, 감사 추적 (ea-decision linkage) |
| **Multi-tenancy** | 공유 기반(커널+표준) 위에 테넌트별 확장, 교차 학습 |

### 2.3 Data Flow

```
                        ┌─────────────────┐
                        │  Kernel Schema  │ (L1-L4 types, relations, validity rules)
                        └────────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    ↓            ↓            ↓
             ┌──────────┐ ┌──────────┐ ┌──────────┐
             │ Profile A│ │ Profile B│ │ Profile C│  (domain mappings + rules)
             └────┬─────┘ └────┬─────┘ └────┬─────┘
                  │            │            │
                  └─────┬──────┘            │
                        ↓                   ↓
                 ┌─────────────┐     ┌─────────────┐
                 │ RuleCorpus  │     │ RuleCorpus  │  (kernel rules + profile rules)
                 │ (tenant A)  │     │ (tenant B)  │
                 └──────┬──────┘     └──────┬──────┘
                        │                   │
                        ↓                   ↓
                 ┌─────────────┐     ┌─────────────┐
                 │ Judgment    │     │ Judgment    │  (evidence-based verdicts)
                 │ Engine      │     │ Engine      │
                 └──────┬──────┘     └──────┬──────┘
                        │                   │
                        ↓                   ↓
                 ┌─────────────┐     ┌─────────────┐
                 │ Decision    │     │ Decision    │  (persisted records)
                 │ Store       │     │ Store       │
                 └──────┬──────┘     └──────┬──────┘
                        │                   │
                        └─────┬─────────────┘
                              ↓
                       ┌─────────────┐
                       │ Evidence    │  (cross-tenant analysis)
                       │ Analyzer    │
                       └──────┬──────┘
                              ↓
                       ┌─────────────┐
                       │ Shared      │  (common references)
                       │ Reference   │
                       │ Catalog     │
                       └─────────────┘
```

### 2.4 Type System Overview

이 문서에서 정의하는 새 타입과 기존 타입의 관계.

```
기존 타입 (현재 ea-kernel)              신규 타입 (이 문서에서 정의)
─────────────────────────              ──────────────────────────
KernelValidityRule                     RuleProvenance        (S1)
RuleMetadata                           RuleLifecycle         (S1)
RuleCorpusEntry                        RuleAsset             (S1)
                                       CorpusVersion         (S1/CC)
JudgmentReport ◄──────────────────────►JudgmentContext       (S2)
RuleEvidence
DecisionRecord ◄──────────────────────►DecisionStore (port)  (S3)
DecisionLedger                         JudgmentStatEntry     (S3)

                                       RuleEffectiveness     (S4)
                                       ConflictHotspot       (S4)
                                       UsageProfile          (S4)
                                       AnalysisReport        (S4)

                                       PromotionPath         (S5)
                                       RuleChangeProposal    (S5)
                                       WhatIfResult          (S5)

                                       RuleChangeSet         (S6)
                                       ImpactReport          (S6)
                                       ReEvaluationEntry     (S6)
```

---

## 3. S1: Rule Authoring (규칙 저작)

### 3.1 Definition

규칙을 정의·검토·승인하여, **출처와 생명주기가 추적 가능한 자산으로 등록**하는 단계.

### 3.2 Actors

| Actor | 역할 |
|-------|------|
| Rule Author | 규칙 초안 작성 (표준 문서·도메인 지식 기반) |
| Reviewer | 규칙 검토·승인 |
| System | 품질 검사, 충돌 탐지, 자동 fallback 생성 |

### 3.3 Data Flow

```
Input                          Process                        Output
─────                          ───────                        ──────
표준 문서 (ArchiMate §5.2.1)   → Rule Author: 초안 작성       → RuleAsset (lifecycle=DRAFT)
도메인 전문가 지식              → System: 품질 검사             → QualityReport
S5 경험적 패턴                  → Reviewer: 검토·승인           → RuleAsset (lifecycle=APPROVED)
                               → System: Corpus 등록           → Updated CorpusVersion
```

### 3.4 Data Model

#### RuleLifecycle

규칙의 생명주기 상태.

```
DRAFT ──→ REVIEW ──→ APPROVED ──→ DEPRECATED
  │          │                        ↑
  └──────────┘                        │
     (반려 시 DRAFT로)            (새 규칙으로 대체 시)
```

```python
class RuleLifecycle(str, Enum):
    DRAFT = "draft"            # 초안 — 판단에 사용되지 않음
    REVIEW = "review"          # 검토 중 — 판단에 사용되지 않음
    APPROVED = "approved"      # 승인 — 활성 판단에 사용됨
    DEPRECATED = "deprecated"  # 폐기 — 새 판단에 사용되지 않음, 이력 유지
```

#### RuleProvenance

규칙의 출처 체인. "이 규칙이 왜 존재하는가?"에 대한 감사 가능한 근거.

```python
@dataclass(frozen=True)
class RuleProvenance:
    standard_ref: str          # "ArchiMate 3.2 §5.2.1" — 근거 표준 조항
    decision_ref: str          # "start-small:123" — ea-decision의 Intent/Choice ID
    interpretation: str        # "Business Actor는 능동적 구조..." — 저작자 해석
    author: str                # "kim@company.com"
    reviewer: str              # "park@company.com" (빈 문자열이면 미검토)
    created_at: str            # ISO 8601 — 최초 작성 시점
    approved_at: str           # ISO 8601 — 승인 시점 (빈 문자열이면 미승인)
    supersedes: str            # 이전 규칙 ID (빈 문자열이면 신규)
```

#### RuleAsset

규칙 + 메타데이터 + 출처 + 생명주기를 하나로 묶은 자산 단위.

```python
@dataclass(frozen=True)
class RuleAsset:
    entry: RuleCorpusEntry       # 기존: rule + metadata
    provenance: RuleProvenance   # 신규: 출처 체인
    lifecycle: RuleLifecycle     # 신규: 생명주기 상태
    asset_version: int           # 이 규칙의 개정 번호 (1, 2, 3...)
```

#### CorpusVersion

판단 재현 가능성을 위한 Corpus 스냅샷 식별자.

```python
@dataclass(frozen=True)
class CorpusVersion:
    id: str                      # uuid4
    kernel_schema_version: str   # "2.5.0"
    profile_rules_hash: str      # SHA256 — 프로파일 규칙 집합의 해시
    empirical_rules_hash: str    # SHA256 — 경험적 규칙 집합의 해시
    total_rules: int
    active_rules: int            # lifecycle=APPROVED인 규칙 수
    created_at: str              # ISO 8601
    description: str
```

### 3.5 Design Rationale Support (ea-decision linkage)

규칙의 근거(Why)를 별도의 Support Layer인 `ea-decision`에서 관리한다.
- **Intent**: 해결하려는 문제나 달성하려는 목표 (Goal/Problem)
- **Choice**: 선택한 아키텍처적 방향 (Architecuture Decision)
- **Linkage**: `RuleProvenance.decision_ref`를 통해 규칙과 근거를 연결하여 "Why"를 설명한다.

### 3.6 Current State (기존 코드 매핑)

| 구성 요소 | 모듈 | 상태 |
|-----------|------|------|
| 규칙 정의 | `ProfileBuilder.allow()/.deny()` | ✅ |
| TOML 로딩 | `profile_loader.py` | ✅ |
| 빌드 검증 | `ProfileBuilder._validate()` | ✅ |
| 품질 게이트 | `profile_quality_gate.check_profile_quality()` | ✅ |
| Dead rule 탐지 | `profile_quality_gate._find_dead_rules()` | ✅ |
| 동일 priority 충돌 탐지 | `profile_quality_gate._find_conflicting_rules()` | ✅ |
| Missing fallback 탐지 | `profile_quality_gate._find_missing_fallbacks()` | ✅ |
| 프로파일 영속화 | `SQLiteProfileStore` | ✅ |
| 프로파일 버전/태그 | `ProfileVersion`, `ProfileTag` | ✅ |
| Audit hook | `StoreAuditHook` (store 전 품질 검사) | ✅ |
| **규칙 생명주기** | `RuleLifecycle` | ✅ |
| **출처 체인** | `RuleProvenance` | ✅ |
| **Corpus 버전** | `CorpusVersionStore` | ✅ |

### 3.7 Target Design

#### 3.7.1 RuleAsset 저장소

`SQLiteProfileStore` 패턴을 재활용. 규칙 자산을 독립적으로 영속화.

```
Interface: RuleAssetStore (port)
  store(asset: RuleAsset) → str (asset_id)
  get(asset_id: str) → RuleAsset | None
  by_rule_id(rule_id: str) → list[RuleAsset]  # 버전 이력
  by_lifecycle(lifecycle: RuleLifecycle) → list[RuleAsset]
  transition(asset_id: str, to: RuleLifecycle, actor: str) → RuleAsset
```

#### 3.7.2 Corpus 스냅샷

규칙 변경 시 Corpus 전체의 스냅샷을 생성하여 판단 재현 가능.

```
Interface: CorpusVersionStore (port)
  snapshot(corpus: RuleCorpus, description: str) → CorpusVersion
  get(version_id: str) → CorpusVersion | None
  latest() → CorpusVersion | None
  restore(version_id: str) → RuleCorpus
```

#### 3.7.3 생명주기 전이 규칙

```
DRAFT → REVIEW:      author 본인 가능
REVIEW → APPROVED:   reviewer ≠ author, 품질 게이트 통과 필수
REVIEW → DRAFT:      반려 사유 필수
APPROVED → DEPRECATED: superseding rule ID 필수
```

### 3.8 Key Decisions

| 결정 | 선택 | 근거 |
|------|------|------|
| RuleAsset vs RuleMetadata 확장 | 별도 RuleAsset 래퍼 | 기존 RuleCorpusEntry 불변 유지, 생명주기는 자산 관리 관심사 |
| CorpusVersion 생성 시점 | 규칙 APPROVED 전이 시 자동 | 판단 재현에 필요한 최소 빈도 |
| 출처 체인 필수 여부 | APPROVED 전이 시 필수, DRAFT/REVIEW에서는 선택 | 초안 단계의 진입 장벽 낮춤 |

---

## 4. S2: Judgment Execution (판단 실행)

### 4.1 Definition

모델링 질문에 대해, **활성 Corpus의 근거에 기반한 판단을 내리고 컨텍스트를 첨부**하는 단계.

### 4.2 Actors

| Actor | 역할 |
|-------|------|
| Modeler | 모델링 질문 제출 (triple) |
| AI Agent | 자동 추천·설명 |
| System | 판단 실행, 증거 수집 |

### 4.3 Data Flow

```
Input                          Process                           Output
─────                          ───────                           ──────
Triple (src, tgt, rel)         → Layer constraint 검사            → JudgmentReport
Active Corpus (versioned)      → Rule matching (priority order)     (verdict, evidence,
                               → Condition evaluation               confidence, conflicts)
                               → Evidence collection              → JudgmentContext
                               → Reference statistics 첨부          (corpus_version, stats,
                                                                    similar_cases)
```

### 4.4 Data Model

#### JudgmentContext

판단에 레퍼런스 통계를 첨부하는 보강 컨텍스트.

```python
@dataclass(frozen=True)
class JudgmentContext:
    corpus_version_id: str           # 어떤 corpus 버전으로 판단했는가
    profile_name: str                # 어떤 프로파일 컨텍스트인가 (빈 문자열이면 커널 수준)
    requestor: str                   # 누가 요청했는가
    requested_at: str                # ISO 8601
    reference_stats: ReferenceStats  # 유사 판단 통계
```

#### ReferenceStats

동일 triple 또는 유사 패턴에 대한 축적된 판단 통계.

```python
@dataclass(frozen=True)
class ReferenceStats:
    exact_match_count: int           # 동일 triple 판단 횟수
    exact_allow_rate: float          # 동일 triple 허용 비율
    pattern_match_count: int         # 유사 패턴 판단 횟수
    pattern_allow_rate: float        # 유사 패턴 허용 비율
    override_count: int              # override 횟수
    profiles_allowing: tuple[str, ...]  # 이 triple을 허용하는 프로파일 목록
```

### 4.5 Current State

| 구성 요소 | 모듈 | 상태 |
|-----------|------|------|
| 스키마 검증 | `KernelSchema.validate_relationship()` | ✅ 탄탄 |
| 증거 기반 판단 | `RuleCorpus.judge()` | ✅ 탄탄 |
| 레이어 제약 선검사 | `LayerConstraint` | ✅ |
| Cross-domain 충돌 탐지 | `RuleCorpus.detect_conflicts()` | ✅ |
| AI 추천 | `AIDecisionInterface.recommend_relations/targets()` | ✅ |
| 설명 생성 | `AIDecisionInterface.explain()` | ✅ |
| **Corpus 버전 추적** | `CorpusVersionStore` | ✅ |
| **레퍼런스 통계** | `ReferenceStats` | ✅ |

### 4.6 Target Design

#### 4.6.1 판단 파이프라인

기존 `RuleCorpus.judge()` 위에 컨텍스트 보강 계층.

```
Interface: JudgmentService
  judge(triple, corpus_version, requestor) → (JudgmentReport, JudgmentContext)
  judge_batch(triples, corpus_version, requestor) → list[(JudgmentReport, JudgmentContext)]
```

내부 흐름:
1. `RuleCorpus.judge()` 호출 → `JudgmentReport`
2. `DecisionStore`에서 동일 triple 이력 조회 → `ReferenceStats` 계산
3. `CorpusVersion` 기록 → `JudgmentContext` 조립
4. `(JudgmentReport, JudgmentContext)` 반환, 동시에 S3으로 자동 전달

### 4.7 Key Decisions

| 결정 | 선택 | 근거 |
|------|------|------|
| 기존 judge() 수정 vs 래핑 | 래핑 (JudgmentService) | 기존 RuleCorpus.judge() 불변 유지, 서비스 계층에서 보강 |
| ReferenceStats 계산 시점 | 판단 시 실시간 | 캐싱 가능하지만 최신성 보장이 우선 |
| Batch API | 지원 | 모델 전체 검증 시 N개 triple 일괄 판단 필요 |

---

## 5. S3: Decision Recording (판단 기록)

### 5.1 Definition

모든 판단을 **영속적이고 추적 가능한 형태로 축적**하여, 분석·감사·재현의 기반을 만드는 단계.

### 5.2 Actors

| Actor | 역할 |
|-------|------|
| System | 판단 결과를 자동으로 기록 (S2 → S3 자동 연결) |

### 5.3 Data Flow

```
Input                          Process                        Output
─────                          ───────                        ──────
JudgmentReport                 → DecisionRecord 생성           → Persisted DecisionRecord
JudgmentContext                → DecisionStore에 영속화        → 인덱스 갱신
                               → JudgmentStat 집계 갱신          (triple, actor, time,
                                                                 corpus_version, profile)
```

### 5.4 Data Model

#### DecisionStore (port)

`SQLiteProfileStore` 패턴의 Decision 전용 영속화 포트.

```python
class DecisionStore(ABC):
    """Abstract storage port for decision persistence."""

    @abstractmethod
    def initialize(self) → None: ...

    @abstractmethod
    def close(self) → None: ...

    @abstractmethod
    def record(self, decision: DecisionRecord,
               context: JudgmentContext) → str: ...  # decision_id

    @abstractmethod
    def get(self, decision_id: str) → DecisionRecord | None: ...

    @abstractmethod
    def by_triple(self, source: str, target: str,
                  relation: str) → list[DecisionRecord]: ...

    @abstractmethod
    def by_corpus_version(self, version_id: str) → list[DecisionRecord]: ...

    @abstractmethod
    def by_time_range(self, start: str, end: str) → list[DecisionRecord]: ...

    @abstractmethod
    def by_actor(self, actor: str) → list[DecisionRecord]: ...

    @abstractmethod
    def count_by_triple(self, source: str, target: str,
                        relation: str) → JudgmentStatEntry: ...
```

#### JudgmentStatEntry

단일 triple에 대한 판단 통계 집계.

```python
@dataclass(frozen=True)
class JudgmentStatEntry:
    source: str
    target: str
    relation: str
    total_count: int
    allow_count: int
    deny_count: int
    override_count: int
    last_judged_at: str             # ISO 8601
    last_corpus_version_id: str
```

### 5.5 Current State (Completed in Phase 1 & 5)
 
| 구성 요소 | 모듈 | 상태 |
|-----------|------|------|
| 의사결정 기록 | `DecisionLedger.record()` | ✅ |
| Triple 인덱스 | `DecisionLedger._triple_index` | ✅ |
| 시간/행위자 조회 | `query()` via `DecisionQueryOptions` | ✅ |
| Override 분류 | `overrides()` | ✅ |
| **영속화** | `SQLiteDecisionStore` | ✅ |
| **자동 기록 (S2→S3 연결)** | `JudgmentService` 자동 기록 | ✅ |
| **Corpus 버전 연결** | `StoredDecisionRecord` | ✅ |
| **통계 집계** | `JudgmentStatistics` (view/table) | ✅ |

### 5.6 Target Design (Implemented)

#### 5.6.1 SQLite 스키마

(Implemented as designed in `SQLiteDecisionStore`)

#### 5.6.2 DecisionLedger 확장

Legacy `DecisionLedger` is maintained for backward compatibility, but `DecisionStore` is the primary persistence layer.

---

## 6. S4: Evidence Analysis (근거 분석)

### 6.1 Definition

축적된 판단에서 **패턴을 탐지하고, 규칙의 실효성을 평가하여, 규칙 진화의 근거**를 만드는 단계.

### 6.5 Current State (Completed in Phase 2 & 5)

| 구성 요소 | 모듈 | 상태 |
|-----------|------|------|
| Override 패턴 탐지 | `DecisionLedger.override_patterns()` | ✅ |
| Empirical 변환 | `DecisionLedger.to_empirical_entries()` | ✅ |
| Dead rule 탐지 | `profile_quality_gate._find_dead_rules()` | ✅ |
| Cross-domain 충돌 | `RuleCorpus.detect_conflicts()` | ✅ |
| **런타임 실효성 통계** | `EvidenceAnalyzer.analyze_rule_effectiveness()` | ✅ |
| **충돌 핫스팟 트렌드** | `EvidenceAnalyzer.detect_conflict_hotspots()` | ✅ |
| **프로파일 사용 통계** | `EvidenceAnalyzer.analyze_usage_profiles()` | ✅ |
| **종합 분석 리포트** | `EvidenceAnalyzer.generate_report()` | ✅ |

---

## 7. S5: Rule Evolution (규칙 진화)

### 7.1 Definition

분석 근거를 바탕으로 **규칙을 개선하고, 경험적 규칙의 신뢰도를 단계적으로 승격**하는 단계.

### 7.5 Current State (Completed in Phase 3 & 5)

| 구성 요소 | 모듈 | 상태 |
|-----------|------|------|
| 승격 후보 식별 | `PromotionEngine.identify_promotion_candidates()` | ✅ |
| 변경 제안 생성 | `PromotionEngine.create_proposal()` | ✅ |
| What-if 시뮬레이션 | `WhatIfSimulator.simulate()` | ✅ |
| **자동화 컨트롤러** | `LifecycleController` | ✅ |
| **이벤트 기반 워크플로우** | `LifecycleEventPort` / `InMemoryEventBus` | ✅ |
| **알림 서비스** | `NotificationService` (Mock) | ✅ |

---

## 8. Integration: Governance System Facade

### 8.1 Definition

전체 거버넌스 라이프사이클(S1~S6)을 통합 관리하는 단일 진입점.

### 8.2 Usage

```python
from ea_kernel.governance import GovernanceSystem

system = GovernanceSystem(data_dir=Path("./data"), schema=base_schema)

# S1: Authoring
draft = system.submit_rule(asset)
approved = system.approve_rule(draft.id, "human:admin")

# S2: Judgment
judgment = system.evaluate("Source", "Target", "relates")

# S4 & S5: Analysis & Automation
report = system.analyze()
system.run_automation()
```

```
EMPIRICAL → CONTEXTUAL:
  min_eval_count=50, min_win_rate=0.8, max_override_rate=0.1,
  min_profiles=1, min_stable_days=30, requires_reviewer=true

CONTEXTUAL → COMMON:
  min_eval_count=200, min_win_rate=0.9, max_override_rate=0.05,
  min_profiles=3, min_stable_days=90, requires_reviewer=true

COMMON → UNIVERSAL:
  min_eval_count=500, min_win_rate=0.95, max_override_rate=0.02,
  min_profiles=5, min_stable_days=180, requires_reviewer=true
  + standard_ref 매핑 필수 (provenance.standard_ref 비어있지 않음)
```

#### RuleChangeProposal

규칙 변경 제안서. What-if 결과를 포함.

```python
class RuleChangeType(str, Enum):
    CREATE = "create"            # 신규 규칙 (empirical에서 승격)
    MODIFY = "modify"            # 기존 규칙 수정 (priority, pattern 등)
    PROMOTE = "promote"          # 신뢰도 승격
    DEPRECATE = "deprecate"      # 규칙 폐기

@dataclass(frozen=True)
class RuleChangeProposal:
    id: str                       # uuid4
    change_type: RuleChangeType
    rule_id: str                  # 대상 규칙 ID (CREATE면 새 ID)
    rationale: str                # 변경 사유
    evidence_summary: str         # 분석 근거 요약
    what_if: WhatIfResult         # 시뮬레이션 결과
    proposed_by: str              # 제안자 (system 또는 사람)
    created_at: str
    status: str                   # "pending" | "approved" | "rejected"
```

#### WhatIfResult

규칙 변경 시뮬레이션 결과. "이 변경을 적용하면 무엇이 바뀌는가?"

```python
@dataclass(frozen=True)
class VerdictChange:
    source: str
    target: str
    relation: str
    old_verdict: bool
    new_verdict: bool
    affected_rule_id: str

@dataclass(frozen=True)
class WhatIfResult:
    total_triples_evaluated: int     # 시뮬레이션에서 평가한 triple 수
    verdict_unchanged: int
    verdict_changed: int
    changes: tuple[VerdictChange, ...]
    new_conflicts: int               # 새로 발생하는 충돌 수
    resolved_conflicts: int          # 해결되는 충돌 수
    net_conflict_delta: int          # new_conflicts - resolved_conflicts
```

### 7.5 Current State

| 구성 요소 | 모듈 | 상태 |
|-----------|------|------|
| Empirical 생성 | `DecisionLedger.to_empirical_entries()` | ✅ 기초 |
| Corpus immutable 확장 | `RuleCorpus.with_profile_rules()` | ✅ |
| Profile diff | `profile_diff.diff_profiles()` | ✅ |
| Profile extend/subset | `profile_composer.extend()/subset()` | ✅ |
| Drift 탐지 | `ProfileAuditor.detect_drift()` | ✅ |
| **신뢰도 승격 경로** | `PromotionEngine` + API | ✅ |
| **승격 조건 검증** | `PromotionCriteria` | ✅ |
| **What-if 시뮬레이션** | `WhatIfSimulator` + API | ✅ |
| **변경 제안서 관리** | `RuleChangeProposal` + API | ✅ |

### 7.6 Target Design

#### 7.6.1 WhatIf 시뮬레이터

```
Interface: WhatIfSimulator
  simulate_rule_change(
    corpus: RuleCorpus,
    change: KernelValidityRule,       # 변경할 규칙
    change_type: RuleChangeType,
  ) → WhatIfResult

  simulate_promotion(
    corpus: RuleCorpus,
    rule_id: str,
    new_confidence: RuleConfidence,
  ) → WhatIfResult
```

내부 흐름:
1. 현재 corpus에서 모든 concrete entity pair × relation 조합 추출
2. 변경 전 verdict 계산 (기존 corpus)
3. 변경 후 corpus 생성 (변경 적용)
4. 변경 후 verdict 계산
5. 차이 비교 → `WhatIfResult`

#### 7.6.2 PromotionEngine

```
Interface: PromotionEngine
  check_eligibility(
    rule_id: str,
    effectiveness: RuleEffectiveness,
    criteria: PromotionCriteria,
  ) → bool

  propose_promotions(
    analysis: AnalysisReport,
    criteria: tuple[PromotionCriteria, ...],
  ) → tuple[RuleChangeProposal, ...]
```

#### 7.6.3 규칙 진화 파이프라인

```
AnalysisReport
    │
    ↓
PromotionEngine.propose_promotions()
    │
    ↓
RuleChangeProposal[] (status=pending)
    │
    ↓
각 proposal에 대해 WhatIfSimulator.simulate()
    │
    ↓
Reviewer 검토 (WhatIfResult 확인)
    │
    ├─ approved → RuleAsset 전이 (S1) → New CorpusVersion
    └─ rejected → 반려 사유 기록
```

### 7.7 Key Decisions

| 결정 | 선택 | 근거 |
|------|------|------|
| What-if 범위 | 전체 entity pair 대상 (brute force) | TopologyGraph._build_adjacency()와 동일 방식, 규모가 커지면 sampling |
| 승격 자동화 수준 | 제안은 자동, 승인은 수동 | UNIVERSAL 승격의 경우 표준 매핑이 필요하므로 완전 자동화 불가 |
| 변경 제안서 영속화 | SQLite | 감사 추적 필요 |

---

## 8. S6: Impact Propagation (영향 전파)

### 8.1 Definition

규칙 변경이 **기존 모델과 판단 이력에 미치는 영향을 평가하고, 변경 사항을 전파**하는 단계.

### 8.2 Actors

| Actor | 역할 |
|-------|------|
| System | 변경 영향 자동 평가, 재검증 실행 |
| Modeler | 영향 보고서 확인, 모델 수정 |

### 8.3 Data Flow

```
Input                          Process                          Output
─────                          ───────                          ──────
CorpusVersion (old → new)      → 변경된 규칙 추출               → RuleChangeSet
DecisionStore (기존 판단)      → 영향받는 triple 필터링          → ImpactReport
                               → 새 corpus로 재판단
                               → verdict 변경 목록 생성
                               → 변경 알림 발행
```

### 8.4 Data Model

#### RuleChangeSet

Corpus 버전 간 변경 내역.

```python
@dataclass(frozen=True)
class RuleChangeSetEntry:
    rule_id: str
    change_type: str             # "added" | "removed" | "modified"
    field: str                   # 변경 필드 (modified인 경우)
    old_value: str
    new_value: str

@dataclass(frozen=True)
class RuleChangeSet:
    from_version_id: str
    to_version_id: str
    entries: tuple[RuleChangeSetEntry, ...]
    created_at: str
```

#### ReEvaluationEntry

단일 triple의 재판단 결과.

```python
@dataclass(frozen=True)
class ReEvaluationEntry:
    source: str
    target: str
    relation: str
    old_verdict: bool
    old_rule_id: str             # 기존 winning rule
    new_verdict: bool
    new_rule_id: str             # 새 winning rule
    changed: bool                # old_verdict ≠ new_verdict
```

#### ImpactReport

규칙 변경의 종합 영향 보고서.

```python
@dataclass(frozen=True)
class ImpactReport:
    id: str                               # uuid4
    change_set: RuleChangeSet
    total_re_evaluated: int
    verdict_unchanged: int
    verdict_changed: int
    entries: tuple[ReEvaluationEntry, ...]  # changed=True인 것만
    created_at: str
```

### 8.5 Current State

| 구성 요소 | 모듈 | 상태 |
|-----------|------|------|
| 토폴로지 그래프 | `TopologyGraph` | ✅ |
| 구조적 영향 분석 | `TopologyGraph.impact_analysis()` | ✅ |
| M0 모델 검증 | `InstanceValidator.validate_model()` | ✅ |
| Batch 검증 + 컨텍스트 | `AIDecisionInterface.validate_model_with_context()` | ✅ |
| Rule 검증 | `RuleVerifier.verify_all()` | ✅ |
| Profile diff | `profile_diff.diff_profiles()` | ✅ |
| Drift 탐지 | `ProfileAuditor.detect_drift()` | ✅ |
| **Corpus 버전 간 verdict 비교** | `ImpactEvaluator` | ✅ |
| **기존 판단 재검증 자동화** | `ImpactEvaluator` | ✅ |
| **변경 알림/이벤트** | `LifecycleEventPort` | ✅ |

### 8.6 Target Design

#### 8.6.1 ImpactEvaluator

```
Interface: ImpactEvaluator
  evaluate(
    old_corpus: RuleCorpus,
    new_corpus: RuleCorpus,
    decision_store: DecisionStore,
  ) → ImpactReport

  evaluate_for_triples(
    old_corpus: RuleCorpus,
    new_corpus: RuleCorpus,
    triples: tuple[tuple[str, str, str], ...],
  ) → ImpactReport
```

내부 흐름:
1. `RuleChangeSet` 계산: old corpus 규칙과 new corpus 규칙의 diff
2. 변경된 규칙에 영향받는 triple 필터링 (패턴 매칭)
3. 각 triple에 대해 old/new corpus 양쪽으로 `validate_relationship()`
4. verdict 차이 수집 → `ImpactReport`

#### 8.6.2 이벤트 인터페이스

```
Interface: LifecycleEventPort
  on_corpus_updated(old_version: CorpusVersion, new_version: CorpusVersion) → None
  on_impact_detected(report: ImpactReport) → None
  on_rule_promoted(proposal: RuleChangeProposal) → None
```

초기 구현은 콜백 함수. 추후 메시지 큐로 확장 가능.

### 8.7 Key Decisions

| 결정 | 선택 | 근거 |
|------|------|------|
| 재평가 범위 | 변경 규칙의 패턴에 매칭되는 triple만 | 전체 재평가는 비용이 크므로, 영향 범위 한정 |
| 이벤트 인터페이스 | 콜백 port (ABC) | zero dependency 원칙 유지, 외부 시스템이 구현 주입 |
| ImpactReport 영속화 | SQLite | 감사 추적 |

---

## 9. Cross-cutting: Versioning (버전 관리)

### 9.1 Definition

모든 핵심 자산에 **버전을 부여하여 판단의 재현 가능성과 변경 추적**을 보장.

### 9.2 Versioning Targets

| 자산 | 현재 버전 관리 | 목표 |
|------|--------------|------|
| Kernel Schema | `KERNEL_VERSION` 문자열 | ✅ 충분 (드물게 변경) |
| Profile | `ProfileVersion` (SQLite, parent_id, content_hash, tag) | ✅ 충분 |
| Rule (개별) | `RuleAsset.asset_version` | ✅ |
| Corpus (전체) | `CorpusVersion` (스냅샷 ID) | ✅ |
| Decision | `DecisionRecord.corpus_version_id` | ✅ |

### 9.3 Reproducibility Contract

```
동일한 (triple, corpus_version) → 동일한 JudgmentReport

이 계약이 보장되면:
- "6개월 전 이 판단을 왜 내렸는가?" → corpus 복원 후 재실행
- "규칙 변경 전후 차이" → 두 corpus 버전으로 비교
- "이 프로파일이 v1.2일 때 유효했던 것이 v1.3에서 깨졌나?" → drift 탐지
```

### 9.4 Version Dependency Chain

```
KernelSchema v2.5.0
    └── Profile "ArchiMate" v3.2.1
         └── RuleAsset "arch-allow-05" v3
              └── CorpusVersion "cv-2025-06-15"
                   └── DecisionRecord "dec-abc-123" (corpus_version_id = "cv-2025-06-15")
```

---

## 10. Cross-cutting: Provenance (출처 추적)

### 10.1 Definition

모든 자산과 판단에 **구조화된 출처 체인을 부여하여 감사(audit) 가능성**을 보장.

### 10.2 Provenance Layers

| 자산 | 추적 대상 | 현재 | 목표 |
|------|----------|------|------|
| Rule | 표준 조항 → 해석 → 저작 → 검토 → 승인 | `RuleProvenance` | ✅ |
| Profile | 빌드 → 품질 검사 → 등록 → 사용 | `ProfileVersion` | ✅ |
| Decision | 요청자 → corpus 버전 → verdict → override 사유 | `JudgmentContext` | ✅ |
| Analysis | 분석 기간 → corpus → 결과 | `AnalysisReport` | ✅ |
| Evolution | 제안 → 시뮬레이션 → 검토 → 승인 | `RuleChangeProposal` | ✅ |

### 10.3 Audit Query Scenarios

```
Q: "이 규칙은 왜 존재하는가?"
A: RuleAsset.provenance.standard_ref → 표준 조항
   RuleAsset.provenance.interpretation → 저작자 해석
   RuleAsset.provenance.approved_at → 승인 시점

Q: "이 판단은 왜 이렇게 내려졌는가?"
A: DecisionRecord → JudgmentReport.evidence → winning rule
   JudgmentContext.corpus_version_id → 당시 corpus 복원 가능
   JudgmentContext.reference_stats → 당시 레퍼런스 통계

Q: "이 규칙이 변경된 이력은?"
A: RuleAssetStore.by_rule_id(rule_id) → asset_version 순으로 이력
   각 version의 provenance.supersedes → 변경 체인

Q: "이 프로파일은 언제부터 reference 등급이었나?"
A: UsageProfile 이력 → reference_grade 전이 시점
```

---

## 11. Cross-cutting: Multi-tenancy (다중 테넌트)

### 11.1 Definition

**공유 기반(커널 + 표준 프로파일) 위에 테넌트별 확장**을 허용하고, 익명화된 교차 학습으로 공통 레퍼런스를 성장.

### 11.2 Tenant Isolation Model

```
┌───────────────────────────────────────────────────────┐
│ Shared Base (읽기 전용)                                │
│  ├── Kernel Schema v2.5.0                              │
│  ├── Built-in Profiles (ArchiMate, TOGAF, ...)        │
│  ├── Kernel Rules (confidence=UNIVERSAL)               │
│  └── Shared Reference Catalog                          │
├───────────────────────────────────────────────────────┤
│ Tenant A                    │ Tenant B                 │
│  ├── Custom Profile(s)      │  ├── Custom Profile(s)   │
│  ├── Tenant Rules           │  ├── Tenant Rules        │
│  │   (overlay on shared)    │  │   (overlay on shared)  │
│  ├── Decision Store         │  ├── Decision Store      │
│  └── Analysis Reports       │  └── Analysis Reports    │
└───────────────────────────────────────────────────────┘
```

### 11.3 Cross-tenant Learning

```
Tenant A: override pattern X 반복 (n=15)
Tenant B: override pattern X 반복 (n=8)
    │
    ↓ (익명화 집계)
Cross-tenant Analysis:
    pattern X가 2개 이상 테넌트에서 반복
    │
    ↓
Shared Reference Catalog에 후보 등록
    │
    ↓
Central Reviewer 검토 → Shared Base에 규칙 추가 (confidence=COMMON)
```

### 11.4 Corpus 합성 (Tenant Resolution Order)

테넌트의 활성 corpus는 계층적 합성:

```
Effective Corpus = Shared Base Rules
                   + Profile Rules (선택한 프로파일)
                   + Tenant Custom Rules (overlay)
                   + Empirical Rules (테넌트 학습 결과)

충돌 시 우선순위:
  Tenant Custom (priority 보존) > Profile Rules > Shared Base > Empirical
```

### 11.5 Data Isolation
 
| 데이터 | 격리 수준 |
|--------|----------|
| Kernel Schema | 공유 (전 테넌트 동일) |
| Built-in Profiles | 공유 (읽기 전용) |
| Custom Profiles | 테넌트별 격리 |
| Decision Records | 테넌트별 격리 (교차 접근 불가) |
| Analysis Reports | 테넌트별 격리 |
| Cross-tenant Insights | 익명화 집계만 공유 |

### 11.6 Current State (Completed in Phase 6)

| 구성 요소 | 모듈 | 상태 |
|-----------|------|------|
| **Tenant Manager** | `MultiTenantManager` | ✅ |
| **Tenant Isolation** | `GovernanceSystem` factories | ✅ |
| **Shared Kernel Dist.** | `MultiTenantManager.sync_shared_schema` | ✅ |
| **Cross-tenant Agg.** | `MultiTenantManager.aggregate_rule_adoption` | ✅ |
| **Pattern Discovery** | `MultiTenantManager.find_common_patterns` | ✅ |

---

## 12. Implementation Roadmap

### 12.1 Phase 구성

단계별 구현은 각 Phase가 독립적으로 가치를 내도록 구성.

```
Phase 1: Foundation (S3 + Versioning)
  "판단 기록이 사라지지 않는다"
  ├── DecisionStore (SQLite)
  ├── CorpusVersion 스냅샷
  ├── DecisionLedger._store 포트 연결
  └── 기존 테스트 호환 유지

Phase 2: Insight (S4)
  "축적된 판단에서 의미가 나온다"
  ├── EvidenceAnalyzer
  ├── RuleEffectiveness 계산
  ├── ConflictHotspot 탐지
  ├── UsageProfile 통계
  └── AnalysisReport 생성

Phase 3: Governance (S1 + S5)
  "규칙이 관리되고 진화한다"
  ├── RuleAsset + RuleProvenance + RuleLifecycle
  ├── RuleAssetStore
  ├── PromotionEngine + PromotionCriteria
  ├── WhatIfSimulator
  └── RuleChangeProposal 관리

Phase 4: Propagation (S6 + S2 보강)
  "변경의 영향을 알 수 있다"
  ├── ImpactEvaluator
  ├── RuleChangeSet diff
  ├── JudgmentService (S2 보강)
  ├── ReferenceStats 첨부
  └── LifecycleEventPort

Phase 5: Automation (Controller)
  "거버넌스가 자동으로 돈다"
  ├── LifecycleController
  ├── Event-Driven Workflow
  ├── Auto-Promotion Logic
  └── Notification Service (Mock)

Phase 6: Scale (Multi-tenancy)
  "여러 조직이 함께 사용한다"
  ├── Tenant isolation
  ├── Corpus 합성 (overlay)
  ├── Cross-tenant analysis
  └── Shared Reference Catalog
```

### 12.2 Phase 의존 관계

```
Phase 1 ──→ Phase 2 ──→ Phase 3
                │            │
                └────────────┴──→ Phase 4 ──→ Phase 5
```

### 12.3 기존 코드 호환성 원칙

| 원칙 | 설명 |
|------|------|
| 기존 API 불변 | `RuleCorpus.judge()`, `KernelSchema.validate_relationship()` 시그니처 변경 없음 |
| 포트 기반 확장 | 새 기능은 ABC 포트로 정의, 기존 모듈은 포트 없이도 동작 |
| 선택적 의존 | `DecisionStore`, `RuleAssetStore`는 `None`이면 기존 동작 |
| 테스트 호환 | 기존 754 테스트 전부 통과 유지 |

---

## Appendix A: Module Mapping

새 타입/모듈의 예상 파일 배치.

```
src/ea_kernel/
├── types.py                    # 기존 + CorpusVersion, JudgmentStatEntry
├── governance_types.py         # 신규: RuleAsset, RuleProvenance, RuleLifecycle,
│                               #       RuleEffectiveness, ConflictHotspot, UsageProfile,
│                               #       AnalysisReport, PromotionCriteria, RuleChangeProposal,
│                               #       WhatIfResult, VerdictChange, RuleChangeSet,
│                               #       ImpactReport, ReEvaluationEntry, JudgmentContext,
│                               #       ReferenceStats
├── decision_store.py           # 신규: DecisionStore ABC + SQLiteDecisionStore
├── decision_ledger.py          # 확장: _store 포트 추가
├── corpus_version_store.py     # 신규: CorpusVersionStore
├── evidence_analyzer.py        # 신규: EvidenceAnalyzer
├── promotion_engine.py         # 신규: PromotionEngine + PromotionCriteria
├── what_if_simulator.py        # 신규: WhatIfSimulator
├── impact_evaluator.py         # 신규: ImpactEvaluator
├── judgment_service.py         # 신규: JudgmentService (S2 래핑 + S3 자동 연결)
├── rule_asset_store.py         # 신규: RuleAssetStore ABC + SQLiteRuleAssetStore
├── lifecycle_events.py         # 신규: LifecycleEventPort ABC
└── ...기존 모듈 유지
```

## Appendix B: Dependency Direction (신규 모듈)

```
types.py + governance_types.py
    ← decision_store.py (types만 import)
    ← corpus_version_store.py (types만 import)
    ← rule_asset_store.py (governance_types만 import)
    ← evidence_analyzer.py (types + governance_types, rule_corpus lazy)
    ← promotion_engine.py (governance_types만 import)
    ← what_if_simulator.py (types + governance_types, rule_corpus lazy)
    ← impact_evaluator.py (types + governance_types, rule_corpus lazy)
    ← judgment_service.py (types + governance_types, rule_corpus + decision_store lazy)
    ← lifecycle_events.py (governance_types만 import)
```

기존 `types.py ← definition.py ← ...` 의존 방향과 동일 패턴 유지.
신규 모듈은 기존 모듈을 import하되, 기존 모듈은 신규 모듈을 모름.
