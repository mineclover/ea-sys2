# EA System Spec Layers (Governance-Managed Formal Model)

본 문서는 EA System의 표준 레이어 순서와 책임을 고정한다.

핵심 원칙:

- `infra > decision > needs > kernel > flow`는 메인 모델 정의 순서다.
- `governance`는 위 레이어들을 관리하는 별도 시스템이다.
- 모든 레이어는 정형 모델을 표현한다.
- 각 레이어는 자기 관점의 전문성과 검증 규칙을 가진 독립 시스템으로 동작한다.
- 각 레이어는 자기 프로파일에서 **다른 레이어를 자기 관점으로 정의**한다. 예: infra는 다른 레이어의 데이터 계약을 정의하고, governance는 다른 레이어의 등록/활성 계약을 정의한다. 이것이 6x6 포트(`*ModelPort`)의 존재 이유다.
- 정책/제약 모델은 중앙집중이 아니라 각 레이어 내부에서 독립적으로 관리한다.
- 런타임 실행 이전에 데이터/제어 흐름을 정적으로 시뮬레이션해 정합성을 검증한다.

## 1. 메인 모델 순서

`infra > decision > needs > kernel > flow`

이 순서는 구현 호출 순서가 아니라, 모델 정의 책임의 상위-하위 체계다.

## 2. 레이어 책임

| Layer | 핵심 책임 | 모델 관점 |
| :--- | :--- | :--- |
| **Infra** | row 데이터 설계 | 저장소, 상태, 인덱싱, 입출력 데이터 관리 모델 |
| **Decision** | 의사결정 메타-메타 모델 정의 | 의사결정 활동/상태/옵션/평가/결론 구조 어휘와 전이 규칙 |
| **Needs** | 요구 모델 정의 | 목표/요구/백로그/컨텍스트의 정형 표현 |
| **Kernel** | 도메인 핵심 모델 정의 | 존재론(요소/관계)과 유효성 규칙 |
| **Flow** | 실행/데이터 흐름 모델 정의 | 단계 순서, 입출력 소비/생산, 트리거/전이 |

`Governance`는 위 5개 레이어 전체를 관리하는 별도 관리 시스템으로 동작한다.
- 모델 등록/버전/활성 상태 관리
- 검증 실행 이력 및 진화(승격/폐기) 관리
- `Infra`가 메타-메타 계약(예: 저장 포트/스키마 계약)을 정의할 수 있고, 그 계약 위 제어 구현은 `Governance`가 담당한다.
- `Governance`는 시스템 진입점 설계를 담당한다.
- 거버넌스 자체의 운영 방식도 메타-메타 모델로 먼저 설계하고, 그 모델대로 운영한다. 즉 거버넌스는 다른 레이어의 관리자인 동시에, 자기 운영 모델의 메타-메타 모델 설계이기도 하다.
- 이를 위해 거버넌스를 2단계로 분리한다:
  - **거버넌스 운영 메타-메타 모델**(공통 어휘·운영 구조 설계): `src/ea_kernel/profiles/governance_profile_stack/00-governance-meta-model.toml`
  - **시스템별 운영 프로파일**(설계된 모델대로 구체화): `src/ea_kernel/profiles/ea_sys/10-governance.toml`, `src/ea_kernel/profiles/governance_profile_stack/20-external-governance.toml`

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

### 3.2.1 런타임 모델 엔트리포인트 체인

`decision -> needs -> kernel -> flow`

- `infra/governance`는 체인 노드가 아니라, 각각 row 데이터 설계/시스템 진입점 설계를 담당한다.

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

## 5. Kernel 레이어 상세

### 5.1 Kernel이 관리하는 3개 자산

| 자산 | 파일 | 역할 |
|:-----|:-----|:-----|
| **Schema** | `specs/kernel_schema.toml` | 커널 메타모델 구조 정의: 20 attributes, 15 entities, 14 relations. 엔티티 상속 트리와 릴레이션 역할 구조의 단일 진실 원천(SSOT) |
| **Rules** | `specs/kernel_rules.toml` | 유효성 규칙: 67 explicit + 14 fallback = 81 total. priority 체계(1/40-50/60/70/80-90)와 조건 시스템(LAYER_ORDER, SAME_BRANCH)으로 관계 허용/금지 판단 |
| **Profiles** | `profiles/ea_sys/*.toml` | 도메인 매핑: 스키마의 추상 타입을 도메인 요소로 구체화. 카테고리 매핑 + 도메인 관계 + 도메인 규칙 3단계 |

### 5.2 6x6 포트 구조에서 Kernel의 역할

Kernel은 다른 5개 레이어를 **도메인 제약 관점**으로 정의한다:

- **Infra**: 커널 아티팩트(spec/rule/profile/audit)의 영속화 계약. 무엇을 어떤 형태로 저장하는가
- **Governance**: 커널 모델의 등록/승인/변경 추적 게이트. 모델 진화가 어떤 절차를 거치는가
- **Decision**: 의사결정 결과가 커널 제약으로 변환되는 경로. 결정이 어떻게 도메인 규칙이 되는가
- **Needs**: 요구사항이 커널 도메인 요소로 매핑되는 경로. 요구가 어떻게 모델로 표현되는가
- **Flow**: 커널 계약이 실행 단계에서 소비/검증되는 경로. 모델이 런타임에 어떻게 사용되는가

각 레이어에 대해 `*ModelPort` 인터페이스 요소를 두고, 해당 포트 아래 4-5개 교차 요소 + 관련 규칙을 배치.

### 5.3 40-kernel.toml 프로파일 구성

| 구간 | 내용 |
|:-----|:-----|
| **내부 구현 요소** | KernelLayer(경계), 4개 서비스(Contract/RuleCompiler/Validation/ProfileRegistry), 3개 아티팩트(CapabilityModel/RuleSet/SpecSnapshot), Goal/Step/Action/Event, Context/Experience/Page/Endpoint |
| **6x6 교차 요소** | 5개 레이어 × 4-5개 요소 = 21개. 각 레이어의 `*ModelPort` 아래 배치 |
| **규칙 3단계** | Pattern 규칙(priority 60, 카테고리 기반) → Explicit 규칙(priority 70, 이름 기반) → Cross-layer 규칙(priority 65/72, 포트-요소 간 구조+행위) |
