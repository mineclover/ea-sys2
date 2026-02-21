# EA System 기본 구조 설명

## 1. 목적
- 이 문서는 시스템의 기본 구조와 각 레이어의 존재 목적을 설명한다.
- 특히 `profile`과 `validator`가 시스템에서 어떤 역할을 하는지 공통 이해를 맞추는 데 목적이 있다.

## 2. 시스템 한 줄 정의
- EA System은 **의사결정과 필요성(인과 기억)**, **구조와 실행(구조화된 기억)**, **표층 노출(경험 산출물)**을 분리하고,
  이를 **거버넌스 원장**으로 추적 가능한 폐루프로 운영하는 모델 기반 시스템이다.

## 3. 레이어별 의미와 존재 이유

### 3.1 Infra
- 역할: 실행 기반 substrate.
- 목적: 저장소/전송/실행/관측 환경의 기술 제약을 모델 계약으로 고정한다.
- 왜 필요한가:
  - 모델이 실제 실행 환경 제약을 무시하지 않도록 경계 조건을 제공한다.
  - 구현이 바뀌어도 상위 레이어가 기대하는 기반 capability 계약은 유지된다.

### 3.2 Decision
- 역할: 인과 판단 계층.
- 목적: 표층 관측과 근거를 바탕으로 무엇을 바꿀지 의사결정한다.
- 핵심 산출물: `decision_record`, `rationale`, `decision_state`.

### 3.3 Needs
- 역할: 인과 정제 계층.
- 목적: 의사결정에서 도출된 방향을 요구/필요 구조로 정제한다.
- 핵심 산출물: `need_record`, `priority`, `need_state`.

### 3.4 Kernel
- 역할: 비즈니스 로직 뼈대(Business Skeleton).
- 목적: 도메인 핵심 개념, 관계, 불변 규칙을 정의한다.
- 핵심 질문: "무엇이 본질 구조인가?"
- 핵심 산출물: `domain_skeleton`, `kernel_change`, `rule_asset`.

### 3.5 Flow
- 역할: 데이터 모델링/실행 모델 계층.
- 목적: Kernel에서 정의된 뼈대를 데이터 관점으로 실행 가능한 흐름으로 변환한다.
- 핵심 질문: "데이터는 어떤 구조로, 어떤 순서로, 어떤 상태를 거쳐 흐르는가?"
- 핵심 산출물: `data_model`, `flow_execution`, `flow_state`.

### 3.6 Projection
- 역할: 최종 표층 산출물 관리 계층.
- 목적: 구현 결과를 사용자/운영자가 인지 가능한 artifact로 노출한다.
- 관리 대상 예시:
  - `api`
  - `tools`
  - `page`
  - `url`
  - `file`
  - `identifier`
- 핵심 산출물: `surface_artifact`, `surface_summary`.

### 3.7 Governance
- 역할: 시스템 원장(System Ledger).
- 목적: 전 레이어의 핵심 사건을 기록하고, 인과/정합성/감사를 가능하게 한다.
- 핵심 산출물: `governance_event`, `audit_trail`.

## 4. 기본 루프
- 시스템의 핵심 루프는 다음과 같다.
  - `projection -> decision -> needs -> kernel -> flow -> projection`
- 의미:
  - Projection의 관측 결과가 Decision으로 들어가고,
  - Needs 정제를 거쳐 Kernel 구조를 수정/강화하고,
  - Flow가 이를 실행 가능한 데이터 모델로 전개하고,
  - 결과가 다시 Projection으로 노출된다.
- Governance는 이 전 과정을 이벤트 체인으로 기록한다.

## 5. 구현은 외부 영역, 모델은 내부 계약
- 구현 세부(프레임워크/런타임/서비스 코드는) 외부 영역으로 본다.
- 내부 시스템은 "무엇을 노출하고 어떻게 추적할 것인가"를 계약으로 유지한다.
- 따라서 구현이 변경되어도 다음 계약은 유지되어야 한다.
  - Artifact 타입의 일관성
  - 상태 전이의 정합성
  - trace/event 기반 인과 추적 가능성

## 6. Profile의 역할
- Profile은 M1 선언 단위다.
- 각 도메인은 profile로 다음을 선언한다.
  - 요소/관계 어휘
  - 규칙(허용/금지)
  - 상태/전이
  - 표층 artifact 타입
  - 레이어/흐름 메타데이터
- 요약: profile은 "도메인 모델의 계약 문서"다.

## 7. Validator의 역할

### 7.1 정적 validator
- 로드/컴파일 시점에 모델 계약 자체의 건전성을 검사한다.
- 예:
  - 참조 무결성
  - 중복/순환
  - 필수 경로 존재
  - 선언 필드 완결성

### 7.2 런타임 validator
- 실행/저장 시점에 계약 준수 여부를 검사한다.
- 예:
  - 상태 전이 적합성
  - 필수 trace link 존재
  - governance event 발행 누락
  - lineage 연속성 단절

## 8. 최소 운영 원칙
1. M2는 계약과 검증 기준을 정의한다.
2. M1(profile)은 도메인 모델 값을 선언한다.
3. M0는 실행 결과를 기록한다.
4. Projection은 최종 경험 산출물을 표준 타입으로 관리한다.
5. Governance 이벤트 없이 핵심 상태 변경이 일어나지 않도록 한다.

## 9. 관련 문서
- 용어: `docs/system-terminology.md`
- use case: `docs/system-usecases.md`
- v2 초안: `docs/m2-v2-draft.md`
- 공통 컨벤션: `docs/ea-sys-conventions.md`
- Projection 표준: `docs/projection-layer-standard.md`
