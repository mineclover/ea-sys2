# Decision Layer -- Role Specialization

> 정규 레이어 정의: `packages/ea-kernel/docs/system_spec_layers.md`
> 코딩 컨벤션: `packages/ea-decision/CLAUDE.md`

---

## 1. 레이어 정체성

### 비유: Research Lab & Archives

Decision 레이어는 시스템의 **연구소이자 기록보관소**다. Kernel이 "What"(무엇이 존재하는가)을, Flow가 "How"(어떻게 실행하는가)를 정의한다면, Decision은 **"Why"(왜 그 결정을 내렸는가)**를 정의한다. 모든 설계 판단은 증거로 뒷받침되어야 하고, 확정된 결정은 불변 기록으로 보존된다.

### Design Thinking 기반 4단계 프로세스

```
Define Intent --> Diverge --> Converge --> Utilize
   (Why)         (Could Be)   (Should Be)   (Is)
```

| 단계 | 역할 | 산출물 |
|:-----|:-----|:------|
| **Define Intent** | 결정의 방향과 맥락 설정 | `Intent` (frozen) |
| **Diverge** | 옵션 생성, 조사, 질문 | `ChoiceOption`, `ResearchNote`, `Question`, `Option` |
| **Converge** | 옵션 선택, 보고서 확정 | `Choice`, `DesignDecision`, `DesignReport` |
| **Utilize** | 결정 결과를 커널 아티팩트로 변환 | `DecisionResult`, `RuleProvenance` |

### 3-Layer Narrative Abstraction

Decision 레이어의 내부 구조는 3단계 서사 추상화를 따른다.

| 계층 | 책임 | 불변성 | 모듈 |
|:-----|:-----|:------|:-----|
| **N1 Vocabulary** | 불변 타입 정의 -- 시스템 어휘 | frozen | `types.py`, `evidence.py`, `pattern.py` (DecisionPattern) |
| **N2 Process** | 워크플로우 실행 -- Topic aggregate root | mutable (aggregate만) | `topic.py`, `process.py`, `lifecycle.py`, `evaluation.py` |
| **N3 Integration** | 외부 연동 -- Kernel bridge, 영속화 | lazy import | `kernel_bridge.py`, `repository.py`, `registry.py` |

**N1은 동결된다.** N1 타입(`Intent`, `Choice`, `DecisionResult`, `Evidence`, `DecisionPattern`)은 모두 `frozen=True`이며, 생성 후 변경할 수 없다. N2에서 유일하게 mutable인 것은 Topic aggregate root다. N3는 lazy import로 ea_kernel에 대한 단방향 의존을 유지한다.

### 런타임 엔트리포인트 체인 시작 위치

```
Runtime chain:  decision --> needs --> kernel --> flow
                 ^START
```

Decision은 런타임 엔트리포인트 체인의 **시작점**이다. Infra와 Governance는 체인 노드가 아니라 각각 row 데이터 설계와 시스템 진입점 설계를 담당한다. Decision에서 시작된 의사결정 모델이 Needs로 전달되고, Kernel에서 도메인 제약으로 고정되며, Flow에서 실행 가능한 절차로 표현된다.

---

## 2. 메타-메타 모델 설계

### DecisionSchema 설계 명세

`20-decision.toml`에 정의된 내부 요소를 기반으로 DecisionSchema를 구성한다. 이 스키마는 커널의 `SchemaPort` 호환 형태로 설계되어야 한다.

#### 2.1 서비스 (ActiveStructure) -- 7개 + 경계 Composite 2개

| 요소 | 카테고리 | 역할 |
|:-----|:---------|:-----|
| `DecisionLayer` | Composite | Decision 메타-메타 모델링 경계, 런타임 엔트리 체인 시작 |
| `TopicAggregate` | Composite | Topic aggregate root 컨테이너 -- research, questions, options, report, report_history 그룹화 |
| `DecisionMetaModelRegistry` | ActiveStructure | 의사결정-흐름 메타 엔티티 및 관계 어휘 등록 |
| `DecisionFlowSchemaService` | ActiveStructure | 의사결정 활동 및 전이에 대한 구조적 스키마 유지 |
| `DecisionAgreementService` | ActiveStructure | 의사결정 결과 종결(closure)을 위한 합의 의미론 유지 |
| `DesignThinkingProcessService` | ActiveStructure | Design Thinking 생명주기 단계 오케스트레이터 (`define_intent` -> `diverge` -> `converge` -> `utilize`) |
| `DecisionPatternRegistryService` | ActiveStructure | DecisionPattern 정의 등록 및 조회 관리 (`registry.py`) |
| `DecisionRepositoryService` | ActiveStructure | Topic aggregate JSON 파일 기반 영속화 -- save, retrieve, list (`repository.py`) |
| `KernelBridgeService` | ActiveStructure | 결정 산출물을 커널 모델링 액션으로 변환 -- lazy ea_kernel import (`kernel_bridge.py`) |

#### 2.2 카탈로그 (PassiveStructure) -- 6개

| 카탈로그 | 열거 값 | 대응 타입 |
|:---------|:--------|:---------|
| `DecisionNodeTypeCatalog` | context, option, evaluation, outcome | -- |
| `DecisionRelationTypeCatalog` | 결정 노드 간 관계 유형 | -- |
| `DecisionStateCatalog` | PROPOSED, ACCEPTED, REJECTED, DEPRECATED | `DecisionStatus` |
| `DecisionPhaseCatalog` | DIVERGE, CONVERGE, UTILIZE | `DecisionPhase` |
| `DecisionComplexityCatalog` | TRIVIAL, STRUCTURAL, STRATEGIC | `DecisionComplexity` |
| `DecisionLifecycleStateCatalog` | DRAFT, PROPOSED, ACCEPTED, REJECTED, DEPRECATED, SUPERSEDED | `DecisionLifecycleState` |

#### 2.3 평가 모델 (Assessment) -- 3개

| 모델 | 역할 | 대응 타입 |
|:-----|:-----|:---------|
| `DecisionCriteriaModel` | 옵션 평가 기준 스키마 메타 정의 | `EvaluationCriteria`, `EvaluationDimension` |
| `DecisionHeuristicModel` | 심의 휴리스틱 스키마 메타 정의 | `HeuristicRule` (PatternSchema 내) |
| `DecisionRationaleModel` | 근거 스키마 및 설명 가능성 제약 메타 정의 | `Rationale` (frozen) |

#### 2.4 레코드 (PassiveStructure) -- 21개

**N1 Frozen Records:**

| 레코드 | 설명 |
|:-------|:-----|
| `IntentRecord` | 결정의 출발점 -- id, description, direction, context_refs |
| `ChoiceOptionRecord` | Diverge 단계 산출 -- intent_id, feasibility_score, alignment_score |
| `ChoiceRecord` | Converge 단계 산출 -- selected_option_id, rationale, distance |
| `DecisionResultRecord` | Utilize 단계 산출 -- intent_id, choice_id, outcome_artifact, timestamp |
| `EvidenceRecord` | 구조화된 증거 -- EvidenceType, uri, title, relevance_score |
| `EvidenceCollectionRecord` | Evidence 불변 컬렉션 -- add()가 새 컬렉션 반환 |
| `DecisionPatternRecord` | 패턴 정의 -- complexity, governed_rule_group, inquiry_template, verification_heuristics, outcome_anchors |
| `PatternSchemaRecord` | 패턴 메타-모델 -- PatternType, phases, heuristics, inquiry_template |
| `EvaluationDimensionRecord` | 평가 차원 -- name, description, weight, scale -- EvaluationResult 가중 점수 계산 기준 |
| `RuleProvenanceRecord` | 커널 브릿지 산출 -- decision_ref, report_ref |

**N2 Mutable Records:**

| 레코드 | 설명 |
|:-------|:-----|
| `ResearchNoteRecord` | 마크다운 조사 내용 -- source_url, references, author |
| `QuestionRecord` | reply()를 통한 질의응답 -- text, asked_by, answer, answered_by |
| `OptionRecord` | 후보 해법 -- title, description, evaluation(pros/cons/score) |
| `EvaluationDetailRecord` | 옵션 분석 -- pros, cons, score(0-10), comment |
| `ModelingActionRecord` | 커널 모델 변경 계획 -- action_type, target, description, status, payload |
| `DesignDecisionRecord` | 확정된 결정 -- selected_option_id, rationale, pattern_name, complexity, impact_analysis, status, approver |
| `DesignReportRecord` | 공식 보고서 -- title, summary, decision, modeling_actions, key_evidence_refs |

**기존 범용 레코드:**

| 레코드 | 설명 |
|:-------|:-----|
| `DecisionContextRecord` | 구조화된 의사결정 맥락 인스턴스 |
| `DecisionOptionRecord` | 구조화된 옵션 그래프 인스턴스 |
| `DecisionEvaluationRecord` | 구조화된 평가 인스턴스 |
| `DecisionOutcomeRecord` | 구조화된 최종 결과 인스턴스 |

#### 2.5 행위 단계 (Behavior/Step) -- 9개

| 단계 | 설명 | 선행 단계 |
|:-----|:-----|:---------|
| `CaptureDecisionContextStep` | 의사결정 맥락 노드 물질화 | -- (DecisionRequestedEvent에 의해 트리거) |
| `BuildOptionGraphStep` | 옵션 노드 그래프 물질화 | CaptureDecisionContextStep |
| `EvaluateOptionGraphStep` | 옵션 그래프를 비교 가능 레코드로 평가 | BuildOptionGraphStep |
| `FinalizeDecisionStep` | 평가를 결과 레코드로 종결 | EvaluateOptionGraphStep |
| `DivergeStep` | Topic Diverge -- add_research, ask, add_option | ApplyPatternStep (선택적) |
| `ConvergeStep` | Topic Converge -- finalize_plan | DivergeStep |
| `UtilizeStep` | Topic Utilize -- 모델링 액션 실행 | ConvergeStep |
| `ApplyPatternStep` | DecisionPattern 적용 -- inquiry_template, verification_heuristics 자동 주입 | -- (PatternAppliedEvent에 의해 트리거) |
| `ReviseReportStep` | 완료된 Topic 재개 -- report_history에 아카이브 후 상태 복귀 | -- (DecisionRevisedEvent에 의해 트리거) |

#### 2.6 이벤트 (Event) -- 5개

| 이벤트 | 트리거 대상 |
|:-------|:-----------|
| `DecisionRequestedEvent` | CaptureDecisionContextStep |
| `DecisionUpdatedEvent` | EvaluateOptionGraphStep (재평가) |
| `DecisionFinalizedEvent` | PublishDecisionModelAction, PersistTopicAction, MapDecisionToKernelAction |
| `DecisionRevisedEvent` | DivergeStep (재개) |
| `PatternAppliedEvent` | ApplyPatternStep |

#### 2.7 규칙 TOML 설계 대상

`decision_rules.toml` (미구현)에 외재화해야 할 규칙 범주:

- **워크플로우 시퀀스 규칙**: CaptureContext -> BuildOptionGraph -> Evaluate -> Finalize -> Publish, Diverge -> Converge -> Utilize
- **패턴 매칭 규칙**: DecisionPattern.matches_intent() -- required_intent_tags 전체 포함 검증
- **생명주기 전이 규칙**: DRAFT -> PROPOSED -> ACCEPTED/REJECTED -> DEPRECATED/SUPERSEDED

커스텀 조건 설계 대상:

| 조건 | 용도 |
|:-----|:-----|
| `SAME_DECISION_TYPE` | 동일 DecisionType 범위 내에서만 유효한 규칙 |
| `SAME_COMPLEXITY` | 동일 DecisionComplexity 수준에서만 적용되는 패턴 규칙 |
| `SAME_LIFECYCLE_STATE` | 동일 생명주기 상태 내에서만 허용되는 전이 규칙 |

---

## 3. 파이프라인 구현 명세

### Stage 진행 현황

| Stage | 이름 | 상태 | 설명 |
|:------|:-----|:-----|:-----|
| **Stage 1** | TOML 외재화 | -- 미구현 | `specs/decision_schema.toml` 미생성. 스키마 정의가 코드 내부에 분산 |
| **Stage 2** | Schema 객체 | -- 미구현 | `DecisionSchema` (frozen, SchemaPort 호환) 미존재. 커널의 `KernelSchema` 패턴 미적용 |
| **Stage 3** | Condition 레지스트리 | -- 미구현 | `condition_registry.py` 미존재. 커널 기본 조건 + Decision 전용 조건 미등록. 패턴 레지스트리(`registry.py`)는 Stage 5에서 완료 |
| **Stage 4** | Lifecycle | 완료 | `DecisionLifecycle` (frozen, DRAFT->PROPOSED->ACCEPTED->REJECTED->DEPRECATED->SUPERSEDED). 전이마다 새 인스턴스 반환 -- Kernel RuleLifecycle 패턴 준수 |
| **Stage 5** | Catalog/Aggregate | 완료 | `Topic` aggregate root -- 전체 워크플로우 구현 (add_research -> ask -> add_option -> finalize_plan -> revise_report). JSON 직렬화 왕복 지원 |
| **Stage 6** | Profile Loading | -- 미구현 | `20-decision.toml` 프로파일을 런타임에 로딩하는 브릿지 미존재 |
| **Stage 7** | Service Layer | -- 미구현 | `decision_service.py` 미존재. kernel_service.py 패턴(순수 함수, dict[str,Any] 반환) 미적용 |

### Stage 의존 관계

```
Stage 1 (TOML)
  |
  v
Stage 2 (Schema) ---> Stage 3 (Condition Registry)
  |                         |
  v                         v
Stage 6 (Profile Loading)  Stage 7 (Service Layer)
  |                         |
  +----------+--------------+
             |
             v
        런타임 통합

Stage 4 (Lifecycle) -- 이미 완료, Stage 7에 통합 필요
Stage 5 (Catalog/Aggregate) -- 이미 완료, Stage 2/7에 통합 필요
```

---

## 4. 고유 전문성

### 4.1 Design Thinking 4-Phase 오케스트레이터

`DesignThinkingProcess` (`process.py`)는 4단계 의사결정 프로세스를 순수 함수로 오케스트레이션한다.

```python
# process.py -- DesignThinkingProcess
process = DesignThinkingProcess()

intent = process.define_intent(
    description="Layer 간 계약 표준화",
    direction="maximize_consistency",
    context_refs=["report:gap-analysis-2024"]
)

options = process.diverge(intent, [
    {"description": "JSON Schema 기반", "feasibility_score": 0.8, "alignment_score": 0.7},
    {"description": "TOML 프로파일 기반", "feasibility_score": 0.9, "alignment_score": 0.95},
])

choice = process.converge(intent, options, selector_func=lambda opts: max(opts, key=lambda o: o.alignment_score))

result = process.utilize(choice, outcome_artifact={"schema": "decision_schema.toml"})
```

`converge()`는 `selector_func: Callable[[list[ChoiceOption]], ChoiceOption]`을 인자로 받아 옵션 선택 전략을 외부에서 주입할 수 있다. 거리(distance)는 `1.0 - alignment_score`로 계산되어 Intent로부터의 Gap을 정량화한다.

### 4.2 증거 기반 평가 프레임워크

#### Evidence 타입 계층 (`evidence.py`)

```
EvidenceType(StrEnum)
  - DOCUMENT     # 문서
  - DATA         # 정량 데이터
  - EXPERT_OPINION  # 전문가 의견
  - BENCHMARK    # 벤치마크
  - REGULATION   # 규정/규제

Evidence (frozen)
  - id, type, uri, title, description, relevance_score, collected_at

EvidenceCollection (frozen)
  - id, items: tuple[Evidence, ...]
  - add(evidence) -> EvidenceCollection  # 불변 -- 새 컬렉션 반환
```

핵심 원칙: **모든 Evidence는 생성 후 변경 불가.** `EvidenceCollection.add()`는 기존 컬렉션을 변경하지 않고 새 컬렉션을 반환한다(함수형 append).

#### 다차원 평가 (`evaluation.py`)

```python
# evaluation.py
EvaluationDimension(frozen): name, description, weight, scale
OptionScore(frozen): option_id, dimension_name, value, rationale
EvaluationResult(frozen): dimensions, scores
  -> weighted_total(option_id) -> float
```

`EvaluationResult.weighted_total(option_id)`는 모든 차원의 가중 합산 점수를 계산한다:

```
total = SUM(score.value * dimension.weight)  for matching option_id
```

### 4.3 패턴 템플릿 시스템

#### DecisionPattern (`pattern.py`, frozen)

```python
@dataclass(frozen=True)
class DecisionPattern:
    name: I18nString
    description: I18nString
    complexity: DecisionComplexity        # TRIVIAL | STRUCTURAL | STRATEGIC
    governed_rule_group: str | None       # Kernel RuleGroup 연결
    required_intent_tags: tuple[str, ...]
    inquiry_template: tuple[I18nString, ...]       # Diverge 단계 자동 질문
    verification_heuristics: tuple[I18nString, ...]  # 검증 가이드라인
    outcome_anchors: dict[str, I18nString]          # 성공/실패 상태 기술
```

`matches_intent(tags)`: required_intent_tags가 전부 포함되어야 매칭 성공.

#### PatternType & PatternSchema (`pattern.py`)

```
PatternType(StrEnum)
  - TRADE_OFF     # A vs B 비교
  - COMPLIANCE    # 규정 X 준수
  - ARCHITECTURE  # 시스템 구조화
  - PROCESS       # 워크플로우 정의

PatternSchema: name, type, description, phases: list[Phase], heuristics: list[HeuristicRule], inquiry_template
Phase: name, description, required_artifacts
HeuristicRule: description, severity (info/warning/critical), check_function
```

#### DecisionComplexity 3단계

| 수준 | 의미 | 적용 예시 |
|:-----|:-----|:---------|
| **TRIVIAL** | 단순 선택, 제한된 옵션 | 라이브러리 버전 선택 |
| **STRUCTURAL** | 구조적 영향, 다수 이해관계자 | 아키텍처 패턴 선택 |
| **STRATEGIC** | 조직 수준, 장기 영향 | 기술 스택 전환 |

### 4.4 Topic Aggregate 워크플로우

`Topic`은 N2의 aggregate root로서, 하나의 의사결정 문제에 대한 전체 Design Thinking 프로세스를 캡슐화한다.

```
Topic (mutable aggregate root)
  |
  |-- add_research(content, source, author) --> None
  |-- ask(text, asked_by) --> None
  |       `-- reply(answer_text, responder) --> None
  |-- add_option(title, description) --> None
  |-- apply_pattern(pattern) --> 질문/휴리스틱 자동 주입
  |-- finalize_plan(title, summary, selected_option_id, rationale) --> DesignReport
  |       `-- 기존 report 아카이브 -> report_history
  |-- revise_report() --> report_history에 아카이브, 상태 active로 복귀
  |-- get_timeline() --> 시간순 이벤트 목록
  |-- to_json() / from_json() --> 완전 직렬화 왕복
```

**상태 전이**: `active` -> (`finalize_plan`) -> `completed` -> (`revise_report`) -> `active`

**JSON 직렬화 왕복**: `Topic.to_json()`은 `dataclasses.asdict()`로 전체 트리를 직렬화하고, `Topic.from_json()`은 중첩된 `ResearchNote`, `Question`, `Option`, `Evaluation`, `DesignReport`, `DesignDecision`, `ModelingAction`을 재수화(hydrate)한다.

### 4.5 생명주기 상태 머신

```
DRAFT --> PROPOSED --> ACCEPTED --> DEPRECATED
                  |            `-> SUPERSEDED
                  `-> REJECTED
```

`DecisionLifecycle` (frozen): 전이마다 새 인스턴스를 반환한다. 이것은 Kernel의 `RuleLifecycle` 패턴과 동일하다.

```python
lifecycle = DecisionLifecycle()  # state=DRAFT
lifecycle = lifecycle.transition(DecisionLifecycleState.PROPOSED)  # 새 인스턴스
lifecycle = lifecycle.transition(DecisionLifecycleState.ACCEPTED)  # 새 인스턴스
```

유효하지 않은 전이는 `ValueError`를 발생시킨다. `REJECTED`, `DEPRECATED`, `SUPERSEDED`는 터미널 상태다.

### 4.6 커널 브릿지

`kernel_bridge.py`는 ea_decision 내에서 ea_kernel을 참조하는 **유일한 지점**이다.

| 함수 | 입력 | 출력 | 역할 |
|:-----|:-----|:-----|:-----|
| `create_rule_provenance(decision_ref, report_ref)` | 문자열 참조 | `dict[str, Any]` | 결정과 커널 RuleAsset을 연결하는 출처 레코드 생성 |
| `decision_result_from_rule_asset(rule_asset)` | RuleAsset | `dict[str, Any]` | 커널 규칙 자산에서 결정 관련 메타데이터 추출 |

두 함수 모두 `try/except ImportError`로 ea_kernel이 없는 환경에서도 동작한다(graceful degradation).

### 4.7 N1/N2 타입 분류표

| 계층 | 타입 | 불변성 | 모듈 |
|:-----|:-----|:------|:-----|
| N1 | `Intent`, `ChoiceOption`, `Choice`, `DecisionResult` | frozen | `types.py` |
| N1 | `DecisionTopic`, `TopicOption`, `EvaluationCriteria`, `Rationale`, `EvidenceReference` | frozen | `types.py` |
| N1 | `Evidence`, `EvidenceCollection` | frozen | `evidence.py` |
| N1 | `DecisionPattern` | frozen | `pattern.py` |
| N1 | `EvaluationDimension`, `OptionScore`, `EvaluationResult` | frozen | `evaluation.py` |
| N2 | `DecisionLifecycle` | frozen (전이→새 인스턴스) | `lifecycle.py` |
| N2 | `Topic`, `ResearchNote`, `Question`, `Option`, `Evaluation`, `DesignReport`, `DesignDecision`, `ModelingAction` | mutable | `topic.py` |
| N2 | `DesignThinkingProcess` | stateless | `process.py` |
| N2 | `PatternSchema`, `Phase`, `HeuristicRule` | mutable | `pattern.py` |
| N3 | `DecisionRegistry` | mutable singleton | `registry.py` |
| N3 | `DecisionRepository` | mutable (I/O) | `repository.py` |

---

## 5. 포트 계약 상세

### 5.1 자기 포트

**`DecisionModelPort`** -- Decision 레이어의 자기 모델 인터페이스.

다른 5개 레이어가 Decision을 자기 관점으로 참조할 때 이 포트를 통해 접근한다.

### 5.2 Decision이 정의하는 다른 레이어 (6x6 교차)

#### Decision -> Infra

Decision이 보는 Infra는 **데이터 가용성과 영속화 계약**이다.

| 요소 | 카테고리 | 설명 |
|:-----|:---------|:-----|
| `DecisionDataAvailability` | PassiveStructure | 의사결정 입력을 위한 데이터 가용성 전제조건 |
| `DecisionStorageContract` | Interface | Topic JSON 파일 영속화를 위한 저장소 계약 |
| `DecisionQueryIndex` | PassiveStructure | 의사결정 추적 검색을 위한 인덱스 계약 |

연결 규칙:
- `DecisionMetaModelRegistry` --(depends_on)--> `DecisionDataAvailability`
- `DecisionFlowSchemaService` --(depends_on)--> `DecisionStorageContract`, `DecisionQueryIndex`
- `DecisionRepositoryService` --(depends_on)--> `DecisionStorageContract`

#### Decision -> Governance

Decision이 보는 Governance는 **승인/정책/감사/버전 관리 게이트**다.

| 요소 | 카테고리 | 설명 |
|:-----|:---------|:-----|
| `DecisionApprovalReference` | PassiveStructure | 의사결정 평가 시 참조하는 거버넌스 승인 상태 |
| `DecisionPolicyConstraint` | Governance | 의사결정 옵션을 제약하는 거버넌스 정책 |
| `DecisionAuditSubmission` | Interface | 거버넌스 컴플라이언스를 위한 감사 제출 포트 |
| `DecisionVersionControl` | PassiveStructure | 메타-메타 모델 진화를 위한 버전 메타데이터 |

연결 규칙:
- `DecisionCriteriaModel` --(depends_on)--> `DecisionPolicyConstraint`
- `DecisionAgreementService` --(coordinates)--> `DecisionAuditSubmission`
- `DecisionPolicyConstraint` --(constrains)--> `FinalizeDecisionStep`
- `DecisionMetaModelRegistry` --(depends_on)--> `DecisionVersionControl`
- `EvaluateOptionGraphStep` --(consumes)--> `DecisionApprovalReference`

#### Decision -> Needs

Decision이 보는 Needs는 **결정 트리거와 목표 참조/피드백 경로**다.

| 요소 | 카테고리 | 설명 |
|:-----|:---------|:-----|
| `NeedsDecisionTrigger` | Event | Needs에서 발생한 의사결정 인스턴스 트리거 이벤트 |
| `NeedsGoalReference` | PassiveStructure | 의사결정 맥락 입력으로 사용되는 목표/요구 참조 |
| `NeedsPriorityInput` | PassiveStructure | 옵션 평가에 소비되는 우선순위화된 Needs |
| `NeedsSatisfactionFeedback` | Interface | 결정 결과를 Needs에 보고하는 피드백 포트 |

연결 규칙:
- `NeedsDecisionTrigger` --(triggers)--> `CaptureDecisionContextStep`
- `CaptureDecisionContextStep` --(consumes)--> `NeedsGoalReference`
- `EvaluateOptionGraphStep` --(consumes)--> `NeedsPriorityInput`
- `PublishDecisionModelAction` --(coordinates)--> `NeedsSatisfactionFeedback`

#### Decision -> Kernel

Decision이 보는 Kernel은 **도메인 제약 참조와 유효성 검증, 규칙 출처 추적 경로**다.

| 요소 | 카테고리 | 설명 |
|:-----|:---------|:-----|
| `KernelConstraintReference` | PassiveStructure | 옵션 평가 시 참조하는 커널 도메인 제약 |
| `KernelValidityCheck` | Interface | 의사결정 산출물을 커널 규칙으로 검증하는 훅 |
| `KernelTypeMapping` | PassiveStructure | 결정 노드 유형을 커널 엔티티 유형으로 매핑 |
| `KernelFeedbackInput` | PassiveStructure | 결정 재평가를 위해 소비되는 커널 검증 결과 |
| `KernelRuleProvenancePort` | Interface | RuleProvenance(decision_ref, report_ref)를 커널에 제출하는 포트 |

연결 규칙:
- `DecisionCriteriaModel` --(depends_on)--> `KernelConstraintReference`
- `EvaluateOptionGraphStep` --(coordinates)--> `KernelValidityCheck`
- `DecisionMetaModelRegistry` --(depends_on)--> `KernelTypeMapping`
- `FinalizeDecisionStep` --(consumes)--> `KernelFeedbackInput`
- `KernelBridgeService` --(coordinates)--> `KernelRuleProvenancePort`
- `MapDecisionToKernelAction` --(coordinates)--> `KernelRuleProvenancePort`

#### Decision -> Flow

Decision이 보는 Flow는 **실행 중 결정 요청 지점과 조건 분기, 결과 피드백**이다.

| 요소 | 카테고리 | 설명 |
|:-----|:---------|:-----|
| `FlowDecisionPoint` | PassiveStructure | Flow에서 의사결정이 필요한 실행 지점 |
| `FlowBranchCondition` | PassiveStructure | Flow 단계 전이의 조건부 분기 정의 |
| `FlowResultFeedback` | PassiveStructure | 결정 모델 보정을 위해 소비되는 Flow 실행 결과 |
| `FlowDecisionHook` | Interface | Flow가 실행 중 의사결정 평가를 호출하는 훅 |

연결 규칙:
- `DecisionFlowSchemaService` --(depends_on)--> `FlowDecisionPoint`
- `BuildOptionGraphStep` --(consumes)--> `FlowBranchCondition`
- `DecisionAgreementService` --(consumes)--> `FlowResultFeedback`
- `FlowDecisionHook` --(coordinates)--> `DecisionFlowSchemaService`

### 5.3 포트 규칙 우선순위 체계

| 우선순위 | 범주 | 적용 대상 |
|:---------|:-----|:---------|
| 60 | 카테고리 레벨 패턴 | `@Composite` contains `@ActiveStructure` 등 |
| 65 | 교차 레이어 포트 구조 | `*ModelPort` contains 교차 요소 |
| 70 | 요소 레벨 구체 규칙 | 서비스-단계, aggregate-레코드 간 명시적 관계 |
| 72 | 교차 레이어 행위 규칙 | 서비스-교차요소 간 depends_on/coordinates/consumes |
| 75 | 단계 시퀀싱/데이터 흐름/제약 | next 체인, produces/consumes, constrains |

---

## 6. 구현 로드맵

### [HIGH] 1. DecisionSchema 생성

**목표**: `types.py`, `topic.py`, `evidence.py`, `evaluation.py`, `pattern.py`에 분산된 타입 정의를 하나의 frozen `DecisionSchema` 객체로 통합한다.

**요구사항**:
- `SchemaPort` 호환 인터페이스 (커널의 `KernelSchema` 패턴 준수)
- entities/relations를 기존 N1/N2 타입에서 자동 추출
- `__post_init__`에서 O(1) 인덱스 구축 (커널 패턴)

**산출물**: `specs/decision_schema.toml` + `DecisionSchema` frozen dataclass

### [HIGH] 2. decision_service.py 생성

**목표**: `kernel_service.py` 패턴을 따르는 서비스 계층 구현.

**요구사항**:
- 순수 함수, `dict[str, Any]` 반환
- Topic CRUD + Design Thinking 프로세스 오케스트레이션
- 패턴 등록/조회
- 생명주기 전이
- 커널 브릿지 호출

**패턴 참조**: `kernel_service.py`의 UC1-UC6 순수 함수 구조

### [HIGH] 3. TOML 외재화

**목표**: 스키마와 규칙을 코드 밖으로 추출.

**산출물**:
- `specs/decision_schema.toml` -- 엔티티/관계/속성 정의
- `specs/decision_rules.toml` -- 워크플로우 시퀀스, 패턴 매칭, 생명주기 전이 규칙
- `specs/decision_schema.ko.toml` -- i18n 한국어 번역

### [MEDIUM] 4. DecisionLifecycle을 Topic에 통합

**현재 상태**: `lifecycle.py`의 `DecisionLifecycle` 상태 머신이 `Topic.status` 필드와 분리되어 있다. Topic은 `"active"/"completed"/"archived"` 문자열을 사용하고, DecisionLifecycle은 `DRAFT/PROPOSED/ACCEPTED/...` StrEnum을 사용한다.

**목표**: Topic의 상태 전이를 DecisionLifecycle 인스턴스로 위임. `DesignDecision.status`(DecisionStatus)와 `DecisionLifecycle.state`(DecisionLifecycleState)의 매핑 정의.

### [MEDIUM] 5. condition_registry.py 생성

**목표**: 커널 기본 조건(`SAME_LAYER`, `LAYER_ORDER`, `ANCESTOR_OF`, `SAME_BRANCH`)에 Decision 전용 조건을 추가.

**Decision 전용 조건**:
- `SAME_DECISION_TYPE` -- 동일 DecisionType 범위 검증
- `SAME_COMPLEXITY` -- 동일 DecisionComplexity 수준 검증
- `SAME_LIFECYCLE_STATE` -- 동일 생명주기 상태 범위 검증

### [MEDIUM] 6. 이중 평가 프레임워크 브릿지

**현재 상태**: 두 개의 평가 체계가 독립적으로 존재한다.
- `evaluation.py`: `EvaluationDimension` + `OptionScore` -> `EvaluationResult.weighted_total()`
- `topic.py`: `Evaluation` (pros/cons/score 0-10) 내장

**목표**: `EvaluationResult`가 Topic의 `Option.evaluation`을 정량화하는 상위 프레임워크로 통합. `Evaluation`(정성)과 `EvaluationDimension`(정량)이 상호 변환 가능한 브릿지 생성.

### [LOW] 7. profile_bridge.py 생성

**목표**: `20-decision.toml` 프로파일을 런타임에 로딩하여 DecisionSchema와 동기화.

**요구사항**:
- ea_profile의 `ProfileLoader` 활용
- TOML 요소 -> DecisionSchema 엔티티 자동 매핑
- 프로파일 규칙 -> 검증 함수 자동 등록
