# Kernel Governance Reference Checklist (v1)

## 릴리스 체크

- [x] 스키마 계약 문서가 최신 코드와 일치한다.
  - `packages/ea-kernel/docs/kernel_governance_db_schema_contract.md`
- [x] 등록/검증 계약 문서가 최신 코드와 일치한다.
  - `packages/ea-kernel/docs/kernel_model_registration_spec.md`
- [x] 트랜잭션 영속 계약 문서가 최신 코드와 일치한다.
  - `packages/ea-kernel/docs/kernel_governance_transaction_contract.md`
- [x] 백업/복구 런북이 체크섬 + 리허설 절차를 포함한다.
  - `packages/ea-kernel/docs/runbooks/kernel_governance_backup_restore.md`

## 자동 검증 체크

- [x] 드리프트 체크 자동화
  - `make check-kernel-governance-drift`
- [x] 복구 리허설 자동화
  - `make rehearse-kernel-governance-recovery`
- [x] K2/K3/K4 회귀 테스트 통과
  - `make test-kernel-governance-db`
- [x] K5 레퍼런스 스냅샷 테스트 통과
  - `make test-kernel-governance-reference`
- [x] 레퍼런스 스냅샷 생성/검증 게이트 통과
  - `make gate-kernel-governance-reference`

## 레퍼런스 아티팩트 체크

- [x] 골든 스냅샷 파일 존재
  - `packages/ea-kernel/docs/reference/kernel_governance_reference_v1.snapshot.json`
- [x] 생성/검증 스크립트 존재
  - `packages/ea-kernel/src/ea_kernel/scripts/kernel_governance_reference_snapshot.py`
- [x] 공식 레퍼런스 문서 존재
  - `packages/ea-kernel/docs/kernel_governance_reference_v1.md`

## 확장 준비도 체크

- [x] 커널 패턴(마이그레이션/등록/검증/복구/스냅샷)이 문서화되어 있다.
- [x] 타 레이어 적용 시 최소 복제 단위가 정의되어 있다.
- [ ] 타 레이어 전용 DB는 아직 미구현(다음 단계 범위).
