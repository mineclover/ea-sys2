# M2 표현력 한계 보고서 (US-022)

## 범위
- 대상: SDLC 인스턴스화 과정 `US-011` ~ `US-021`
- 기준: `M2에서 직접 선언/검증할 수 없어 Python 하드코딩(또는 테스트 하드코딩)으로 보완한 항목`

## 분류 기준
- `(a) M2 어휘 부족`: 모델에 필요한 개념/필드 자체가 없음
- `(b) M2 규칙 표현력 부족`: 개념은 있으나 제약을 충분히 선언할 수 없음
- `(c) 런타임 제약`: 선언만으로는 불가능하고 실행 시점 상태가 필요
- `(d) 도구 미지원`: 모델은 가능하나 loader/validator/registry가 받쳐주지 못함

## US별 한계 기록
| US | M2로 표현 불가 → Python 하드코딩 필요 항목 | 분류 | 현재 워크어라운드(근거 코드) | 해소 방향 |
| --- | --- | --- | --- | --- |
| US-011 | 레이어 흐름(`definition/runtime/feedback`)이 구조화되지 않은 문자열이라 경로 의미를 정적 검증하기 어려움 | (a), (b) | `LayerStack`가 flow를 `str`로 보관 (`packages/ea-profile/src/ea_profile/types.py:227`), layer validator는 의존/순환만 검증 (`packages/ea-profile/src/ea_profile/profile_validator.py:80`) | **M2 확장**: flow를 문자열이 아닌 typed edge list로 승격 |
| US-011 | 프로파일 파일 해석 대상을 코드 맵으로 수동 등록해야 함 | (d) | SDLC catalog 정적 맵 (`packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py:7`) | **도구 개선**: 디렉터리 스캔 + 메타데이터 기반 자동 등록 |
| US-012 | 대칭/고유 스택 공존 시 loader 모듈을 도메인별로 중복 구현해야 함 | (d) | `sdlc/layer_stack.py`, `sdlc_native/layer_stack.py`가 거의 동일 구조 (`packages/ea-kernel/src/ea_kernel/profiles/sdlc/layer_stack.py:1`) | **도구 개선**: 공통 layer-stack loader 템플릿화 |
| US-013 | 상태 토큰(`PROPOSED`)과 상태 요소명(`ArchDecisionStatusProposed`) 불일치 보정이 필요 | (a), (d) | alias/canonicalization regex 하드코딩 (`packages/ea-profile/src/ea_profile/profile_validator.py:12`, `packages/ea-profile/src/ea_profile/profile_validator.py:186`) | **M2 확장**: 상태 요소에 canonical token 필드 추가 |
| US-014 | underscore 토큰(`IN_PROGRESS`)은 alias 추론만으로 안정 처리 불가해 동일 문자열 요소를 별도 선언해야 함 | (a) | 전이+요소 동시 선언 (`packages/ea-kernel/src/ea_kernel/profiles/sdlc/30-requirements.toml:49`, `packages/ea-kernel/src/ea_kernel/profiles/sdlc/30-requirements.toml:131`) | **M2 확장**: alias 규칙을 명시 선언하거나 transition 토큰 스키마 분리 |
| US-015 | `Service -> Repository -> DataModel` 같은 중간계층 강제는 경로 제약 1개로 못 쓰고 allow+deny 조합으로 수동 구성 | (b) | 허용/금지 rule pair 하드코딩 (`packages/ea-kernel/src/ea_kernel/profiles/sdlc/40-domain-model.toml:90`, `packages/ea-kernel/src/ea_kernel/profiles/sdlc/40-domain-model.toml:138`) | **M2 확장**: path constraint DSL(필수 경유 노드) 추가 |
| US-016 | 파이프라인 체인/게이트 의미를 단일 규칙으로 표현 못해 `next/constrains/triggers`로 분해 필요 | (b) | 단계 체인과 게이트를 개별 rule로 분해 (`packages/ea-kernel/src/ea_kernel/profiles/sdlc/50-pipeline.toml:155`) | **M2 확장**: pipeline-stage/state-gate 전용 규칙 타입 추가 |
| US-017 | 단일 projection 프로파일 validator가 도메인 합성 컨텍스트를 모르므로 오탐 가능 | (d) | 실제 검증은 합성 프로파일 단위로 우회 (progress US-017/021), validator는 단일 profile 기준 (`packages/ea-profile/src/ea_profile/profile_validator.py:138`) | **도구 개선**: validator에 `domain compose context` 모드 추가 |
| US-018 | 상태 전이 적합성은 `직전 스냅샷` 조회가 필요해 선언만으로 강제 불가 | (c) | 저장 직전 lineage latest 조회 후 전이 검사 (`packages/sdlc-domain/src/sdlc_domain/sdlc_store.py:226`, `packages/sdlc-domain/src/sdlc_domain/sdlc_store.py:555`) | **M1 허용**: runtime store contract로 명시 유지 |
| US-019 | 헤드라인 KPI(`requirements_throughput`, `pipeline_success_rate`, `adr_effectiveness`) 매핑이 profile id 문자열에 고정 | (a), (d) | KPI 매핑 하드코딩 (`packages/sdlc-domain/src/sdlc_domain/sdlc_analyzer.py:417`) | **M2 확장** 또는 **도구 개선**: metric 정의를 profile metadata로 외부화 |
| US-019 | success/terminal 상태가 프로파일에 명시되지 않아 depth 기반 추론 알고리즘 필요 | (a), (b) | 상태그래프 depth/terminal/success 계산 (`packages/sdlc-domain/src/sdlc_domain/sdlc_analyzer.py:196`) | **M2 확장**: transition에 terminal/success semantic annotation 추가 |
| US-020 | projection 소스 모델 결합(어떤 프로파일을 합칠지)이 선언되지 않아 도메인별 조합을 코드로 고정 | (a), (d) | SDLC/거버넌스 조합 하드코딩 (`packages/sdlc-domain/src/sdlc_domain/sdlc_projection.py:293`, `packages/sdlc-domain/src/sdlc_domain/sdlc_projection.py:300`) | **M2 확장**: projection profile에 `source_profiles` 선언 |
| US-020 | 저심도 표층 유지를 위한 synthetic edge 생성이 선언 규칙만으로 부족 | (b), (c) | synthetic `contains/depends_on` 주입 (`packages/sdlc-domain/src/sdlc_domain/sdlc_projection.py:142`, `packages/sdlc-domain/src/sdlc_domain/sdlc_projection.py:161`) | **M1 허용**: view adapter의 파생 규칙으로 유지 + 정책화 |
| US-020 | artifact type registry 대상 프로파일 탐색이 특정 도메인 import에 묶여 있음 | (d) | path 탐색 하드코딩 (`packages/ea-projection/src/ea_projection/artifacts.py:29`) | **도구 개선**: registry 기반 profile discovery API 도입 |
| US-021 | raw id 중복(`projection`) 공존 검증을 위해 네임스페이스 prefix를 수동 부여해야 함 | (d) | `governance:*` / `sdlc:*` 수동 분리 (`packages/sdlc-domain/tests/test_multi_domain_coexistence.py:64`) | **도구 개선**: namespaced profile id를 core loader/composer가 1급 지원 |
| US-021 | 도메인별 compose 순서/대상 프로파일 목록을 테스트 코드에서 수동 유지 | (d) | 정적 tuple 유지 (`packages/sdlc-domain/tests/test_multi_domain_coexistence.py:31`) | **도구 개선**: domain manifest 기반 compose 자동화 |

## 분류별 해소 전략
- `(a) M2 어휘 부족` 우선 확장
  - 상태 canonical token
  - projection source profile 선언
  - 분석 metric/semantic 상태(terminal/success) 선언
- `(b) M2 규칙 표현력 부족` 점진 확장
  - path constraint DSL
  - pipeline stage/gate rule type
  - projection view 파생규칙 선언(선택)
- `(c) 런타임 제약`은 M1/runtime 계층 책임으로 명시
  - store 전이검증, synthetic view 보정은 런타임 훅으로 유지
- `(d) 도구 미지원`은 단기 투자 우선
  - profile discovery 자동화
  - namespaced profile load/compose
  - validator의 단일/합성 컨텍스트 모드 분리

## 우선순위 제안
1. P0: 도구 개선(`namespaced loader`, `profile discovery`, `validator context mode`)
2. P1: M2 확장(`state canonical token`, `metric semantics`, `source_profiles`)
3. P2: 고급 규칙 DSL(`path constraint`, `pipeline rule object`)

