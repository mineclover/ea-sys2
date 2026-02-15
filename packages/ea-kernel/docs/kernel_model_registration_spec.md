# Kernel Model Registration Spec (K2)

## 목적

커널 레이어에서 모델 등록과 정합성 검증을 독립적으로 수행하기 위한
영속 스키마 및 서비스 계약을 정의한다.

핵심 요구:
- 등록 전/후 정합성 검증 가능
- 등록 실패 시 부분 상태가 남지 않는 원자성
- 버전/검증 이력 추적 가능

## 스키마

대상 DB: `profiles.db`

### `model_registry`

- 모델 식별 및 현재 상태 저장
- 컬럼:
  - `model_id` (PK)
  - `model_name` (UNIQUE)
  - `owner`
  - `status` (`registered|active|disabled`)
  - `active_version_id` (nullable)
  - `created_at`, `updated_at`

### `model_versions`

- 모델 버전 스냅샷 저장
- 컬럼:
  - `version_id` (PK)
  - `model_id` (FK -> `model_registry.model_id`)
  - `version` (model-local unique)
  - `content_hash`
  - `profile_data` (serialized profile JSON)
  - `parent_version_id` (nullable)
  - `created_by`, `created_at`

### `validation_runs`

- 검증 실행 이력 저장
- 컬럼:
  - `run_id` (PK)
  - `model_id` (FK)
  - `version_id` (FK)
  - `validator`
  - `passed` (0/1)
  - `errors_json`
  - `context_json`
  - `created_at`

## 서비스 계약

구현:
- `packages/ea-kernel/src/ea_kernel/model_registration.py`

### Register (원자성)

`register(profile, owner, created_by, context)`:
1. `model_registry` 확보(신규 생성 또는 기존 row update)
2. `model_versions` insert
3. `ProfileAuditor`로 검증 실행
4. `validation_runs` insert
5. 검증 실패 시 전체 rollback

보장:
- 실패 시 `model_registry/model_versions/validation_runs`에 부분 row 없음
- 동일 `(model_id, version)` 중복 등록 차단

### Activate

`activate(model_name, version, actor)`:
- 지정 버전에 `passed=1` 검증 이력이 있어야 활성화 가능
- 성공 시 `model_registry.active_version_id` 설정 + `status=active`

### Independent Validation

`validate_registered(model_name, version, context)`:
- 이미 등록된 버전을 재검증하고 `validation_runs`에 추가 기록
- 등록 상태와 독립적으로 실행 가능

## 마이그레이션

- K2는 `profiles` target schema version `2`에서 활성화
- 구현: `packages/ea-kernel/src/ea_kernel/migrations/kernel_governance.py`
  - step `v1 -> v2`: `model_registry`, `model_versions`, `validation_runs` 추가

## 테스트

- `packages/ea-kernel/tests/test_kernel_governance_migrations.py`
  - profiles v2 스키마/테이블 존재 검증
- `packages/ea-kernel/tests/test_kernel_governance_registration.py`
  - 등록 성공/실패 rollback/중복 방지/활성화/독립 재검증

## 운영 진입점

### CLI

- `python -m ea_kernel model register <toml> [--db-path ...]`
- `python -m ea_kernel model validate <model_name> <version> [--db-path ...]`
- `python -m ea_kernel model activate <model_name> <version> [--db-path ...]`
- `python -m ea_kernel model show <model_name> [--db-path ...]`

### API

- `POST /models/register`
- `POST /models/validate`
- `POST /models/activate`
- `GET /models/{model_name}`

## EA-SYS 거버넌스 모델 계약 (v0.4.2)

`ea-sys` 기준으로 `/models/*` 엔드포인트를 TOML 모델로 명시한다.

- 파일: `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/10-governance.toml`
- 엔트리포인트: `GovernanceEntryPort`
- 엔드포인트 요소:
  - `ModelRegisterEndpoint`
  - `ModelValidateEndpoint`
  - `ModelActivateEndpoint`
  - `ModelStateEndpoint`
  - `ModelDecisionTraceEndpoint`
- 요청/응답/오류/트랜잭션 레코드:
  - `ModelRegisterRequestRecord`, `ModelRegisterResponseRecord`
  - `ModelValidateRequestRecord`, `ModelValidateResponseRecord`
  - `ModelActivateRequestRecord`, `ModelActivateResponseRecord`
  - `ModelStateQueryRecord`, `ModelStateResponseRecord`
  - `ModelDecisionTraceQueryRecord`, `ModelDecisionTraceResponseRecord`
  - `ModelDecisionTraceExploreResponseRecord`
  - `ModelApiErrorRecord`, `ModelTransactionRecord`
  - `ModelEvidenceWarningRecord`

엔드포인트 계약 원칙:

1. 모든 `/models/*` 요청은 `GovernanceEntryPort`를 통과한다.
2. 모든 `/models/*` 엔드포인트는 `KernelModelPort`로 위임된다.
3. 각 엔드포인트는 요청 레코드를 `consumes`, 응답/오류/트랜잭션 레코드를 `produces`한다.
4. 등록/검증/활성화/조회 라우팅은 각각 `LayerModelRegistry`, `ValidationCoordinator`, `ActivationCoordinator`, `VersionLifecycleManager`와의 `coordinates` 관계로 고정한다.

API 오류 응답 계약:

- `/models/*` 오류는 `ModelApiErrorRecord` 형식으로 반환한다.
  - `status_code`
  - `detail`
  - `category`

API 성공 응답 계약:

- 등록/검증/활성화 응답은 `transaction_id`를 포함하여 `ModelTransactionRecord` 추적을 지원한다.
- 등록/검증/활성화 요청은 선택적으로 `decision_id`, `evidence_refs[]`를 포함할 수 있다.
- `decision_id`가 제공되면 거버넌스는 `DecisionTraceContract v1`를 decision 레이어에 기록한다.
- `evidence_refs[]`가 비어있으면 `missing_evidence_refs` 경고를 `ModelEvidenceWarningRecord` 및 트랜잭션 이벤트(`decision_trace_warning`)로 남긴다.

Decision trace 조회 계약:

- `GET /models/decisions/{decision_id}`
  - raw `DecisionTraceContract v1` payload 반환
- `GET /models/decisions/{decision_id}/explore`
  - 근거(`evidence`) / 영향(`impact`) / 변경 이력(`history`) 탐색 뷰 반환

검증:

- `packages/ea-kernel/examples/validate_ea_sys_layers.py --simulate`
  - `governance-entrypoint`
  - `governance-model-api-contract`
  - `layer-6x6-contract`
  - `layer-6x6-owner: flow`
  - `entrypoint-order: decision > needs > kernel > flow`
  - `infra-role: row-data-design`
  - `governance-role: system-entrypoint-design`
  위 계약/소유자 기준이 모두 `passed`여야 한다.

### EA System 레이어 검증 스크립트 연동

- `packages/ea-kernel/examples/validate_ea_sys_layers.py`
- 등록 옵션:
  - `--register`
  - `--db-path`
  - `--register-name-mode layer|profile`
  - `--activate`
- 기본 `register-name-mode=layer`는 모델명을 `{profile}.{layer}`로 생성해
  레이어별 독립 등록/검증을 보장한다.
