# Projection Layer Standard (M1P)

## 1. 목적

M1 raw topology는 정합성은 높지만 탐색 밀도가 과도할 수 있다.  
Projection Layer(M1P)는 동일한 M1 원본 위에 목적별 추상화 뷰를 제공하여,
`멀리서 큰 흐름 → 가까이서 상세 흐름 → 개발자 추적`을 일관된 규격으로 지원한다.

또한 L4(trace)는 단순 데이터 흐름 뷰가 아니라, 의사결정 기반 변경 추적 뷰를 제공해야 한다.
즉 `decision_id`를 기준으로 "판단 근거(evidence) -> 변경 연산(operations) -> 영향(impact)"이
연결된 형태로 탐색 가능해야 한다.
이때 변경 연산은 `cause_type/cause_id`와 `change_phase(planned|applied|superseded|rolled_back)`를
함께 포함해야 하며, needs 연동 시 `kernel_change_phase`와 정합해야 한다.

---

## 2. 계층 모델

- `M2`: 메타-메타 정의(어휘, 규칙 정의)
- `M1(raw)`: 도메인 메타 프로파일의 원본 토폴로지
- `M1P`: 탐색/표현 최적화 프로젝션 레이어 (본 문서 대상)
- `M0`: 런타임 스냅샷/실행 데이터

`M1P`는 원본을 대체하지 않는다. 원본(M1)은 항상 추적 가능해야 한다.

---

## 3. Projection API

### 3.1 Endpoint

- `GET /profiles/{name}/projection`

### 3.2 Query

- `level`: `l0 | l1 | l2 | l3 | l4` (기본 `l0`)
- `lens`: `panorama | overview | capability | interaction | execution | trace`
- `cross_layer`: `true|false`
- `lang`: i18n 언어
- `actor`: actor seed (`l2`에서 주로 사용)
- `depth`: actor/seed BFS depth (actor: 기본 4, seed: 기본 2)
- `max_edges`: projection edge budget override
- `tier`: `ui | function | data | decision | evidence` — 관심사별 카테고리 포커싱 (지정 시 level의 `allowed_categories`를 대체)
- `seed`: 임의 요소 이름 — 해당 요소 기준 BFS 스코핑 (전체 관계 adjacency 사용)

### 3.3 Response

기본 구조는 `/profiles/{name}/topology`와 동일하며 `projection` 메타를 추가한다.

- `projection.level`: `L0..L4`
- `projection.lens`: 적용 렌즈
- `projection.budget`: default/effective edge budget
- `projection.filters`: relation/category 필터
- `projection.drilldown.next_levels`: 다음 상세 레벨
- `projection.source`: 프로젝션 생성에 사용한 원본 뷰 정보
- `projection.seed`: seed 정보 (actor seed 또는 element seed)
- `projection.tier`: tier 정보 (name, categories, next_tiers)

---

## 4. 레벨 규약

- `L0 panorama`: 전략 파노라마(핵심 구조/인과)
- `L1 capability`: 경험/기능 책임 맵
- `L2 interaction`: actor 기준 유효 상호작용 경로
- `L3 execution`: step/action/event 실행 체인
- `L4 trace`: 개발자용 데이터/결정 추적
  - `decision trace` 중심: 변경 이유/근거/결과를 함께 조회

각 레벨은 `allowed_relations`, `allowed_categories`, `edge budget`를 고정 규약으로 가진다.

---

## 4.1 Tier 규약

Level은 관계 유형과 엣지 버짓을 제어하고, Tier는 "무엇을 보는가"를 제어한다. 두 축은 직교한다.

| Tier | 카테고리 | 이름 패턴 규칙 | 전이 대상 |
|:-----|:---------|:--------------|:---------|
| **ui** | Page, Interface, Context | — | function |
| **function** | ActiveStructure, Behavior, Executable, Governance | — | data, decision |
| **data** | PassiveStructure, Composite | Evidence 패턴 **제외** | evidence |
| **decision** | Assessment, Goal, Event | — | evidence |
| **evidence** | PassiveStructure | Evidence/Provenance/Rationale/Audit/AnalysisReport/Compliance **포함만** | — |

- `evidence`와 `data`는 같은 `PassiveStructure`를 공유하므로 이름 패턴으로 구분한다.
- Evidence 판별 우선: 이름에 패턴 매치 → evidence, 아니면 → data.
- Tier 정의는 `projection_policy.toml`의 `[m2.tiers]`에 선언된다.

## 4.2 Seed 규약

Seed는 "어디서 출발하는가"를 제어한다. 임의 요소 이름을 seed로 받아 BFS로 스코핑한다.

- Actor focus와 달리 **전체 관계 adjacency** 사용 (actor-interaction 관계만이 아님)
- 기본 depth=2 (seed+tier 조합 시)
- Seed 지정 시 focus mode가 `seed`로 전환되고 view_mode가 `focus`로 강제된다.

---

## 5. 현재 구현 상태 (2026-02-19)

- **ea-projection 패키지** (`packages/ea-projection/`)
  - `ProjectionSchema` (SchemaPort): 18 entities, 10 shared relations
  - `condition_registry`: 3 projection 전용 조건 (SAME_PROJECTION_LEVEL, SAME_LENS_TYPE, SAME_VIEW_MODE)
  - `profile_bridge`: `load_projection_profile()` / `load_projection_profile_from_content()`
  - 테스트: 11 tests (frozen, entity/relation count, SchemaPort compliance)
- **70-projection.toml** 프로파일 (`packages/ea-kernel/src/ea_kernel/profiles/ea_sys/`)
  - 68 elements, 10 relations, 119 rules
  - 7개 ModelPort (자기 + 6개 cross-layer)
  - 6단계 파이프라인: SelectLevel → ApplyLens → ComputeBudget → ExecuteReduction → GenerateView → ValidateView → PublishProjection
  - S3/S4/S5 거버넌스 라이프사이클 요소 포함
- **7x7 ModelPort 확장**: 기존 6개 TOML에 ProjectionModelPort + cross-layer 요소/규칙 추가
- backend
  - `profile_projection()` 서비스 구현
  - `/profiles/{name}/projection` API 구현
  - 레벨별 기본 스펙(`L0~L4`) 적용
  - actor 기반 interaction(`L2`) seed/depth 지원
  - 정책 외부화 구현: `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/projection_policy.toml`
    - `m2`: projection 정책 스키마 계약(level/lens/base_view/focus)
    - `m2.tiers`: tier 정의 (ui/function/data/decision/evidence) + 전이 규칙
    - `m1`: global + layer override 정책 값(관계/카테고리/edge budget)
  - fail-fast 검증: 정책 파싱/계약 위반 시 fallback하지 않고 projection 호출을 400 오류로 종료
  - **Tier 필터링**: 관심사별 카테고리 포커싱 (level의 allowed_categories를 대체)
  - **Seed 스코핑**: 임의 요소 기준 BFS (전체 관계 adjacency, actor focus 일반화)
  - tier/seed 정책 검증: `_validate_projection_policy_document()`에서 tier definitions 검증
- frontend API
  - `fetchProfileProjection()` — `tier`, `seed` 파라미터 추가
  - `useProfileProjection()`
  - `ProfileProjectionResponse`, `TierMeta`, `SeedMeta` 타입

---

## 6. 다음 보강 계획

1. Projection 정책 TOML에 대한 정적 검증기/CI lint 추가
2. 레벨별 품질 가드레일 도입 (node/edge/cross ratio/latency)
3. UI 레벨 스위처(`L0~L4`) + tier 스위처 + drilldown breadcrumb 제공
4. `L4 trace`에 decision/data lineage 오버레이 연결
5. projection explain API (`왜 이 노드/엣지가 보였는지`) 추가
6. Tier 전이 자동 탐색 UI (ui → function → data → evidence 드릴다운)
