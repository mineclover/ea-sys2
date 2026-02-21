# M2 v2 코어 패키지 매핑

## 1. 목적
- M2 v2 도입 시 어떤 코어 패키지를 변경/신규로 작업할지 사전에 고정한다.
- 구현 전 설계/일정/소유권 논의를 위한 기준표로 사용한다.

## 2. 네이밍 원칙
1. 코어 패키지는 `ea-` prefix를 사용한다.
2. 도메인 패키지와 코어 패키지를 분리한다.
3. v2 전용 기능은 기존 패키지 내부 `v2` 모듈로 우선 수용한다.
4. 기존 패키지 책임을 과도하게 키우는 경우에만 신규 패키지를 만든다.

## 3. 패키지 매핑 표
| 패키지명 | 상태 | 역할 | v2 핵심 작업 |
| --- | --- | --- | --- |
| `ea-profile` | 기존(확장) | profile 스키마/로더/validator 중심 | `InfraAssetSpec`, `ServiceOpsEventSpec`, `EvidenceBindingSpec` 타입/로더/정적 validator 추가 |
| `ea-kernel` | 기존(확장) | profile discovery/composition, layer API | namespace-aware discovery/composer, v2 profile registry, 도메인 합성 검증 지원 |
| `ea-governance` | 기존(확장) | system ledger/audit | `governance_events` + `service_ops_events` 수집/보존/조회 API 표준화 |
| `ea-infra` | 기존(확장) | infra 모델/저장소 계약 | `infra_assets` 카탈로그 모델 + owner/env/criticality 인덱스 |
| `ea-flow` | 기존(확장) | 실행/데이터 모델 | `flow_execution`과 `evidence_bindings` 연동, pipeline 상태 이벤트 표준화 |
| `ea-projection` | 기존(확장) | 표층 산출물 관리 | artifact type(`api/tool/page/url/file/identifier`) 강제, source layer 매핑 검증 |
| `ea-decision` | 기존(확장) | 의사결정 모델 | `service_ops_events` 입력 기반 decision 피드백 경로 연결 |
| `ea-needs` | 기존(확장) | needs 정제 모델 | 운영 이벤트 기반 needs 재정제 계약 연결 |
| `ea-trace` | 신규(코어) | trace/evidence 공통 유틸 | trace chain 조립, lineage 재생, evidence binding validator 공통 모듈 제공 |
| `ea-ops` | 신규(코어) | 서비스 운영 어휘 표준 | incident/slo/deploy/rollback 이벤트 스키마 및 정규화 제공 |
| `sdlc-domain` | 기존(도메인) | 도메인 검증 레퍼런스 | v2 계약을 실증하는 reference domain 유지 |

## 4. 권장 모듈 경로(초안)
### 4.1 기존 패키지 확장
- `packages/ea-profile/src/ea_profile/v2/types.py`
- `packages/ea-profile/src/ea_profile/v2/loader.py`
- `packages/ea-profile/src/ea_profile/v2/validator.py`
- `packages/ea-kernel/src/ea_kernel/v2/profile_registry.py`
- `packages/ea-governance/src/ea_governance/v2/event_ledger.py`
- `packages/ea-infra/src/ea_infra/v2/asset_catalog.py`
- `packages/ea-projection/src/ea_projection/v2/artifact_contract.py`
- `packages/ea-flow/src/ea_flow/v2/execution_evidence.py`

### 4.2 신규 패키지
- `packages/ea-trace/src/ea_trace/chain.py`
- `packages/ea-trace/src/ea_trace/evidence.py`
- `packages/ea-ops/src/ea_ops/events.py`
- `packages/ea-ops/src/ea_ops/slo.py`

## 5. 구현 순서 (패키지 기준)
1. `ea-profile` (v2 스키마/validator)
2. `ea-kernel` (registry/discovery/composer)
3. `ea-governance` + `ea-trace` (ledger/trace 체인)
4. `ea-infra` + `ea-ops` (infra 자산/ops 어휘)
5. `ea-flow` + `ea-projection` (실행-표층 연결)
6. `ea-decision` + `ea-needs` (피드백 루프 연계)
7. `sdlc-domain` 회귀 검증

## 6. 관련 문서
- `docs/m2-v2-draft.md`
- `docs/system-usecases.md`
- `docs/system-foundation.md`
