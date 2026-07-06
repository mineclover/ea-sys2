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
- 접근식 선택 책임:
  - 동일 문제에 여러 접근식이 있을 때 목적별 공식 선택은 Decision에서 판단 기록으로 남긴다.
  - Needs는 선택된 접근식을 실행 가능한 요구/우선순위/제약으로 정규화한다.

### 3.3 Needs
- 역할: 인과 정제 계층.
- 목적: 의사결정에서 도출된 방향을 요구/필요 구조로 정제한다.
- 핵심 산출물: `need_record`, `priority`, `need_state`.

### 3.4 Kernel
- 역할: 비즈니스 로직 뼈대(Business Skeleton).
- 목적: 도메인 핵심 개념, 관계, 불변 규칙을 정의한다.
- 핵심 질문: "무엇이 본질 구조인가?"
- 핵심 산출물: `domain_skeleton`, `kernel_change`, `rule_asset`.
- 경계 기준:
  - Kernel은 "반드시 성립해야 하는 것"을 소유한다.
  - 예: "주문은 결제 성공 후에만 확정된다"는 Kernel의 `rule_asset`이다.

### 3.5 Flow
- 역할: 데이터 모델링/실행 모델 계층.
- 목적: Kernel에서 정의된 뼈대를 데이터 관점으로 실행 가능한 흐름으로 변환한다.
- 핵심 질문: "데이터는 어떤 구조로, 어떤 순서로, 어떤 상태를 거쳐 흐르는가?"
- 핵심 산출물: `data_model`, `flow_execution`, `flow_state`.
- 경계 기준:
  - Flow는 Kernel 제약이 주어진 상태에서 "실제로 무엇이 어떤 순서로 일어나는가"를 소유한다.
  - 예: "주문 생성 -> 결제 호출 -> 응답 수신 -> 주문 확정 처리"는 Flow의 `flow_execution`이다.

### 3.6 Projection
- 역할: 최종 표층 산출물 관리 계층.
- 목적: 구현 결과를 사용자/운영자가 인지 가능한 artifact로 노출한다.
- Projection artifact 타입은 Core + Extension 구조로 관리한다.
- Core set:
  - `api`
  - `tool`
  - `page`
  - `identifier`
- Extension set:
  - `url`, `file`, `api_endpoint`, `data_schema`, `contract`처럼 도메인별 타입은 artifact registry에 선언해 확장한다.
- 선정 기준:
  - Core set은 외부에 노출되는 최소 표면을 고정한다.
  - 각 레이어의 필수 출력(`decision_record`, `need_record`, `domain_skeleton`, `flow_execution`)은 루프 내부에서 소비되는 중간 산물이다.
  - `surface_artifact`는 이 내부 산물을 Projection이 외부 노출형 artifact로 등록한 결과다.
- 핵심 산출물: `surface_artifact`, `surface_summary`.

### 3.7 Governance
- 역할: 시스템 원장(System Ledger).
- 목적: 전 레이어의 핵심 사건을 기록하고, 인과/정합성/감사를 가능하게 한다.
- 핵심 산출물: `governance_event`, `audit_trail`.
- 이벤트 범위:
  - 필수 기록: 레이어 간 전이, 규범 상태 전이, Kernel 구조/규칙 변경, Projection 노출/폐기, 운영 이벤트가 Decision/Needs로 환류되는 경우.
  - 선택 기록: 레이어 내부 계산 단계, 캐시 갱신, 중간 요약 갱신처럼 인과 체인이나 외부 계약을 바꾸지 않는 변경.

### 3.8 메타 운영 레이어
- Terminology:
  - 전역 용어/별칭/심볼 검색 기준을 제공한다.
  - 런타임 폐루프 노드는 아니지만 각 레이어가 필요할 때 canonical term과 symbol을 조회한다.
- Knowledge:
  - 출처/source, 근거/evidence, 주장/claim, 의사결정 연결을 관리한다.
  - Decision은 판단 근거를 기록할 때 Knowledge claim/evidence를 참조할 수 있다.
- 참조 방식:
  - 기본은 pull 방식이다. 각 레이어와 validator가 필요한 시점에 Terminology/Knowledge registry를 조회한다.
  - 정적 validator는 로드/컴파일 시점에 용어, 심볼, 근거 참조 무결성을 검사한다.
  - Terminology/Knowledge 변경은 governance event로 기록하되, 기존 loop 상태를 자동 변경하지 않는다.

## 4. 기본 루프
- 시스템의 핵심 루프는 다음과 같다.
  - `projection -> decision -> needs -> kernel -> flow -> projection`
- 의미:
  - Projection의 관측 결과가 Decision으로 들어가고,
  - Needs 정제를 거쳐 Kernel 구조를 수정/강화하고,
  - Flow가 이를 실행 가능한 데이터 모델로 전개하고,
  - 결과가 다시 Projection으로 노출된다.
- Governance는 이 전 과정을 이벤트 체인으로 기록한다.

### 4.1 루프 1회 전이 의미
- 루프 한 바퀴는 이전 Projection과 다른 관측 가능한 결과를 남겨야 한다.
- 전이 유형은 `converge`, `expand`, `refine` 중 하나로 분류한다.
- `converge`는 기존 목적에 수렴시키는 변경, `expand`는 표층 산출물/범위 확장, `refine`은 기존 산출물의 의미/근거/연결 정교화를 뜻한다.
- 최소 결과는 다음 중 하나다.
  - 새로운 `surface_artifact` 추가
  - 기존 `surface_artifact`의 lifecycle 상태 전이
  - 기존 artifact의 source/trace 연결 갱신
  - `surface_summary` 갱신과 그 원인 trace 기록
- 위 변화가 없다면 완료된 폐루프가 아니라 관측/검토 단계에 머문 것으로 본다.

### 4.2 `decision -> needs` 순서의 근거
- 이 시스템에서 Needs는 원초적 욕구 목록이 아니라 Decision으로 채택된 판단을 요구 구조로 정제한 결과다.
- Projection 관측은 신호와 해석이 섞여 있으므로, 먼저 Decision이 "무엇을 문제로 볼 것인가"와 "어떤 접근식을 선택할 것인가"를 고정한다.
- Needs는 그 판단을 바탕으로 우선순위, 제약, 전달 단위를 정규화해 Kernel로 넘긴다.

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
6. 핵심 상태 변경은 외부 계약, trace 인과 체인, artifact 노출 상태, Kernel 규칙/구조 중 하나를 바꾸는 변경으로 본다.

## 9. 관련 문서
- 용어: `docs/system-terminology.md`
- use case: `docs/system-usecases.md`
- v2 초안: `docs/m2-v2-draft.md`
- 공통 컨벤션: `docs/ea-sys-conventions.md`
- Projection 표준: `docs/projection-layer-standard.md`
