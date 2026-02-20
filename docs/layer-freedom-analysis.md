# SDLC Layer Freedom Analysis (US-023)

## 범위
- 비교 대상:
  - 대칭 매핑: `packages/ea-kernel/src/ea_kernel/profiles/sdlc/00-layer-stack.toml`
  - 고유 계층: `packages/ea-kernel/src/ea_kernel/profiles/sdlc_native/00-layer-stack.toml`
- 비교 목적: 동일 SDLC 도메인을 서로 다른 레이어 구조로 모델링할 때, M2가 허용/제약하는 자유도의 실제 경계를 문서화한다.

## 1) 대칭 매핑(US-011) 분석

### 장점 (표현 가능한 항목)
| 항목 | 내용 |
| --- | --- |
| 거버넌스 스켈레톤 재사용 | `DevInfra -> ArchDecision -> Requirements -> DomainModel -> Pipeline` 체인과 `DevGovernance` 제어 레이어를 선언해 기존 거버넌스 구조를 SDLC로 치환 가능 |
| Cross-layer 제어 평면 모델링 | `DevGovernance`가 다수 레이어에 동시에 의존하는 제어 관점을 `depends_on`으로 표현 가능 |
| 레이어 메타데이터 분리 | `responsibility`, `model_perspective`를 각 레이어에 독립 선언해 용어/책임 치환을 쉽게 유지 가능 |

### 한계 (표현 불가능/약한 표현 항목)
| 항목 | 한계 내용 |
| --- | --- |
| "대칭성" 자체 검증 부재 | M2는 "원본 도메인과 1:1 구조 동형" 여부를 검증하지 못한다. 현재는 사람이 설계 의도를 유지해야 한다. |
| flow 의미 검증 부재 | `definition_flow/runtime_flow/feedback_flow`는 문자열이므로 경로 유효성/순서 의미를 정적으로 강제하지 못한다. |
| 제어 레이어 의미 강제 부재 | `DevGovernance`를 마지막/제어 레이어로 유지해야 한다는 도메인 의도는 메타데이터 수준에서 강제되지 않는다. |

## 2) 고유 계층(US-012) 분석

### 장점 (표현 가능한 항목)
| 항목 | 내용 |
| --- | --- |
| 도메인 고유 단계 반영 | `Planning/Implementation/Verification/Deployment/Monitoring` 같은 SDLC 고유 단계를 직접 선언 가능 |
| 비선형 의존 그래프 표현 | `Verification <- (Planning, Implementation)`, `Monitoring <- (Deployment, Verification)` 같은 fan-in/fan-out DAG를 표현 가능 |
| 대칭 구조와 독립 공존 | 대칭 스택과 고유 스택이 동일 커널 M2에서 동시에 `validate_profile` 통과 가능 |

### 한계 (표현 불가능/약한 표현 항목)
| 항목 | 한계 내용 |
| --- | --- |
| 단계 의미론 검증 부재 | `Planning -> Implementation -> ...`이 실제 SDLC 단계 논리와 일치하는지 M2가 판단하지 못한다. |
| flow-graph 일관성 자동검증 부재 | flow 문자열과 `depends_on` 그래프가 서로 정합적인지 교차 검증하지 않는다. |
| 규칙 타입 표현 한계 | 의존성은 `depends_on` 단일 타입으로만 표현되어, "hard/soft dependency", "approval gate" 같은 의미를 구분하기 어렵다. |

## 3) 동일 도메인 2개 구조의 프로파일 rule 차이

| 비교 축 | 대칭 매핑(`sdlc`) | 고유 계층(`sdlc_native`) | 해석 |
| --- | --- | --- | --- |
| 레이어 수 | 6 (`DevGovernance` 포함) | 5 | M2는 레이어 개수 자체를 제한하지 않는다. |
| 핵심 그래프 형태 | 선형 체인 + 제어평면 허브(DevGovernance) | 단계 중심 DAG(Verification/Monitoring 다중 의존) | M2는 chain/star/DAG 모두 수용한다(순환만 금지). |
| runtime 관점 | `DevGovernance`에서 시작해 실행 제어 강조 | `Implementation`에서 시작해 실행 단계 강조 | runtime 의미는 설계자가 문자열로 선언한다. |
| feedback 관점 | Pipeline 결과를 DevGovernance가 흡수 후 전 레이어 환류 | Monitoring 중심의 운영 피드백 환류 | 피드백 경로도 의미 검증 없이 선언 가능하다. |
| 검증 결과 | `validate_profile` + 레이어 스택 검증 통과 | `validate_profile` + 레이어 스택 검증 통과 | 두 구조 모두 동일 M2 계약 위에서 적합하다. |

## 4) 결론: M2의 실질 제약 범위

### M2가 실제로 강제하는 제약
- 구조 건전성 제약:
  - 레이어 `order` 중복 금지
  - `depends_on`의 참조 무결성(존재하는 레이어만 참조)
  - 순환 의존 금지
- 로더 레벨 보강 제약:
  - 의존 방향(`dep.order < layer.order`) 검증

### M2가 강제하지 않는 영역
- 어떤 레이어를 써야 하는지(명명/개수/책임/관점) 자체
- 대칭 매핑인지, 고유 계층인지 같은 설계 철학
- flow 문자열의 경로 의미, graph와의 정합성, 단계 의미론

### 최종 판단
- M2는 **레이어 구조를 폭넓게 허용**한다. 즉, 대칭 매핑과 고유 계층 모두를 수용할 정도로 설계 자유도가 크다.
- 동시에 M2 제약은 주로 **구조 위생(참조/순환/방향)**에 집중되어 있어, 아키텍처 의미론(왜 이 구조인가)에 대한 강제력은 낮다.
- 따라서 "M2가 제약을 가하느냐"에 대한 답은 **예(구조적 제약은 강함), 그러나 의미적 제약은 약함**이다.
