# EA System 용어 정의 (Glossary)

## 1. 목적
- 이 문서는 EA System에서 반복적으로 사용하는 핵심 용어를 일관되게 정의한다.
- 대상: `M2/M1/M0`, `profile`, `validator`, 레이어/추적/표층 관련 용어.
- 본 문서는 정책 문서가 아니라 **공통 언어 계약** 문서다.

## 2. 계층 용어
| 용어 | 정의 |
| --- | --- |
| `M2` | 메타모델 계약 계층. 시스템이 허용하는 어휘(요소/관계/규칙/흐름)와 검증 기준을 정의한다. |
| `M1` | 프로파일 계층. 도메인별로 M2 어휘를 사용해 실제 모델(요소/관계/규칙/전이)을 선언한다. |
| `M1P` | Projection된 M1 view. M1 raw를 탐색 목적에 맞게 추상화한 표층 표현 계층이다. |
| `M0` | 런타임/인스턴스 계층. 실제 저장 데이터, 실행 상태, 이벤트 기록이 존재하는 계층이다. |

## 3. 모델링 핵심 용어
| 용어 | 정의 |
| --- | --- |
| `Kernel` | 비즈니스 로직 뼈대를 정의하는 중심 계층. 핵심 개념/관계/규칙의 기준점이다. |
| `Layer` | 시스템 책임을 분리하는 구조 단위. 예: infra, decision, needs, kernel, flow, projection, governance. |
| `Domain` | 특정 업무 맥락의 모델 집합. 예: governance domain, sdlc domain. |
| `Profile` | M1 선언 단위. TOML로 정의되는 도메인 모델 문서(요소/관계/규칙/전이/메타데이터). |
| `ProfileSpec` | profile 자체의 식별/버전/네임스페이스 등 상위 메타 정의. |
| `Profile Bridge` | profile(TOML)를 로딩하고 schema/condition registry를 연결하는 어댑터 모듈. |
| `Category` | element의 의미 분류 단위. 예: ActiveStructure, Behavior, PassiveStructure. |
| `Element` | profile이 정의하는 도메인 개체 타입. |
| `Relation` | element 간 연결 타입. 예: contains, depends_on, next, produces. |
| `Validity Rule` | element/relation 조합의 허용/금지를 선언하는 규칙. |
| `State Token` | lifecycle 상태의 canonical 식별자. |
| `Transition` | state token 간 허용 가능한 상태 전이 정의. |
| `Artifact Type` | projection 표층 산출물 타입. 예: api_endpoint, page, tool, url, file, identifier. |
| `Layer Stack` | 레이어 목록과 의존 순서를 정의한 메타 구조. |
| `Flow Edge` | 레이어 간 또는 단계 간 흐름 연결(typed edge). |

## 4. 추적/거버넌스 용어
| 용어 | 정의 |
| --- | --- |
| `Trace Link` | 의사결정-요구-구조-실행-표층 사이 인과 연결을 표현하는 링크 계약. |
| `Governance Event` | 상태 변경/구조 변경/표층 노출 등 핵심 사건을 기록하는 표준 이벤트. |
| `Lineage ID` | 같은 계보(진화 연속성)를 가진 레코드 집합을 묶는 식별자. |
| `Trace ID` | 단일 처리 흐름(요청/결정/실행)을 추적하는 상관관계 식별자. |
| `Audit Trail` | governance event의 불변 시퀀스 기록. |
| `Loop Contract` | `projection -> decision -> needs -> kernel -> flow -> projection` 폐루프를 강제하는 계약. |

## 5. 검증 용어
| 용어 | 정의 |
| --- | --- |
| `Validator` | 선언/실행이 계약을 만족하는지 검사하는 검증기. |
| `Static Validation` | 로드/컴파일 시점 검증. 참조 무결성, 중복, 순환, 필수 경로 존재 등을 검사한다. |
| `Runtime Validation` | 실행/저장 시점 검증. 전이 적합성, trace/event 존재, lineage 연속성 등을 검사한다. |
| `Profile Validation Result` | validator의 결과 객체. pass/fail와 상세 오류 집합을 포함한다. |
| `Compose` | 복수 profile을 결합해 통합 도메인 모델을 만드는 과정. |
| `Namespace` | profile id 충돌을 피하기 위한 식별자 경계. 예: `governance:projection`, `sdlc:projection`. |

## 6. 운영 규칙 (요약)
1. 용어는 문서/코드/API에서 동일 의미로 사용한다.
2. 새 개념 추가 시 먼저 이 문서에 정의를 추가한다.
3. 동의어를 만들기보다 canonical term을 우선 사용한다.
4. 설계 논의 시 "M2에서 강제하는가 / M1에서 선언하는가 / M0에서 실행되는가"를 함께 명시한다.

## 7. 관련 문서
- `docs/system-foundation.md`
- `docs/m2-v2-draft.md`
- `docs/ea-sys-conventions.md`
- `docs/projection-layer-standard.md`
