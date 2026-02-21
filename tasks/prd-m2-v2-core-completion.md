[PRD]
# PRD: M2 v2 Core Completion (Unimplemented + Partial Specs)

## 1. Overview
현재 `docs/m2-v2-draft.md` 기준으로 M2 v2 엔티티 12개 중 일부만 구현되어 있으며, 특히 `FlowEdgeSpec`, `LoopContractSpec`, `GovernanceEventSpec`, `InfraAssetSpec`는 미구현 상태다.  
본 PRD는 미구현 영역을 포함해 12개 엔티티 전체를 실행 가능한 코드/검증/문서 계약으로 완성하여, 선언 기반 검증과 lineage replay 가능성을 시스템 기본 기능으로 고정하는 것을 목표로 한다.

## 2. Goals
- M2 v2 엔티티 12개를 타입/로더/검증기/런타임 훅으로 일관되게 구현한다.
- 프로파일 로딩 시 정적 검증으로 필수 경로/필드/교차 제약 위반을 조기 차단한다.
- 런타임에서 governance event 및 loop contract 강제 검증을 지원한다.
- `ea-governance` API와 `ea-infra` 저장소가 v2 계약을 직접 소비하도록 연결한다.
- 운영 팀이 재현 가능한 runbook으로 검증/운영할 수 있도록 문서를 최신화한다.

## 3. Quality Gates
These commands must pass for every user story:
- `uv run ruff check <changed-files-or-packages>` - Lint and style checks
- `uv run pytest <story-scoped-tests>` - Story-scoped regression tests

No browser/UI verification is required for this PRD.

## 4. User Stories

### US-001: v2 Core Type System 정의
**Description:** As a platform architect, I want a canonical v2 type system so that all M2 entities share one source of truth.

**Acceptance Criteria:**
- [ ] `ea-profile`에 12개 엔티티 대응 타입(`ProfileSpec`, `LayerSpec`, `FlowEdgeSpec`, `StateTokenSpec`, `TransitionSpec`, `ArtifactTypeSpec`, `TraceLinkSpec`, `GovernanceEventSpec`, `LoopContractSpec`, `InfraAssetSpec`, `ServiceOpsEventSpec`, `EvidenceBindingSpec`)이 정의된다.
- [ ] 필수 필드와 enum 타입이 코드에서 강제된다.
- [ ] 기존 profile 타입과 병행 가능한 하위 호환 레이어(변환/어댑터)가 제공된다.
- [ ] 타입 직렬화/역직렬화 단위 테스트가 추가된다.

### US-002: v2 Loader 확장 (TOML → Typed Spec)
**Description:** As a platform architect, I want the loader to parse v2 blocks so that profiles can declare the full contract declaratively.

**Acceptance Criteria:**
- [ ] loader가 `flow_edges`, `state_tokens`, `transitions`, `artifact_types`, `trace_links`, `governance_events`, `loop_contracts`, `infra_assets`, `service_ops_events`, `evidence_bindings` 블록을 파싱한다.
- [ ] 누락 필수 필드에 대해 명시적 에러 메시지를 반환한다.
- [ ] 기존 v1/v1.5 profile 로딩이 깨지지 않는다.
- [ ] 샘플 v2 TOML fixture 기반 로더 테스트가 추가된다.

### US-003: FlowEdgeSpec + LoopContractSpec 정적 검증기 구현
**Description:** As a platform architect, I want mandatory loop path validation so that causal closed-loop guarantees are enforced at load time.

**Acceptance Criteria:**
- [ ] 필수 경로(`infra->kernel`, `infra->flow`, `decision->needs`, `needs->kernel`, `kernel->flow`, `flow->projection`, `projection->decision`) 존재 검증이 구현된다.
- [ ] `loop_contracts.path`가 flow graph 상 닫힌 경로인지 검증한다.
- [ ] 잘못된 경로/단절 경로에 대한 구조화 에러 코드를 제공한다.
- [ ] validator 테스트가 성공/실패 케이스 모두 포함한다.

### US-004: TransitionSpec + StateTokenSpec 고도화
**Description:** As a platform architect, I want transition contracts to include trace/governance requirements so that state transitions are auditable.

**Acceptance Criteria:**
- [ ] `TransitionSpec`에 `requires_trace`, `requires_governance_event` 계약이 반영된다.
- [ ] `from/to`가 같은 layer의 `StateTokenSpec`을 참조하는지 검증된다.
- [ ] alias/canonical 매핑 규칙이 공통 유틸로 정리된다.
- [ ] transition 검증 테스트가 alias 포함 케이스를 검증한다.

### US-005: GovernanceEventSpec 계약 도입
**Description:** As a platform architect, I want typed governance event specs so that event required fields and retention policy are enforceable.

**Acceptance Criteria:**
- [ ] `GovernanceEventSpec(name, must_include, retention_policy)` 타입/validator가 구현된다.
- [ ] `must_include` 최소 키(`trace_id`, `lineage_id`) 검증이 구현된다.
- [ ] retention 정책 enum/허용값 검증이 구현된다.
- [ ] governance event spec 위반 테스트가 추가된다.

### US-006: InfraAssetSpec 카탈로그 모델/저장소 구현
**Description:** As a platform architect, I want infra assets cataloged with ownership and criticality so that projection/governance can reference infrastructure consistently.

**Acceptance Criteria:**
- [ ] `InfraAssetSpec` 모델과 저장소 인터페이스(in-memory + SQLite)가 구현된다.
- [ ] `owner/environment/criticality/asset_type/exposure_refs` 필드 제약 검증이 구현된다.
- [ ] `asset_type=api_gateway` 교차 제약(`url:` 또는 `api:` ref 필수)이 구현된다.
- [ ] 저장/조회/필터(예: owner, environment, criticality) 테스트가 추가된다.

### US-007: ServiceOpsEventSpec 통합 정렬
**Description:** As a platform architect, I want ServiceOpsEventSpec to be consumed from the unified v2 spec layer so that duplicated contracts are removed.

**Acceptance Criteria:**
- [ ] `ea-ops`의 `ServiceOpsEventSpec`와 `ea-profile v2` spec 타입 간 매핑 또는 단일 소스 전략이 확정된다.
- [ ] `ea-governance` ingestion API가 통합 spec 경로를 사용한다.
- [ ] critical severity 교차 제약이 통합 경로에서 동일하게 보장된다.
- [ ] 호환성 회귀 테스트가 추가된다.

### US-008: EvidenceBindingSpec 통합 및 TraceLinkSpec 연계
**Description:** As a platform architect, I want evidence and trace contracts connected so that replay and audit can validate required evidence.

**Acceptance Criteria:**
- [ ] `EvidenceBindingSpec`와 `TraceLinkSpec` 관계 검증 로직이 추가된다.
- [ ] `source_type=surface_artifact`일 때 `environment` 필수 규칙이 통합 validator에서 보장된다.
- [ ] lineage replay 시 evidence 누락 경고 또는 차단 모드가 선택 가능하게 구현된다.
- [ ] trace/evidence 통합 테스트가 추가된다.

### US-009: Runtime Contract Enforcement Hook 도입
**Description:** As a platform architect, I want runtime hooks for transition/event/loop checks so that static contracts are enforced during execution.

**Acceptance Criteria:**
- [ ] 상태 전이 시 `requires_trace` 계약 강제 훅이 구현된다.
- [ ] 상태 전이/구조 변경/표층 노출 시 required governance event 발행 여부 검증 훅이 구현된다.
- [ ] lineage 단절/필수 relation 누락의 warning vs block 정책을 설정 가능하게 제공한다.
- [ ] runtime enforcement 테스트가 추가된다.

### US-010: Governance API 확장 (v2 spec 조회/검증)
**Description:** As a platform architect, I want governance APIs to expose v2 spec status so that operators can inspect contract readiness.

**Acceptance Criteria:**
- [ ] v2 spec/validator 결과를 조회하는 read-only API endpoint가 추가된다.
- [ ] 엔티티별 구현 상태(loaded/validated/errors)를 반환한다.
- [ ] validation error envelope가 기존 API 에러 형식과 일관된다.
- [ ] API contract 테스트가 추가된다.

### US-011: Migration/Compatibility Layer
**Description:** As a platform architect, I want a migration path from legacy profile fields so that adoption does not require a hard cutover.

**Acceptance Criteria:**
- [ ] 기존 `LayerStack` 문자열 flow 필드를 `FlowEdgeSpec`로 변환하는 마이그레이션 유틸이 제공된다.
- [ ] legacy profile을 로드할 때 deprecation warning이 기록된다.
- [ ] 변환 결과를 검증하는 golden test가 추가된다.
- [ ] cutover 가이드 문서가 추가된다.

### US-012: 문서/Runbook 정합화
**Description:** As a platform architect, I want docs and runbooks aligned with implemented v2 contracts so that teams can operate repeatably.

**Acceptance Criteria:**
- [ ] `docs/m2-v2-draft.md`의 엔티티/검증/DoD 섹션이 구현 기준으로 업데이트된다.
- [ ] `docs/m2-v2-package-map.md`에 실제 구현 패키지 및 모듈 경로가 반영된다.
- [ ] 운영 검증 절차(runbook)에 정적 validator + runtime hook + replay 점검 루틴이 문서화된다.
- [ ] 문서 기반 수동 smoke 절차가 재현 가능하게 정리된다.

## 5. Functional Requirements
1. FR-1: 시스템은 12개 v2 엔티티를 타입 수준에서 표현할 수 있어야 한다.
2. FR-2: 시스템은 v2 TOML 블록을 파싱하여 typed spec으로 로드해야 한다.
3. FR-3: 시스템은 필수 flow 경로와 loop contract 닫힘 조건을 정적으로 검증해야 한다.
4. FR-4: 시스템은 transition/state token 참조 무결성을 검증해야 한다.
5. FR-5: 시스템은 governance event required field와 retention policy를 검증해야 한다.
6. FR-6: 시스템은 infra assets를 저장/조회/필터링할 수 있어야 한다.
7. FR-7: 시스템은 service ops 이벤트 계약을 통합된 spec 경로로 검증해야 한다.
8. FR-8: 시스템은 evidence binding과 trace link의 교차 제약을 검증해야 한다.
9. FR-9: 시스템은 런타임에서 trace/event/lineage 계약 위반을 감지해야 한다.
10. FR-10: 시스템은 v2 spec 상태와 검증 결과를 API로 조회 가능해야 한다.
11. FR-11: 시스템은 legacy profile에서 v2 spec으로의 변환 경로를 제공해야 한다.
12. FR-12: 시스템은 운영 문서와 구현 계약을 동기화해야 한다.

## 6. Non-Goals (Out of Scope)
- 웹 UI/시각화 대시보드의 신규 UX 개발
- 도메인별 비즈니스 규칙 추가(예: 새로운 SDLC 도메인 모델)
- 저장소 엔진 교체(SQLite 외 신규 DB 도입)
- 대규모 성능 최적화(기능 완성 후 별도 단계)

## 7. Technical Considerations
- 패키지 분할 원칙: `ea-profile`(스키마/validator), `ea-governance`(runtime/API), `ea-infra`(infra assets), `ea-ops`(ops contract), `ea-trace`(evidence/trace).
- 하위 호환 우선: 기존 profile 로더/검증기와 공존 가능한 migration adapter 필요.
- 에러 계약 일관성: validator/runtime/API에서 구조화된 error code + field path 유지.
- 테스트 전략: unit(타입/validator), integration(ingestion/lineage), compatibility(legacy→v2 migration) 3계층.

## 8. Success Metrics
- M2 v2 엔티티 12개 모두에 대해 타입/로더/검증 항목이 구현되어 테스트로 보장된다.
- 미구현 4개(`FlowEdgeSpec`, `LoopContractSpec`, `GovernanceEventSpec`, `InfraAssetSpec`)가 운영 가능한 상태로 승격된다.
- 주요 런타임 계약 위반 시 warning/block 정책이 의도대로 동작한다.
- 관련 문서(`m2-v2-draft`, package-map, runbook)와 코드 간 불일치 항목이 0건이다.

## 9. Open Questions
- `GovernanceEventSpec.retention_policy`의 표준 enum 집합을 어디까지 고정할지?
- lineage 위반 처리의 기본 정책을 warning으로 둘지 block으로 둘지?
- legacy profile 자동 마이그레이션을 기본 on으로 둘지, 명시 플래그 기반으로 둘지?
- `ServiceOpsEventSpec` 단일 소스는 `ea-ops` 고정인지, `ea-profile v2` 중심인지?
[/PRD]
