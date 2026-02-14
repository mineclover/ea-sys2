# Kernel Governance Reference v1

## 목적

커널 거버넌스 DB(`rules.db`, `decisions.db`, `versions.db`, `profiles.db`)를
다른 레이어가 재사용할 수 있는 공식 레퍼런스 기준으로 고정한다.

본 문서는 K5 결과물이며, 레퍼런스 데이터셋/골든 스냅샷/호환성 정책을 포함한다.

## 레퍼런스 아티팩트

- 골든 스냅샷(JSON):
  - `packages/ea-kernel/docs/reference/kernel_governance_reference_v1.snapshot.json`
- 생성/검증 스크립트:
  - `packages/ea-kernel/src/ea_kernel/scripts/kernel_governance_reference_snapshot.py`
- 자동 게이트:
  - `make gate-kernel-governance-reference`

## 레퍼런스 데이터셋 구성

시드 입력:
- `packages/ea-kernel/examples/ralph_tui_layers/00-infra.toml`
- `packages/ea-kernel/examples/ralph_tui_layers/10-governance.toml`
- `packages/ea-kernel/examples/ralph_tui_layers/20-decision.toml`
- `packages/ea-kernel/examples/ralph_tui_layers/30-needs.toml`
- `packages/ea-kernel/examples/ralph_tui_layers/40-kernel.toml`
- `packages/ea-kernel/examples/ralph_tui_layers/50-flow.toml`

시드 규칙:
1. 각 레이어는 독립 모델명으로 등록한다: `RalphTUIImplementation.<layer>`
2. 커널 레이어(`.kernel`)만 활성화한다.
3. 커널 레이어는 등록 시 검증 + 독립 재검증 1회를 수행한다.
4. 골든 스냅샷은 비결정적 값(UUID/timestamp)을 직접 고정하지 않고,
   스키마 버전/테이블/행 개수/등록 모델 상태를 고정한다.
5. 각 레이어 프로파일은 공용 런타임 빌더(`build_profile_runtime_schema`)로
   투영한 메트릭(컴파일/오버레이)을 스냅샷에 함께 고정한다.

## 사용법

레퍼런스 스냅샷 생성:
- `uv run python packages/ea-kernel/src/ea_kernel/scripts/kernel_governance_reference_snapshot.py build --force-reset`

레퍼런스 스냅샷 검증:
- `uv run python packages/ea-kernel/src/ea_kernel/scripts/kernel_governance_reference_snapshot.py verify`

통합 게이트:
- `make gate-kernel-governance-reference`

## 호환성 정책 (Semantic Versioning)

DB 레퍼런스 버전 규칙:
- `MAJOR`: 비호환 스키마 변경(컬럼 삭제/타입 변경/제약 강화로 기존 데이터 불가)
- `MINOR`: 하위 호환 확장(테이블/컬럼 추가, 인덱스 추가, 선택 필드 추가)
- `PATCH`: 버그 수정/문서 수정/운영 절차 수정(스키마 계약 무변경)

운영 원칙:
1. `schema_version`(또는 `schema_info.schema_version`)은 단조 증가해야 한다.
2. 마이그레이션은 전진 전용이며 idempotent를 유지한다.
3. N 릴리스는 최소 N-1 데이터셋 검증 경로를 제공해야 한다.

## Deprecation 정책

1. Deprecated 표시는 문서 + 마이그레이션 노트 + 체크리스트에 동시에 기록한다.
2. Deprecated는 최소 1개 MINOR 릴리스 기간 유지 후 MAJOR에서 제거 가능하다.
3. 제거 전 반드시 대체 경로(테이블/컬럼/API)를 명시한다.

## 레이어 확장 가이드

Infra/Governance/Decision/Needs/Flow 레이어 확장 시 커널 레퍼런스 패턴을 복제한다.

필수 복제 항목:
1. `schema_version` 계약과 마이그레이션 러너 패턴
2. 등록 -> 검증 -> 활성화 원자성
3. 드리프트 체크 + 백업/복구 리허설 + 골든 스냅샷 검증

권장 순서:
1. 레이어 전용 DB 스키마 초안
2. 등록/검증 서비스 구현
3. K4 수준 운영 하드닝(드리프트/복구)
4. K5 수준 레퍼런스 스냅샷 고정
