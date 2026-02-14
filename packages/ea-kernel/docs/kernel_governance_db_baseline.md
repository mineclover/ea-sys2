# Kernel Governance DB Baseline (K0)

## 목적

커널 거버넌스 DB의 현재 상태를 동결하고, K1~K5 진행 전 기준점(baseline)으로 사용한다.

## 기준 소스

- `packages/ea-kernel/src/ea_kernel/rule_asset_store.py`
- `packages/ea-kernel/src/ea_kernel/decision_store.py`
- `packages/ea-kernel/src/ea_kernel/corpus_version_store.py`
- `packages/ea-kernel/src/ea_kernel/profile_store.py`
- `packages/ea-kernel/src/ea_kernel/governance.py`

## DB 인벤토리

| DB 파일 | 책임 | 버전 메타 | 주요 테이블 |
|---|---|---|---|
| `rules.db` | Rule lifecycle 저장 | `schema_version` (int) | `rule_assets`, `rule_asset_history` |
| `decisions.db` | 판정/통계 저장 | `schema_version` (int) | `decision_records`, `judgment_statistics` |
| `versions.db` | 코퍼스 스냅샷 저장 | 없음 (K0) | `corpus_versions`, `version_entries` |
| `profiles.db` | 프로파일 등록/태깅 | `schema_info` (`schema_version` key) | `profile_versions`, `profile_tags` |

SQL 스냅샷:
- `packages/ea-kernel/docs/sql_snapshots/k0/rules.sql`
- `packages/ea-kernel/docs/sql_snapshots/k0/decisions.sql`
- `packages/ea-kernel/docs/sql_snapshots/k0/versions.sql`
- `packages/ea-kernel/docs/sql_snapshots/k0/profiles.sql`

## 핵심 유스케이스 10개

1. Draft 규칙 등록 후 조회 가능해야 한다.
2. 규칙 상태 전이(Draft -> Review -> Approved -> Deprecated)가 기록되어야 한다.
3. 규칙 업데이트 시 버전 이력이 누적되어야 한다.
4. 판정 기록 저장 시 triple/source/actor 기준 조회가 가능해야 한다.
5. 판정 저장 시 통계(`judgment_statistics`)가 일관되게 갱신되어야 한다.
6. 코퍼스 버전 생성 시 규칙 엔트리 스냅샷이 함께 저장되어야 한다.
7. 코퍼스 버전 간 diff(added/removed/modified)를 계산할 수 있어야 한다.
8. 프로파일 저장 시 버전 체인(parent)과 content hash가 유지되어야 한다.
9. 프로파일 태그는 profile_name 범위에서 upsert 가능해야 한다.
10. 시스템 재시작 후 DB 데이터가 유지되고 다시 로드되어야 한다.

## 현재 강점

- `rules.db`/`decisions.db`는 초기 스키마 버전 테이블을 갖고 있다.
- 규칙/판정/버전/프로파일 저장소가 분리되어 책임이 명확하다.
- 단위/통합 테스트가 이미 비교적 넓은 범위를 커버한다.

## 현재 결손 (K1에서 해결)

1. `versions.db`에는 스키마 버전 메타가 없다.
2. DB별 마이그레이션 실행 경로가 분산되어 있다.
3. "계획(plan) -> 적용(apply)" 형태의 공통 러너가 없다.
4. 스키마 계약 문서가 코드 위치별로 흩어져 있다.

## 리스크 레지스터

| ID | 리스크 | 영향 | 대응 |
|---|---|---|---|
| R-01 | 저장소별 버전 관리 방식 불일치 | 마이그레이션 실패/혼선 | 공통 runner + 버전 판독 규칙 통합 |
| R-02 | 부분 적용(중간 실패) 시 복구 경로 불명확 | 데이터 정합성 저하 | 단계별 dry-run + idempotent 스텝 |
| R-03 | 등록/검증/활성화 원자성 부재 | 부분 등록 상태 발생 | K2에서 트랜잭션 경계와 롤백 강제 |
| R-04 | 감사 추적 분절(in-memory tx) | 원인 추적 비용 증가 | K3에서 tx 영속화 테이블 도입 |
| R-05 | 운영 절차 미정의(백업/복원) | 장애 복구 지연 | K4 런북/리허설 테스트 추가 |

## 품질 게이트 (K0)

- `make test-kernel`
- `make lint`
- `make typecheck`

