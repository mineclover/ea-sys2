# 6x6 포트 계약 명세

> 현재 EA-Sys TOML 프로파일에 정의된 포트를 정리하고, 각 포트의 런타임 계약을 구체화

## 1. 6x6 매트릭스 개요

각 레이어(행)는 6개 `*ModelPort`를 선언하여 다른 5개 레이어 + 자기 자신에 대한 계약을 **자기 전문성 관점에서** 정의한다.

| | Infra 대상 | Governance 대상 | Decision 대상 | Needs 대상 | Kernel 대상 | Flow 대상 |
|---|---|---|---|---|---|---|
| **Infra 관점** | 내부 요소 | GovernanceStorage* | DecisionData* | NeedsData* | KernelSpec* | FlowExecution* |
| **Governance 관점** | InfraSchema* | 내부 요소 | DecisionProcess* | NeedsRegistration* | KernelContract* | FlowExecution* |
| **Decision 관점** | DecisionData* | DecisionApproval* | 내부 요소 | NeedsDecision* | KernelConstraint* | FlowDecision* |
| **Needs 관점** | NeedsStorage* | NeedsApproval* | DecisionOutcome* | 내부 요소 | KernelDomain* | FlowFulfillment* |
| **Kernel 관점** | KernelSpec* | KernelModel* | DecisionConstraint* | NeedsDomain* | 내부 요소 | FlowContract* |
| **Flow 관점** | FlowState* | FlowApproval* | FlowDecision* | NeedsFulfillment* | KernelContract* | 내부 요소 |

---

## 2. 포트별 계약 명세

### 2.1 Infra 관점 (00-infra.toml)

**소유 포트**: `InfraModelPort` + 5개 cross-layer ModelPort

Infra는 **row 데이터 설계** 관점에서 각 레이어의 저장소·스키마·인덱싱·보존 계약을 정의한다.

#### Infra → Infra (내부 핵심 요소)

| 요소 | 카테고리 | 설명 |
|------|---------|------|
| InfraLayer | Composite | 인프라 row-data 설계 경계 |
| DataPlatformService | ActiveStructure | row-data 계약과 물리 데이터 접근 제어 |
| StorageLifecycleService | ActiveStructure | 스키마 수명주기, 마이그레이션, 보존 루틴 |
| ProfileStoragePort | Interface | 거버넌스용 프로파일/모델 영속 포트 |
| EventStoragePort | Interface | 이벤트 로그 영속 포트 |
| InfraModelPort | Interface | 자기 모델 인터페이스 |
| LayerVersionStore | PassiveStructure | 레이어 모델 페이로드 버전 테이블 |
| ValidationRunStore | PassiveStructure | 검증 실행 결과 테이블 |
| EvidenceStore | PassiveStructure | 증거/감사 테이블 |
| StoragePolicy | Governance | 영속 행위 제약 |

#### Infra → Governance

| 요소 | 설명 |
|------|------|
| GovernanceStorageSchema | 거버넌스 데이터 스키마 정의 |
| GovernanceAuditStore | 거버넌스 감사 로그 저장소 |
| GovernanceRetentionPolicy | 거버넌스 데이터 보존 정책 |
| GovernanceDataMigration | 거버넌스 스키마 마이그레이션 |

#### Infra → Decision

| 요소 | 설명 |
|------|------|
| DecisionDataSchema | 의사결정 데이터 스키마 정의 |
| DecisionIndexStrategy | 의사결정 데이터 인덱싱 전략 |
| DecisionArchivePolicy | 의사결정 아카이브 정책 |

#### Infra → Needs

| 요소 | 설명 |
|------|------|
| NeedsDataSchema | 요구 데이터 스키마 정의 |
| NeedsContextStore | 요구 컨텍스트 저장소 |
| NeedsBacklogIndex | 요구 백로그 인덱스 |

#### Infra → Kernel

| 요소 | 설명 |
|------|------|
| KernelSpecSchema | 커널 스펙 스키마 정의 |
| KernelGraphStore | 커널 그래프 저장소 |
| KernelValidationLogStore | 커널 검증 로그 저장소 |
| KernelStorageMigration | 커널 스키마 마이그레이션 |

#### Infra → Flow

| 요소 | 설명 |
|------|------|
| FlowExecutionLogSchema | 실행 로그 스키마 정의 |
| FlowCheckpointStore | 실행 상태 체크포인트 저장소 |
| FlowEventLogStore | 이벤트 로그 저장소 |
| FlowDataRetentionPolicy | 데이터 보존 정책 |

---

### 2.2 Governance 관점 (10-governance.toml)

**소유 포트**: `GovernanceEntryPort` + `GovernanceModelPort` + 5개 cross-layer ModelPort

Governance는 **5개 레이어 통합 관리** 관점에서 등록·버전·검증·활성·변경 통제를 정의한다.

#### Governance → Governance (내부 핵심 요소)

| 요소 | 카테고리 | 설명 |
|------|---------|------|
| GovernanceLayer | Composite | 거버넌스 통제면 경계 |
| LayerModelRegistry | ActiveStructure | 레이어 모델 정의 등록/인덱싱 |
| VersionLifecycleManager | ActiveStructure | 모델 버전 수명주기, 활성 포인터 |
| ValidationCoordinator | ActiveStructure | 호환성/무결성 검증 워크플로 |
| AgreementCoordinator | ActiveStructure | 이해관계자 합의 워크플로 |
| ActivationCoordinator | ActiveStructure | 활성화 조율 |
| GovernanceContainer | ActiveStructure | 통합 퍼사드 |
| GovernanceEntryPort | Interface | 시스템 진입점 |
| GovernanceModelPort | Interface | 자기 모델 인터페이스 |
| GovernanceDbPort | Interface | 데이터베이스 포트 |
| *6개 Policy* | Governance | Registration/Version/Compatibility/Approval/Boundary/Transaction |
| *4개 Goal* | Goal | Transparency/Consistency/Traceability/Evolvability |
| *11개 Endpoint* | Interface | ModelRegister/Validate/Activate/State/DecisionTrace/KernelRule/KernelEvaluate/KernelSnapshot/NeedsCatalog/LayerSnapshot/GovernanceDashboard |
| *9개 Ops/서비스* | ActiveStructure | KernelModelOps, KernelRuleOps, DecisionTraceOps, NeedsOps, TransactionManager, ExecutionService, MetaGenerator, ProfileBridge, ConditionRegistryService |

#### Governance → Infra

| 요소 | 설명 |
|------|------|
| InfraSchemaGovernance | 인프라 스키마 거버넌스 |
| InfraCapacityAudit | 인프라 용량 감사 |
| InfraCompliancePolicy | 인프라 규정 준수 정책 |
| InfraChangeRecord | 인프라 변경 기록 |

#### Governance → Decision

| 요소 | 설명 |
|------|------|
| DecisionProcessAudit | 의사결정 프로세스 감사 |
| DecisionModelApproval | 의사결정 모델 승인 |
| DecisionGovernancePolicy | 의사결정 거버넌스 정책 |
| DecisionComplianceRecord | 의사결정 규정 준수 기록 |

#### Governance → Needs

| 요소 | 설명 |
|------|------|
| NeedsRegistrationGate | 요구 등록 게이트 |
| NeedsPriorityAudit | 요구 우선순위 감사 |
| NeedsGovernancePolicy | 요구 거버넌스 정책 |
| NeedsChangeRecord | 요구 변경 기록 |

#### Governance → Kernel

| 요소 | 설명 |
|------|------|
| KernelContractApproval | 커널 계약 승인 |
| KernelRulePromotionGate | 커널 규칙 승격 게이트 |
| KernelGovernancePolicy | 커널 거버넌스 정책 |
| KernelEvolutionRecord | 커널 진화 기록 |
| KernelQualityGate | 커널 품질 게이트 |

#### Governance → Flow

| 요소 | 설명 |
|------|------|
| FlowExecutionAudit | 흐름 실행 감사 |
| FlowContractComplianceCheck | 흐름 계약 규정 준수 검사 |
| FlowGovernancePolicy | 흐름 거버넌스 정책 |
| FlowComplianceRecord | 흐름 규정 준수 기록 |

---

### 2.3 Decision 관점 (20-decision.toml)

**소유 포트**: `DecisionModelPort` + 5개 cross-layer ModelPort

Decision은 **의사결정 메타-메타 모델** 관점에서 활동·상태·옵션·평가·결론 구조를 정의한다.

#### Decision → Decision (내부 핵심 요소)

| 요소 | 카테고리 | 설명 |
|------|---------|------|
| DecisionLayer | Composite | 의사결정 메타-메타 모델 경계 |
| DecisionMetaModelRegistry | ActiveStructure | 의사결정 메타 엔티티/관계 어휘 등록 |
| DecisionFlowSchemaService | ActiveStructure | 의사결정 활동/전이 구조 스키마 유지 |
| DecisionAgreementService | ActiveStructure | 합의 워크플로 |
| TopicAggregate | Composite | Topic 집합체 |
| DesignThinkingProcessService | ActiveStructure | Design Thinking 프로세스 오케스트레이터 |
| DecisionPatternRegistryService | ActiveStructure | 의사결정 패턴 레지스트리 |
| DecisionRepositoryService | ActiveStructure | Topic 집합체 JSON 영속화 |
| KernelBridgeService | ActiveStructure | 의사결정 → 커널 모델링 액션 브릿지 |
| *6개 Catalog* | PassiveStructure | NodeType/RelationType/State/Phase/Complexity/LifecycleState |
| *3개 Model* | Assessment | Criteria/Heuristic/Rationale |
| *21개 Record* | PassiveStructure | Context/Option/Evaluation/Outcome/Intent/ChoiceOption/Choice/DecisionResult/ResearchNote/Question/Option/EvaluationDetail/ModelingAction/DesignDecision/DesignReport/DecisionPattern/PatternSchema/Evidence/EvidenceCollection/EvaluationDimension/RuleProvenance |
| *9개 Step* | Behavior | CaptureContext/BuildOptionGraph/Evaluate/Finalize/Diverge/Converge/Utilize/ApplyPattern/ReviseReport |
| *3개 Action* | Executable | PublishDecisionModel/MapDecisionToKernel/PersistTopic |
| *2개 Goal* | Goal | DecisionTrace/EvidenceBasedDecision |
| *5개 Event* | Event | Requested/Updated/Finalized/Revised/PatternApplied |

#### Decision → Infra

| 요소 | 설명 |
|------|------|
| DecisionDataAvailability | 의사결정 데이터 가용성 |
| DecisionStorageContract | 의사결정 저장 계약 |
| DecisionQueryIndex | 의사결정 쿼리 인덱스 |

#### Decision → Governance

| 요소 | 설명 |
|------|------|
| DecisionApprovalReference | 의사결정 승인 참조 |
| DecisionPolicyConstraint | 의사결정 정책 제약 |
| DecisionAuditSubmission | 의사결정 감사 제출 |
| DecisionVersionControl | 의사결정 버전 관리 |

#### Decision → Needs

| 요소 | 설명 |
|------|------|
| NeedsDecisionTrigger | 요구 기반 의사결정 트리거 |
| NeedsGoalReference | 요구 목표 참조 |
| NeedsPriorityInput | 요구 우선순위 입력 |
| NeedsSatisfactionFeedback | 요구 충족 피드백 |

#### Decision → Kernel

| 요소 | 설명 |
|------|------|
| KernelConstraintReference | 커널 제약 참조 |
| KernelValidityCheck | 커널 유효성 검사 |
| KernelTypeMapping | 커널 타입 매핑 |
| KernelFeedbackInput | 커널 피드백 입력 |
| KernelRuleProvenancePort | 커널 규칙 출처 포트 |

#### Decision → Flow

| 요소 | 설명 |
|------|------|
| FlowDecisionPoint | 흐름 내 의사결정 지점 |
| FlowBranchCondition | 흐름 분기 조건 |
| FlowResultFeedback | 흐름 결과 피드백 |
| FlowDecisionHook | 흐름 의사결정 훅 |

---

### 2.4 Needs 관점 (30-needs.toml)

**소유 포트**: `NeedsModelPort` + 5개 cross-layer ModelPort

Needs는 **요구 모델 정의** 관점에서 이해관계자·요구·정당화·컨텍스트의 정형 표현을 정의한다.

#### Needs → Needs (내부 핵심 요소)

| 요소 | 카테고리 | 설명 |
|------|---------|------|
| NeedsLayer | Composite | 요구 모델링 경계 |
| NeedsCatalogService | ActiveStructure | 정규화된 요구/우선순위 페이로드 관리 |
| NeedCatalog | Composite | 요구 카탈로그 집합체 |
| *9개 Vocabulary 타입* | PassiveStructure | Stakeholder/Desire/Justification/NeedStatement/UseCase/Need/NeedRelation/NeedProcessUnit/NeedsSchema |
| *5개 Status 상태* | Goal | Draft/Expressed/Acknowledged/Addressed/Withdrawn |
| *4개 Priority 수준* | Assessment | Critical/High/Medium/Low |
| *6개 CauseType* | Context | Emotional/Situational/Physical/Logical/Mental/Philosophical |
| *3개 ProcessStage* | Behavior | Identify/Query/ModelDetail |
| *2개 JustificationType* | Assessment | Because/InOrderTo |
| *3개 ResolutionComplexity* | Assessment | Simple/Procedural/Complex |
| *5개 NeedRelation 타입* | Assessment | DependsOn/ConflictsWith/Supports/Refines/Supersedes |
| *5개 서비스/포트* | ActiveStructure/Interface/PassiveStructure | NeedsQueryService(ActiveStructure), KernelBridgePort(Interface), ProfileBridgePort(Interface), NeedRepository(ActiveStructure), ConditionRegistry(PassiveStructure) |
| *4개 Event* | Event | Expressed/Revised/StatusTransition/DecisionEvidenceInherited |

#### Needs → Infra

| 요소 | 설명 |
|------|------|
| NeedsStorageContract | 요구 저장 계약 |
| NeedsContextDataSource | 요구 컨텍스트 데이터 소스 |
| NeedsBacklogStore | 요구 백로그 저장소 |

#### Needs → Governance

| 요소 | 설명 |
|------|------|
| NeedsApprovalGate | 요구 승인 게이트 |
| NeedsChangePolicy | 요구 변경 정책 |
| NeedsAuditPort | 요구 감사 포트 |
| NeedsVersionRecord | 요구 버전 기록 |

#### Needs → Decision

| 요소 | 설명 |
|------|------|
| DecisionOutcomeInput | 의사결정 결과 입력 |
| DecisionContextReference | 의사결정 컨텍스트 참조 |
| DecisionTriggerPort | 의사결정 트리거 포트 |

#### Needs → Kernel

| 요소 | 설명 |
|------|------|
| KernelDomainReference | 커널 도메인 참조 |
| KernelConstraintInput | 커널 제약 입력 |
| KernelValidationPort | 커널 검증 포트 |
| KernelCoverageTarget | 커널 커버리지 대상 |

#### Needs → Flow

| 요소 | 설명 |
|------|------|
| FlowFulfillmentStatus | 흐름 충족 상태 |
| FlowProgressFeedback | 흐름 진행 피드백 |
| FlowCompletionEvent | 흐름 완료 이벤트 |

---

### 2.5 Kernel 관점 (40-kernel.toml)

**소유 포트**: `KernelContractPort` + `KernelModelPort` + 5개 cross-layer ModelPort

Kernel은 **도메인 핵심 모델** 관점에서 존재론(요소/관계)과 유효성 규칙을 정의한다.

#### Kernel → Kernel (내부 핵심 요소)

| 요소 | 카테고리 | 설명 |
|------|---------|------|
| KernelLayer | Composite | 커널 스펙 경계 |
| KernelContractService | ActiveStructure | 커널 계약 발행 |
| KernelRuleCompiler | ActiveStructure | 규칙 컴파일러 |
| KernelValidationService | ActiveStructure | 유효성 검증 서비스 |
| KernelProfileRegistry | ActiveStructure | 프로파일 레지스트리 |
| KernelContractPort | Interface | 커널 계약 포트 |
| GovernanceSystem | ActiveStructure | 거버넌스 시스템 퍼사드 |
| *12개 거버넌스 서비스* | ActiveStructure | JudgmentService/EvidenceAnalyzer/PromotionEngine/WhatIfSimulator/ImpactEvaluator/LifecycleController/KernelModelRegistrationService/KernelService/RuleCorpus/ProfileRuleCompiler/ProfileTopologyGraph/InMemoryEventBus |
| *4개 Store* | ActiveStructure | RuleAssetStore/DecisionStore/CorpusVersionStore/I18nStore |
| *18개 Data 타입* | PassiveStructure | KernelCapabilityModel/KernelRuleSet/KernelSpecSnapshot/EnhancedJudgment/ReferenceStats/AnalysisReport/RuleEffectiveness/ConflictHotspot/UsageProfile/RuleChangeProposal/SimulationResult/ImpactReport/RuleChangeSet/ModelRegistryEntry/ModelVersionEntry/ValidationRunEntry/RegistrationResult/Notification |
| *4개 Page* | Page | KernelTopology/RuleBrowser/ProfileEditor/KernelGovernanceDashboard |
| *4개 Endpoint* | Interface | Query/Validate/Profile/KernelGovernance |
| *2개 이벤트 인프라* | Interface | LifecycleEventPort/NotificationService |
| *1개 Assessment* | Assessment | PromotionCriteria |
| *3개 Goal* | Goal | KernelConsistency/RuleLifecycleIntegrity/EvidenceBasedEvolution |
| *6개 Step* | Behavior | ContractReview/ExecuteJudgment/AnalyzeEvidence/SimulateChange/EvaluateImpact/RunAutoPromotion |
| *5개 Action* | Executable | SubmitRule/ApproveRule/DeprecateRule/CreateSnapshot/PublishKernelContract |
| *5개 Event* | Event | KernelSpecPublished/LifecycleEvent/RuleSubmitted/RuleApproved/CorpusUpdated |
| *4개 Context* | Context | ModelAuthor/ModelExplorer/ModelValidator/GovernanceOperator |
| *4개 Experience* | Composite | KernelModeling/KernelExploration/KernelValidation/KernelGovernance |

#### Kernel → Infra

| 요소 | 설명 |
|------|------|
| KernelSpecStore | 커널 스펙 저장소 |
| KernelRuleStore | 커널 규칙 저장소 |
| KernelProfileStore | 커널 프로파일 저장소 |
| KernelAuditLog | 커널 감사 로그 |

#### Kernel → Governance

| 요소 | 설명 |
|------|------|
| KernelModelRegistration | 커널 모델 등록 |
| KernelVersionGate | 커널 버전 게이트 |
| KernelCompatibilityCheck | 커널 호환성 검사 |
| KernelApprovalPolicy | 커널 승인 정책 |
| KernelChangeRecord | 커널 변경 기록 |

#### Kernel → Decision

| 요소 | 설명 |
|------|------|
| DecisionConstraintInput | 의사결정 제약 입력 |
| DecisionRuleMapping | 의사결정 규칙 매핑 |
| DecisionTraceReference | 의사결정 추적 참조 |
| DecisionFeedbackChannel | 의사결정 피드백 채널 |

#### Kernel → Needs

| 요소 | 설명 |
|------|------|
| NeedsDomainMapping | 요구 도메인 매핑 |
| RequirementConstraintBridge | 요구-제약 브릿지 |
| NeedsCoverageReport | 요구 커버리지 리포트 |
| NeedsChangeNotification | 요구 변경 알림 |

#### Kernel → Flow

| 요소 | 설명 |
|------|------|
| FlowContractSnapshot | 흐름 계약 스냅샷 |
| FlowValidationHook | 흐름 검증 훅 |
| FlowExecutionFeedback | 흐름 실행 피드백 |
| FlowConstraintViolationEvent | 흐름 제약 위반 이벤트 |

---

### 2.6 Flow 관점 (50-flow.toml)

**소유 포트**: `FlowModelPort` + 5개 cross-layer ModelPort

Flow는 **실행/데이터 흐름 모델** 관점에서 단계 순서, 입출력 소비/생산, 트리거/전이를 정의한다.

#### Flow → Flow (내부 핵심 요소 — 3-Plane 모델)

**P1 Specification Plane**:

| 요소 | 카테고리 | 설명 |
|------|---------|------|
| SpecificationPlane | Composite | 선언적 정의 평면 |
| StepSpecContract | Interface | StepSpec ABC |
| FlowMetaStepDefinition | PassiveStructure | FlowMetaStep 정의 |
| KernelGroundedStepSpecType | Behavior | 커널 앵커 기반 StepSpec |
| WorkflowSpecContract | Interface | WorkflowSpec ABC |
| UseCaseSpecType | Behavior | 유스케이스 스펙 |
| ExecutionContextData | PassiveStructure | 실행 컨텍스트 |
| StepResultSpecData | PassiveStructure | 단계 결과 스펙 |
| FlowGenerationRuleData | Assessment | 커널 엔티티 → 흐름 스펙 생성 규칙 |
| FlowTopologyData | PassiveStructure | 선언적 프로세스 구조 (단계/전이/생성 규칙) |

**P2 Coordination Plane**:

| 요소 | 카테고리 | 설명 |
|------|---------|------|
| CoordinationPlane | Composite | 조율/그래프 평면 |
| ProcessSpecType | ActiveStructure | ProcessSpec 타입 |
| StepDefinitionNode | Behavior | 단계 정의 노드 |
| DataFlowEdgeLink | PassiveStructure | 데이터 흐름 엣지 |
| LogicConditionExpr | Assessment | 논리 조건 표현 |
| DataTransformationSpec | Behavior | 데이터 변환 스펙 |
| SchemaDefinitionData | PassiveStructure | 스키마 정의 데이터 |
| StepSchemaUsageSpec | PassiveStructure | 단계 데이터 계약 (입출력 스키마 선언) |
| FlowOntologyRegistry | ActiveStructure | Flow 온톨로지 레지스트리 |
| FlowStepCategoryEnum | Assessment | 단계 역할 분류 (ACTION/DECISION/EVENT/GATEWAY/TRANSFORMATION) |

**P3 Realization Plane**:

| 요소 | 카테고리 | 설명 |
|------|---------|------|
| RealizationPlane | Composite | 명령적 실행 평면 |
| FlowRuntimeEngine | ActiveStructure | FlowRuntime 엔진 |
| StepImplementerContract | Interface | StepImplementer ABC |
| StepInterpretationResultData | PassiveStructure | 선언적 해석 결과 데이터 |
| StepExecutionResultData | PassiveStructure | 실행 결과 데이터 (StepInterpretationResult 확장) |
| FlowExecutionResultData | PassiveStructure | 워크플로 실행 결과 |

**8단계 파이프라인**:

| 요소 | 설명 |
|------|------|
| ContextIngestStep | 컨텍스트 입력 수집 |
| NormalizeNeedStep | 요구 정규화 |
| BuildKernelInputStep | 커널 입력 구성 |
| MapKernelSpecStep | 커널 스펙 매핑 |
| ExecuteKernelAction | 커널 액션 실행 |
| VerifyOutcomeStep | 결과 검증 |
| PersistFlowStateStep | 흐름 상태 영속화 |
| PublishFlowOutcomeAction | 흐름 결과 발행 |

**FlowLayerContractMatrix**: 6x6 전체 계약을 소유하는 핵심 요소.

#### Flow → Infra

| 요소 | 설명 |
|------|------|
| FlowStateCheckpoint | 흐름 상태 체크포인트 |
| FlowExecutionLog | 흐름 실행 로그 |

#### Flow → Governance

| 요소 | 설명 |
|------|------|
| FlowApprovalGate | 흐름 승인 게이트 |
| FlowAuditSubmission | 흐름 감사 제출 |
| FlowCompliancePolicy | 흐름 규정 준수 정책 |
| FlowChangeRecord | 흐름 변경 기록 |

#### Flow → Decision

| 요소 | 설명 |
|------|------|
| FlowDecisionGate | 흐름 의사결정 게이트 |
| FlowBranchInput | 흐름 분기 입력 |
| FlowDecisionOutcome | 흐름 의사결정 결과 |
| FlowDecisionFeedback | 흐름 의사결정 피드백 |

#### Flow → Needs

| 요소 | 설명 |
|------|------|
| NeedsFulfillmentReport | 요구 충족 리포트 |
| NeedsCompletionNotification | 요구 완료 알림 |

#### Flow → Kernel

| 요소 | 설명 |
|------|------|
| KernelContractReference | 커널 계약 참조 |
| KernelValidationResult | 커널 검증 결과 |
| KernelSpecVersion | 커널 스펙 버전 |
| KernelConstraintHook | 커널 제약 훅 |

---

## 3. 계약 소유권 규칙

### 3.1 Flow의 FlowLayerContractMatrix 소유

Flow가 `FlowLayerContractMatrix`를 소유하며, 6x6 전체 계약의 **조정** 책임을 갖는다. 이는 Flow가 런타임 실행 시 모든 레이어 간 데이터 흐름을 조율하기 때문이다.

### 3.2 자기 포트 수정 규칙

각 레이어는 자기 `*ModelPort` 내 요소만 수정할 수 있다:
- Infra는 `GovernanceStorageSchema`를 정의/수정 가능 (Infra 관점의 Governance 계약)
- Governance는 `InfraSchemaGovernance`를 정의/수정 가능 (Governance 관점의 Infra 계약)
- 동일 대상에 대한 두 관점의 계약은 **독립적으로 존재**하며, 충돌 해소는 Governance가 담당

### 3.3 상호 계약 대칭성

| Infra→Governance | Governance→Infra |
|---|---|
| GovernanceStorageSchema (데이터 스키마) | InfraSchemaGovernance (스키마 거버넌스) |
| GovernanceAuditStore (감사 저장소) | InfraCapacityAudit (용량 감사) |
| GovernanceRetentionPolicy (보존 정책) | InfraCompliancePolicy (규정 준수) |
| GovernanceDataMigration (마이그레이션) | InfraChangeRecord (변경 기록) |

각 쌍은 동일 주제를 **서로 다른 전문성 관점**에서 바라본다.

---

## 4. 크로스레이어 라우팅

### 4.1 GovernanceEntryPort → *ModelPort 라우팅

```
외부 요청 → GovernanceEntryPort
  ├─→ ModelRegisterEndpoint → 적절한 LayerModelPort 라우팅
  ├─→ ModelValidateEndpoint → KernelModelPort + 대상 LayerModelPort
  ├─→ ModelActivateEndpoint → VersionLifecycleManager
  ├─→ ModelStateEndpoint → 레이어별 스냅샷 조회
  └─→ ModelDecisionTraceEndpoint → DecisionTraceOps → DecisionModelPort
```

### 4.2 피드백 경로

```
Flow 실행 결과 (FlowExecutionResultData)
  → FlowExecutionFeedback (Kernel ModelPort)
  → KernelChangeRecord (Governance ModelPort)
  → DecisionFeedbackChannel (Decision ModelPort via Kernel)
```

**구체적 피드백 흐름**:
1. **flow → kernel**: `FlowConstraintViolationEvent` → 커널 제약 위반 감지
2. **kernel → governance**: `KernelEvolutionRecord` → 커널 규칙 변경 이력 축적
3. **governance → decision**: `DecisionComplianceRecord` → 의사결정 모델 보정 환류

---

## 5. 구현 매핑

### 포트 요소 → Python 모듈/클래스 대응표

| 포트 요소 | Python 모듈 | 클래스/함수 |
|----------|------------|-----------|
| **Infra** | | |
| DataPlatformService | (미구현) | — |
| StorageLifecycleService | (미구현) | — |
| ResourceIndexingService | `ea_infra.indexer` | `ResourceIndexer` |
| SQLiteStorageBackend | (미구현 — 패턴은 ea_kernel 스토어에 존재) | — |
| **Governance** | | |
| GovernanceContainer | `ea_governance.facade` | `GovernanceContainer` |
| LayerModelRegistry | `ea_kernel.model_registration` | `ModelRegistrationService` |
| VersionLifecycleManager | `ea_governance.facade` | `.register_kernel_model()` |
| ValidationCoordinator | `ea_governance.facade` | `.validate_kernel_model()` |
| TransactionManager | `ea_governance.transaction` | `TransactionManager` |
| KernelModelOps | `ea_governance.kernel_model_ops` | `KernelModelOps` |
| KernelRuleOps | `ea_governance.kernel_rule_ops` | `KernelRuleOps` |
| DecisionTraceOps | `ea_governance.decision_trace_ops` | `DecisionTraceOps` |
| NeedsOps | `ea_governance.needs_ops` | `NeedsOps` |
| ExecutionService | `ea_governance.execution_service` | `ExecutionService` |
| GovernanceLayerStorePort | `ea_governance.layer_store` | `GovernanceLayerStore` (ABC) |
| GovernanceKernelStore | `ea_governance.kernel_store` | `GovernanceKernelStore` |
| GovernanceNeedsStore | `ea_governance.needs_store` | `GovernanceNeedsStore` |
| **Decision** | | |
| TopicAggregate | `ea_decision.topic` | `Topic` |
| DesignThinkingProcessService | `ea_decision.process` | `DesignThinkingProcess` |
| DecisionPatternRegistryService | `ea_decision.registry` | `DecisionRegistry` |
| KernelBridgeService | `ea_decision.kernel_bridge` | `create_rule_provenance()` |
| DecisionRepositoryService | `ea_decision.repository` | `DecisionRepository` |
| **Needs** | | |
| NeedsCatalogService | `ea_needs.catalog` | `NeedCatalog` |
| NeedsSchema | `ea_needs.needs_schema` | `NEEDS_SCHEMA` |
| NeedsQueryService | `ea_needs.needs_service` | `list_needs()`, `describe_need()`, etc. |
| KernelBridgePort | `ea_needs.kernel_bridge` | `validate_kernel_refs()` |
| ProfileBridgePort | `ea_needs.profile_bridge` | `load_needs_profile()` |
| ConditionRegistry | `ea_needs.condition_registry` | `needs_condition_registry()` |
| NeedRepository | `ea_needs.repository` | `NeedRepository` |
| **Kernel** | | |
| KernelContractService | `ea_kernel.spec` | `KERNEL_SPEC` |
| KernelRuleCompiler | `ea_kernel.profile_rule_compiler` | `ProfileRuleCompiler` |
| KernelValidationService | `ea_kernel.rule_corpus` | `RuleCorpus.judge()` |
| KernelProfileRegistry | `ea_kernel.profile_registry` | `ProfileRegistry` |
| KernelService | `ea_kernel.kernel_service` | `list_entities()`, `judge()`, etc. |
| RuleCorpus | `ea_kernel.rule_corpus` | `RuleCorpus` |
| GovernanceSystem | `ea_kernel.governance` | `GovernanceSystem` |
| JudgmentService | `ea_kernel.judgment_service` | `JudgmentService` |
| EvidenceAnalyzer | `ea_kernel.evidence_analyzer` | `EvidenceAnalyzer` |
| PromotionEngine | `ea_kernel.promotion_engine` | `PromotionEngine` |
| WhatIfSimulator | `ea_kernel.what_if_simulator` | `WhatIfSimulator` |
| ImpactEvaluator | `ea_kernel.impact_evaluator` | `ImpactEvaluator` |
| LifecycleController | `ea_kernel.lifecycle_controller` | `LifecycleController` |
| KernelModelRegistrationService | `ea_kernel.model_registration` | `ModelRegistrationService` |
| ProfileRuleCompiler | `ea_kernel.profile_rule_compiler` | `ProfileRuleCompiler` |
| ProfileTopologyGraph | `ea_kernel.profile_graph` | `ProfileTopologyGraph` |
| RuleAssetStore | `ea_kernel.rule_asset_store` | `RuleAssetStore` (ABC) |
| DecisionStore | `ea_kernel.decision_store` | `DecisionStore` (ABC) |
| CorpusVersionStore | `ea_kernel.corpus_version_store` | `CorpusVersionStore` (ABC) |
| I18nStore | `ea_kernel.i18n_store` | `I18nStore` (ABC) |
| InMemoryEventBus | `ea_kernel.lifecycle_events` | `InMemoryLifecycleEventBus` |
| NotificationService | `ea_kernel.notification_service` | `NotificationService` (ABC) |
| **Flow** | | |
| FlowRuntimeEngine | `ea_flow.runtime` | `FlowRuntime` |
| StepImplementerContract | `ea_flow.runtime` | `StepImplementer` (ABC) |
| StepSpecContract | `ea_flow.spec` | `StepSpec` (ABC) |
| WorkflowSpecContract | `ea_flow.spec` | `WorkflowSpec` (ABC) |
| ProcessSpecType | `ea_flow.topology` | `ProcessSpec` |
| FlowOntologyRegistry | `ea_flow.topology` | `FlowOntology` |
| FlowProfileType | `ea_flow.profile` | `FlowProfile` |
| AddRuleStepSpecType | `ea_flow.kernel_actions` | `AddRuleStepSpec` |
| DeprecateRuleStepSpecType | `ea_flow.kernel_actions` | `DeprecateRuleStepSpec` |
| AddRuleImplementerType | `ea_flow.kernel_implementers` | `AddRuleImplementer` |
| DeprecateRuleImplementerType | `ea_flow.kernel_implementers` | `DeprecateRuleImplementer` |
