# Kernel Governance DB Reference Plan (Kernel-First)

## 0) 전제 확인

### 0.1 현재 상태 진단 (코드 기준)

현재 구현은 "커널 거버넌스 DB를 기준으로 레퍼런스를 완성하고, 타 레이어는 순차 확장" 상태다.

- 커널 거버넌스 영속 저장소:
  - `rules.db`, `decisions.db`, `versions.db`
  - 근거: `packages/ea-kernel/src/ea_kernel/governance.py`
- 상위 거버넌스 컨테이너는 커널 시스템을 중심으로 초기화:
  - `KernelSystem(data_dir / "kernel", schema)`
  - 근거: `packages/ea-governance/src/ea_governance/facade.py`
- `ea-governance` 트랜잭션은 SQLite 영속 저장소 기반:
  - `transactions.db`
  - 근거: `packages/ea-governance/src/ea_governance/transaction.py`
- 레이어별 독립 모델 등록/영속 DB는 아직 부재:
  - `ea-infra`, `ea-needs`, `ea-decision`, `ea-flow`는 전용 모델 등록 DB 미구현
  - `ea-governance`는 트랜잭션 DB는 존재하나 레이어 모델 등록 DB는 미구현

### 0.2 본 문서의 범위

- 범위: **커널 레이어의 거버넌스 DB 완성도 상향**
- 비범위: 나머지 레이어(Infra/Governance/Decision/Needs/Flow)의 DB 설계/구현
- 원칙: 커널을 공식 레퍼런스로 완성한 뒤, 동일 패턴을 다른 레이어에 확장

---

## 1) 목표

커널 거버넌스 DB를 아래 조건을 만족하는 **공식 레퍼런스 구현**으로 만든다.

1. 스키마/마이그레이션이 명시적이며 버전 호환 정책이 있다.
2. 모델 등록(Registration)과 정합성 검증(Validation)이 트랜잭션 경계 안에서 재현 가능하다.
3. 장애/복구/백업/감사 로그까지 포함한 운영 기준이 문서화된다.
4. 테스트 스위트가 계약(Contract) 수준으로 동작을 고정한다.

---

## 2) 완료 정의 (Definition of Done)

아래 6개 축을 모두 통과하면 "커널 거버넌스 DB 공식 레퍼런스"로 판정한다.

1. **Schema Contract**
- 테이블, 제약조건, 인덱스, 상태전이 규칙이 문서와 코드에서 일치
- `PRAGMA foreign_keys=ON` 기준 무결성 오류 0

2. **Migration Safety**
- 최소 N-1 -> N, N -> N+1 전진 마이그레이션 검증
- 기존 데이터 손실 0, idempotent 보장

3. **Registration Integrity**
- "등록 -> 검증 -> 활성화"의 원자성 보장
- 실패 시 롤백되어 부분 등록 상태가 남지 않음

4. **Auditability**
- 규칙 변경, 판정, 버전 스냅샷이 모두 추적 가능
- 핵심 이벤트의 actor/time/reason 필드 누락 0

5. **Operational Reliability**
- 백업/복구 리허설 성공
- 락 충돌/재시도 정책 문서화 및 테스트 통과

6. **Reference Documentation**
- ERD + 상태전이 + API 계약 + 운영 런북 완비
- 신규 레이어가 재사용 가능한 템플릿 제공

---

## 3) 핵심 격차 (As-Is -> To-Be)

1. `GovernanceSystem`은 영속 저장소가 존재하나, DB 스키마 계약/버전 정책 문서가 분산되어 있다.
2. 독립 검증은 `load_profile(...)` 중심이며, "등록된 모델" 기준 검증 파이프라인과 연결이 약하다.
3. `ea-governance` 트랜잭션 영속화는 K3에서 해소되었고, 현재는 `transactions.db`로 end-to-end 감사 추적이 가능하다.
4. 커널 거버넌스 DB를 공식 레퍼런스로 선언하기 위한 운영 품질 기준(복구, 백업, 드리프트 탐지)이 아직 부족하다.

---

## 4) 설계 방향 (Kernel Only)

### 4.1 논리 경계

커널 거버넌스 DB는 아래 4개 기능 축을 가진다.

- Rule Lifecycle: 규칙 자산/상태/승격 이력
- Decision Evidence: 판정 기록/증거/링크
- Corpus Versioning: 규칙 집합 스냅샷/복원
- Profile Registration: 모델 등록/버전/태깅/검증 결과

### 4.2 물리 전략

초기에는 기존 파일 분리 전략을 유지한다.

- `rules.db`
- `decisions.db`
- `versions.db`
- `profiles.db` 또는 기존 `profile_store` 파일 경로 표준화

핵심은 "물리 통합"이 아니라 **스키마/트랜잭션/검증 계약의 통합**이다.

### 4.3 등록-검증 표준 시퀀스

1. 모델 등록 요청 수신
2. 스키마 정합성 검증 (`load_profile` + 커널 규칙 검증)
3. 저장소 반영 (버전/태그/메타데이터)
4. 활성화 후보 평가
5. 승인 시 활성화, 실패 시 롤백
6. 이벤트 로그/감사 기록 남김

---

## 5) 단계별 실행 계획

### Phase K0 - Baseline Freeze

목표: 현재 커널 DB 구조를 정확히 동결하고 결손을 계량화한다.

작업:
- 현행 DDL/인덱스/제약조건 인벤토리 문서화
- 핵심 유스케이스 10개 선정(등록/판정/승격/복원/실패)
- 리스크 레지스터 작성

산출물:
- `kernel_governance_db_baseline.md`
- DB별 스키마 스냅샷(SQL)

검증:
- `make test-kernel`

### Phase K1 - Schema Contract + Migration Foundation

목표: 스키마 계약을 버전화하고 마이그레이션 체계를 도입한다.

작업:
- DB별 `schema_version` 관리 테이블 도입
- 마이그레이션 실행기(전진/드라이런) 추가
- FK/UNIQUE/CHECK/INDEX 보강

산출물:
- `packages/ea-kernel/src/ea_kernel/migrations/*`
- `kernel_governance_db_schema_contract.md`

검증:
- 신규 테스트: `test_kernel_governance_migrations.py`

### Phase K2 - Registration Integrity (핵심)

목표: "등록되기 위한 DB 설계"를 구체화하고, 등록-검증 원자성을 확보한다.

작업:
- 등록 메타 모델 확정:
  - `model_registry` (모델 식별/소유/상태)
  - `model_versions` (콘텐츠 해시/부모 버전)
  - `validation_runs` (검증 결과/오류/실행 컨텍스트)
- `ProfileRegistry` + `ProfileStore` + 검증기 통합 파사드 추가
- 등록 실패 롤백 처리

산출물:
- `kernel_model_registration_spec.md`
- 등록 API/CLI 초안 (`register`, `validate`, `activate`)

검증:
- 신규 테스트: `test_kernel_governance_registration.py`
- 케이스: 중복 등록, 충돌 태그, 부모 버전 누락, 실패 롤백

### Phase K3 - Governance Transaction Persistence

목표: 거버넌스 실행 이력을 영속화하여 감사 가능성을 완성한다.

작업:
- 트랜잭션 이벤트 저장소 추가 (`transactions`, `transaction_events`)
- `ea-governance` 실행 경로와 커널 DB 감사 로그 연결
- 트랜잭션 상태 전이 규칙 문서화

산출물:
- `kernel_governance_transaction_contract.md`

검증:
- 신규 테스트:
  - `packages/ea-governance/tests/test_transaction_persistence.py`
  - `packages/ea-governance/tests/test_transaction_manager.py`

### Phase K4 - Reliability & Ops Hardening

목표: 실제 운영 가능한 신뢰성 기준을 충족한다.

작업:
- 백업/복원 절차 및 무결성 체크섬
- 동시성 정책(WAL, retry/backoff, timeout) 명시
- 데이터 드리프트 탐지 스크립트 제공

산출물:
- `runbooks/kernel_governance_backup_restore.md`
- `scripts/check_kernel_governance_drift.py`
- `scripts/rehearse_kernel_governance_recovery.py`
- `Makefile` 게이트 타깃: `gate-kernel-governance-db`

검증:
- 신규 테스트: `test_kernel_governance_recovery.py`
- 장애 주입 테스트(중간 실패/부분 쓰기/락 경합)

### Phase K5 - Official Reference Release

목표: 커널 거버넌스 DB를 공식 레퍼런스로 동결/배포한다.

작업:
- 레퍼런스 데이터셋(seed + golden snapshot)
- 호환성 정책(semantic versioning + deprecation policy)
- 외부 레이어 확장 가이드 작성

산출물:
- `kernel_governance_reference_v1.md`
- `kernel_governance_reference_checklist.md`

검증:
- 전체 게이트 통과 시 v1 태깅

---

## 6) 테스트 보완 계획 (우선순위)

P0:
- 등록 원자성/롤백 테스트
- 마이그레이션 전진 안전성 테스트
- 규칙 라이프사이클 상태전이 불변식 테스트

P1:
- 대량 판정 기록 성능 회귀 테스트
- 동시성(멀티 스레드/멀티 프로세스) 충돌 테스트

P2:
- 백업/복원 시나리오 테스트
- 감사 로그 완전성 테스트(actor/time/reason)

권장 실행 게이트:
- `make test-kernel`
- `make lint`
- `make typecheck`

---

## 7) 일정 제안 (6주)

1주차: K0
2주차: K1
3-4주차: K2
5주차: K3-K4
6주차: K5 + 레퍼런스 릴리스 리뷰

---

## 8) 이후 확장 원칙 (다른 레이어로 전파)

커널 완료 후 나머지 레이어 DB는 "커널에서 검증된 패턴"만 복제한다.

- 스키마 버전 관리 방식 재사용
- 등록-검증 원자성 패턴 재사용
- 감사/복구 런북 템플릿 재사용

즉, 순서는 "커널 레퍼런스 완성 -> 레이어별 적용"으로 가져간다.

---

## 진행 현황 (현재 세션)

- K0: baseline 문서 + SQL 스냅샷 완료
- K1: 마이그레이션 러너(v1) 완료
- K2: 모델 등록/검증 DB 및 서비스 완료
- K3: 트랜잭션 영속화(`transactions`, `transaction_events`) 완료
- K4: 드리프트 체크 + 체크섬 백업/복구 리허설 스크립트 + 복구 테스트 + CI 게이트 완료
- K5: 레퍼런스 v1 문서 + 체크리스트 + 골든 스냅샷 생성/검증 스크립트 + 레퍼런스 게이트 완료
