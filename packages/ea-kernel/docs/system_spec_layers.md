# EA System Spec Layers (Governance-Managed Formal Model)

본 문서는 EA System의 표준 레이어 순서와 책임을 고정한다.
핵심 원칙은 다음 두 가지다.

- `infra > decision > needs > kernel > flow`는 메인 모델 정의 순서다.
- `governance`는 위 레이어들을 관리하는 별도 시스템이다.
- 모든 레이어는 정형 모델을 표현한다.
- 정책/제약 모델은 중앙집중이 아니라 각 레이어 내부에서 독립적으로 관리한다.
- 런타임 실행 이전에 데이터/제어 흐름을 정적으로 시뮬레이션해 정합성을 검증한다.

## 1. 메인 모델 순서

`infra > decision > needs > kernel > flow`

이 순서는 구현 호출 순서가 아니라, 모델 정의 책임의 상위-하위 체계다.

## 2. 레이어 책임

| Layer | 핵심 책임 | 모델 관점 |
| :--- | :--- | :--- |
| **Infra** | 데이터 관리 | 저장소, 상태, 인덱싱, 입출력 데이터 관리 모델 |
| **Decision** | 의사결정 메타-메타 모델 정의 | 의사결정 활동/상태/옵션/평가/결론 구조 어휘와 전이 규칙 |
| **Needs** | 요구 모델 정의 | 목표/요구/백로그/컨텍스트의 정형 표현 |
| **Kernel** | 도메인 핵심 모델 정의 | 존재론(요소/관계)과 유효성 규칙 |
| **Flow** | 실행/데이터 흐름 모델 정의 | 단계 순서, 입출력 소비/생산, 트리거/전이 |

`Governance`는 위 5개 레이어 전체를 관리하는 관리 시스템으로 동작한다.
- 모델 등록/버전/활성 상태 관리
- 검증 실행 이력 및 진화(승격/폐기) 관리
- `Infra`가 메타-메타 계약(예: 저장 포트/스키마 계약)을 정의할 수 있고, 그 계약 위 제어 구현은 `Governance`가 담당한다.

## 3. 계층 흐름

### 3.1 모델 정의 흐름

`infra -> decision -> needs -> kernel -> flow`

- `infra`가 데이터 관리 모델을 제공한다.
- `decision`이 의사결정 흐름의 메타-메타 구조를 정형화하고 `needs`가 요구를 정형화한다.
- `kernel`이 핵심 의미 체계를 고정한다.
- `flow`가 실행 가능한 절차/데이터 전이를 표현한다.

### 3.2 거버넌스 관리 흐름 (Management Plane)

`governance -> {infra, decision, needs, kernel, flow}`

- 각 레이어 모델의 등록/검증/활성 상태를 관리한다.
- 레이어 진화 이력을 추적하고 기준 버전을 통제한다.

### 3.3 피드백 흐름 (Evidence Plane)

`flow -> kernel -> governance -> decision`

- `flow`에서 생성된 이력/결과를 `kernel` 제약으로 해석한다.
- 결과는 `governance`에 버전 이력과 검증 이력으로 축적된다.
- 누적 근거는 `decision` 흐름/구조 모델 보정으로 환류된다.

## 4. 시뮬레이션 우선 검증

런타임 없이 다음을 먼저 검증한다.

- Layer-local relation integrity: 각 레이어 규칙이 그 레이어 내부 relation 정의와 일치하는지
- Decision coverage: flow 주요 단계가 decision 메타-메타 규칙으로 통제되는지
- Data availability: `consumes` 입력이 `produces`/초기 데이터로 충족되는지
- Sequence integrity: `next` 체인이 단절되지 않는지

즉, 실행 엔진 테스트 이전에 모델 자체의 정합성을 정적 시뮬레이션으로 확인한다.
