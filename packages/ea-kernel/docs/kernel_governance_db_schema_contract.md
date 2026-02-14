# Kernel Governance DB Schema Contract (K1 Draft)

## 목적

커널 거버넌스 DB(`rules.db`, `decisions.db`, `versions.db`, `profiles.db`)의
스키마 버전 관리와 마이그레이션 실행 경로를 단일 계약으로 고정한다.

## 대상 DB

- `rules.db`
- `decisions.db`
- `versions.db`
- `profiles.db`

## 버전 추적 규약

1. `rules.db`, `decisions.db`, `versions.db`
- 테이블: `schema_version(version INTEGER PRIMARY KEY)`
- 현재 기준 버전: `1`

2. `profiles.db`
- 테이블: `schema_info(key TEXT PRIMARY KEY, value TEXT NOT NULL)`
- 키: `schema_version`
- 현재 기준 버전: `"2"`

## 마이그레이션 러너 계약

구현 모듈:
- `packages/ea-kernel/src/ea_kernel/migrations/kernel_governance.py`

공개 API:
- `plan_kernel_governance_migrations(data_dir)`
- `apply_kernel_governance_migrations(data_dir, dry_run=False)`
- `format_migration_plan(items)`

동작 원칙:
1. 러너는 DB별 현재 버전을 읽어 pending step만 계획한다.
2. `dry_run=True`는 파일/DB를 생성하지 않는다.
3. 적용은 idempotent 해야 한다(같은 버전 재적용 없음).

## K1 v1 스텝 정의

- `rules` target: rule lifecycle 스키마 bootstrap
- `decisions` target: decision recording 스키마 bootstrap
- `versions` target: corpus version bootstrap + `schema_version` 정규화
- `profiles` target: profile registration 스키마 bootstrap

## K2 v2 스텝 정의 (`profiles`)

- `model_registry` 추가
- `model_versions` 추가
- `validation_runs` 추가
- `schema_info.schema_version = "2"` 업그레이드

## 테스트 계약

- `packages/ea-kernel/tests/test_kernel_governance_migrations.py`

검증 항목:
1. 빈 디렉터리에서 4개 target이 v0 -> v1로 계획되는지
2. dry-run 시 파일 생성이 없는지
3. apply 후 재실행 시 pending 0인지(idempotent)
4. DB별 버전 메타 테이블과 값이 맞는지
