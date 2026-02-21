# EA System 목적 기반 Use Case

## 1. 문서 목적
- 본 문서는 EA System의 목표를 **검증 가능한 use case**로 명시한다.
- 목표:
  - 데이터 파이프라인, 비즈니스 의사결정, 프로그램 구현, 비즈니스 로직, 데이터 구현, 서비스 관리의
    시스템적 가시화와 거버넌스 설계를 가능하게 한다.
  - 회사 인프라 명칭/구성/계층/구현 결과를 명시적으로 추적 가능하게 만든다.

## 2. 기본 설계 충분성 검토 (요약)
| 평가 항목 | 현재 설계 상태 | 판정 |
| --- | --- | --- |
| 레이어 책임 분리(Decision/Needs/Kernel/Flow/Projection/Governance/Infra) | `docs/system-foundation.md`, `docs/m2-v2-draft.md`에 정의됨 | 충족 |
| 인과 폐루프(`projection -> decision -> needs -> kernel -> flow -> projection`) | v2 초안의 loop contract로 정의됨 | 충족 |
| 표층 산출물 타입(API/Tools/Page/URL/File) 관리 | v2 artifact type 초안에 포함 | 충족 |
| 전사 인프라 자산 명칭의 체계적 카탈로그화 | 방향성만 존재, 표준 자산 스키마 미정 | 부분 |
| 서비스 관리(운영 건강도/SLO/Incident/Runbook) 모델링 | 거버넌스 이벤트 기반은 있으나 운영 어휘 미흡 | 부분 |
| 구현 결과와 모델 간 자동 추적(코드/배포/운영 증거 연동) | trace/event 계약은 있으나 연결 표준 미완성 | 부분 |

## 3. 필수 Use Case 목록

### UC-01. 전사 인프라 자산 카탈로그 가시화
- 목적: 모든 인프라 리소스(서비스, DB, 큐, 스토리지, 네트워크)를 명칭/소유조직/환경 단위로 식별 가능하게 노출.
- 최소 충족 기준:
  1. Infra profile에 자산 타입과 식별 규칙이 선언된다.
  2. 자산은 `lineage_id`, `owner`, `environment`를 가진다.
  3. Projection에서 자산별 URL/File/API 문서 링크가 노출된다.

### UC-02. 의사결정 근거 추적
- 목적: 특정 변경이 왜 발생했는지 Decision/Needs 근거를 재생 가능하게 유지.
- 최소 충족 기준:
  1. `decision_record -> need_record -> kernel_change` trace link가 필수다.
  2. 각 전이 이벤트에 `trace_id`, `actor`, `reason`, `evidence_refs`가 존재한다.
  3. 거버넌스 이벤트 로그만으로 변경 사유를 역추적할 수 있다.

### UC-03. 비즈니스 로직 뼈대 가시화
- 목적: Kernel 계층에서 도메인 핵심 개념/규칙/경계를 명시적으로 확인.
- 최소 충족 기준:
  1. 핵심 엔티티/관계/금지 규칙이 profile rule로 선언된다.
  2. 변경 전후 뼈대 diff(`kernel_change`)가 저장된다.
  3. rule 위반은 validator에서 즉시 검출된다.

### UC-04. 데이터 모델/파이프라인 실행 가시화
- 목적: Flow 계층에서 데이터 모델과 실행 경로를 상태 기반으로 추적.
- 최소 충족 기준:
  1. 데이터 모델 단위(`data_model`)와 실행 단위(`flow_execution`)가 분리 정의된다.
  2. 상태 전이(`queued/building/...`)가 선언형으로 검증된다.
  3. 실행 결과가 Projection artifact로 연결된다.

### UC-05. 구현 결과 표층 관리
- 목적: 구현 결과를 최종 경험 산출물 단위로 관리.
- 최소 충족 기준:
  1. `api`, `tools`, `page`, `url`, `file`, `identifier`를 artifact type으로 선언한다.
  2. artifact는 source layer/element와 연결된다.
  3. 미선언 artifact type은 런타임에서 차단된다.

### UC-06. 서비스 운영 관리
- 목적: 운영 관점에서 서비스 상태를 거버넌스 가능하게 가시화.
- 최소 충족 기준:
  1. 서비스 상태 이벤트(`degraded`, `incident_open`, `recovered`)가 governance event로 표준화된다.
  2. SLO/SLI, 장애 티켓, 런북 링크가 trace chain에 연결된다.
  3. 운영 이슈가 Decision/Needs 재정제로 이어지는 루프를 지원한다.

### UC-07. 멀티 도메인 공존과 격리
- 목적: 여러 도메인(예: governance, sdlc)이 충돌 없이 동일 커널에서 동작.
- 최소 충족 기준:
  1. profile namespace 격리가 강제된다.
  2. 도메인별 validator가 교차 간섭 없이 동작한다.
  3. 공통 Projection 엔진으로 서로 다른 artifact 세트를 출력한다.

### UC-08. 변경 영향 및 감사 대응
- 목적: 변경이 어떤 계층/서비스/산출물에 영향을 주는지 빠르게 확인.
- 최소 충족 기준:
  1. 변경 단위마다 영향 대상(`affected_layers`, `affected_artifacts`)이 계산된다.
  2. governance audit trail이 immutable 정책을 따른다.
  3. 감사 요청 시 trace chain 재생 리포트를 즉시 생성할 수 있다.

## 4. 현재 설계 대비 갭 (보완 필요)
1. Infra 자산 모델 표준 부족:
   - 자산 타입 taxonomy, 명명 규칙, 환경/소유자 메타 스키마 추가 필요.
2. 운영 서비스 관리 어휘 부족:
   - SLO/SLI, incident, change window, runbook artifact 타입 도입 필요.
3. 구현-모델 자동 연결 표준 미완:
   - 배포 파이프라인/코드 저장소/모니터링 결과를 trace link로 자동 연결하는 규격 필요.

## 5. 즉시 반영 권고 (v2 우선순위)
1. `InfraAssetSpec` 추가 (name, type, owner, env, criticality, endpoint/url/file_refs).
2. `ServiceOpsEventSpec` 추가 (incident/slo/deploy/rollback 표준 이벤트).
3. `EvidenceBindingSpec` 추가 (code_commit, ci_run, deploy_id, dashboard_url 연결).

## 6. 관련 문서
- `docs/system-foundation.md`
- `docs/system-terminology.md`
- `docs/m2-v2-draft.md`
- `docs/m2-v2-package-map.md`
