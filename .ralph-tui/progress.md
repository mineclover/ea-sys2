# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- KernelProfile에 새 tuple 필드를 추가할 때는 `types -> builder -> loader(TOML) -> serializer(dict/json) -> composer` 경로를 함께 갱신해야 값 손실 없이 round-trip/compose가 유지된다.
- 중첩 TOML 배열 테이블(`[[layer_stack.layers]]`)은 loader에서 `doc["layer_stack"]["layers"]`로 파싱되므로, builder에서 stack 메타(`set_*`)와 항목 누적(`add_*`)을 분리하면 확장 스키마를 안정적으로 수용할 수 있다.
- TOML의 문자열 목록 필드(`input_artifacts`, `output_artifacts`)는 loader에서 `str | list[str]`를 모두 허용해 tuple로 정규화하면 축약 표기와 배열 표기를 동시에 지원하면서 builder/serializer 타입 일관성을 유지할 수 있다.
- 프로파일 정적 검증은 builder 내부 강제 검증과 분리된 `validate_* -> validate_profile` 순수 함수 계층으로 두면, 로드 시점 강제/선택 검증 정책을 유연하게 바꾸면서 동일 검증 규칙을 재사용할 수 있다.
- 상태머신 M1 로직을 M2 프로파일로 승격할 때는 `lifecycle`에 프로파일 전이 검증 단일 진입점(`ensure_profile_transition`)을 두고 도메인 mutator(approve/finalize/revise)에서 공통 호출하면 하드코딩 제거와 에러 메시지 일관성을 동시에 확보할 수 있다.
- 상태 Enum 값(`draft`)과 프로파일 전이 토큰(`DRAFT`) 표현이 다를 수 있으므로, lifecycle 검증 진입점에서 공통 canonicalization(upper-case 정규화)을 적용하면 레이어 간 전이 검증 로직을 재사용하기 쉽다.
- 정적 Enum을 프로파일 기반 레지스트리로 치환할 때는 `profile load(lru_cache) -> normalize/duplicate guard -> ensure()` 경로를 단일화하고, `dataclass.__post_init__`에서 `ensure()`를 공통 호출하면 기본 규칙/커스텀 규칙 모두에서 미정의 타입을 일관되게 차단할 수 있다.
- 독립 레이어 스택 선언은 `전용 TOML(00-layer-stack) -> cached loader -> validate_layer_stack(순환/참조) + order 방향 검증` 조합으로 분리하면 기존 대형 프로파일과 독립적으로 M1 구조 계약을 안정 검증할 수 있다.
- 거버넌스 통합 validator에서는 상태전이 토큰(`DRAFT`)과 상태 요소명(`NeedStatusDraft`)이 다를 수 있으므로, `validate_state_transitions`에서 상태형 요소명의 `Status/State` suffix alias를 canonical token으로 추출하면 레이어별 네이밍 차이를 흡수하면서 동일 검증 규칙을 재사용할 수 있다.
- 도메인 대칭 레이어 스택은 `기존 flow skeleton(정의/런타임/피드백) 유지 + 레이어 이름/책임/관점만 도메인 치환 + 전용 layer_stack.py 재사용`으로 구성하면, 새 도메인 온보딩 시 validator/테스트 템플릿을 그대로 재활용할 수 있다.
- 동일 커널 M2에서 복수 도메인 레이어 스택 공존을 증명할 때는 `도메인별 독립 layer_stack 패키지 + 공통 validate_profile/validate_layer_stack` 조합을 병렬 검증하면, 레이어 수/의존 그래프가 달라도 M2 적합성을 일관되게 확인할 수 있다.
- 도메인별 상태머신 변형(예: REVIEW 단계 추가) 검증은 `전이 edge-set 비교 + 각 프로파일 validate_profile 동시 통과 확인`으로 구성하면, 규칙 차별성과 동일 M2 적합성을 한 번에 증명할 수 있다.
- 상태토큰에 underscore가 포함된 전이(`IN_PROGRESS`)를 쓸 때는 상태 alias 추출(`Status/State` suffix)만으로는 누락될 수 있으므로, 해당 토큰을 프로파일 elements에 동일 문자열로 선언하면 validator를 안정적으로 통과시킬 수 있다.
- 중간 계층 강제 아키텍처 규칙(예: `Service -> Repository -> DataModel`)은 `허용 경로 allow rules`와 `직접 경로 deny rules`를 함께 선언하고 테스트에서도 allow/deny pair를 같이 검증하면, 우회 접근 금지를 명확하게 보장할 수 있다.
- 파이프라인 프로파일에서 실행 순서와 통제 포인트를 함께 표현할 때는 `next`를 단계 체인(Build/Test/Stage/Deploy)에만 할당하고, 승인/복구는 `constrains`/`triggers`로 분리하면 규칙 의도와 테스트 검증 포인트가 명확해진다.
- 도메인 Projection 프로파일 차별성 검증은 `artifact_types 이름집합 disjoint 비교 + 신규 도메인 프로파일 validate_profile 통과` 조합으로 구성하면, 기존 도메인 제약에 영향 없이 동일 M2 메타모델 확장을 안정적으로 증명할 수 있다.
- 프로파일 기반 상태 검증이 필요한 Store는 `profile_id + lineage_id`를 전이 검증 키로 고정하고 `store()` 직전에 `latest(lineage) -> ensure_profile_transition`를 호출하면, InMemory/SQLite 양쪽 구현에서 동일 전이 규칙을 일관되게 강제할 수 있다.
- S4 Analyzer를 도메인 확장할 때는 `profile elements(카테고리/alias) + state_transitions(depth/terminal/success)`를 먼저 컴파일해 차원을 만들고, Store snapshot 집계를 그 차원에 투영하면 지표(throughput/success/effectiveness) 하드코딩을 제거하면서도 리포트 포맷을 유지할 수 있다.

---

## 2026-02-20 - US-001
- What was implemented
  - `ProfileStateTransition` frozen dataclass를 추가하고, `KernelProfile`에 `state_transitions` 필드를 기본값 `()`로 확장.
  - `ProfileBuilder`에 `add_state_transition(from_state, to_state, guard_condition, description)` 메서드와 내부 누적 저장소를 추가.
  - TOML loader가 `[[state_transitions]]` 섹션을 파싱해 builder로 전달하도록 확장(필수 필드 검증 포함).
  - serializer/composer 경로도 `state_transitions`를 보존하도록 갱신해 데이터 유실 방지.
  - 테스트 추가: TOML 상태전이 로드 검증, builder 추가 API 검증, serializer/composer/state default 검증.
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-profile/src/ea_profile/types.py`
  - `packages/ea-profile/src/ea_profile/builder.py`
  - `packages/ea-profile/src/ea_profile/loader.py`
  - `packages/ea-profile/src/ea_profile/serializer.py`
  - `packages/ea-profile/src/ea_profile/composer.py`
  - `packages/ea-profile/tests/test_loader.py`
  - `packages/ea-profile/tests/test_builder.py`
  - `packages/ea-profile/tests/test_types.py`
  - `packages/ea-profile/tests/test_serializer.py`
  - `packages/ea-profile/tests/test_composer.py`
- **Learnings:**
  - Patterns discovered
    - `KernelProfile` 모델 확장은 builder/loader만 수정하면 불충분하고 serializer/composer 전달 경로까지 동시에 맞춰야 회귀를 막을 수 있다.
  - Gotchas encountered
    - `uv run`으로 lint/typecheck 실행 시 캐시/환경 이슈가 발생해, 품질 점검은 `.venv/bin/ruff`, `.venv/bin/mypy`로 직접 실행해 검증했다.
---

## 2026-02-20 - US-002
- What was implemented
  - `ProfileArtifactType` frozen dataclass를 추가하고, `KernelProfile`에 `artifact_types` 필드를 기본값 `()`로 확장.
  - `ProfileBuilder`에 내부 누적 저장소와 `add_artifact_type(name, tier, description, kernel_element_pattern)` 메서드를 추가.
  - TOML loader가 `[[artifact_types]]` 섹션을 파싱해 builder로 전달하도록 확장(필수 필드 `name`, `tier` 검증 포함).
  - serializer/composer 경로도 `artifact_types`를 보존하도록 갱신해 dict/json round-trip 및 compose 경로 데이터 유실 방지.
  - 테스트 추가: TOML artifact type 로드 검증, builder API 검증, serializer/composer 보존 검증, 기본값 검증.
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-profile/src/ea_profile/types.py`
  - `packages/ea-profile/src/ea_profile/builder.py`
  - `packages/ea-profile/src/ea_profile/loader.py`
  - `packages/ea-profile/src/ea_profile/serializer.py`
  - `packages/ea-profile/src/ea_profile/composer.py`
  - `packages/ea-profile/tests/test_loader.py`
  - `packages/ea-profile/tests/test_builder.py`
  - `packages/ea-profile/tests/test_types.py`
  - `packages/ea-profile/tests/test_serializer.py`
  - `packages/ea-profile/tests/test_composer.py`
- **Learnings:**
  - Patterns discovered
    - Projection artifact type 같은 선언형 tuple 확장도 기존 패턴(`types -> builder -> loader -> serializer -> composer`)을 그대로 적용해야 round-trip/compose 일관성이 유지된다.
  - Gotchas encountered
    - 루트 워크스페이스에서 `uv run ruff/mypy`는 샌드박스에서 `~/.cache/uv` 접근 오류가 날 수 있어 `.venv/bin/ruff`, `.venv/bin/mypy`로 대체 검증이 안정적이었다.
---

## 2026-02-20 - US-003
- What was implemented
  - `LayerDefinition`, `LayerStack` frozen dataclass를 `ea_profile.types`에 추가하고 `KernelProfile`에 `layer_stack` 필드를 확장했다.
  - `ProfileBuilder`에 `set_layer_stack(...)`, `add_layer_definition(...)`를 추가해 레이어 스택 메타데이터를 선언적으로 누적할 수 있게 했고, build/validate 경로에 연동했다.
  - TOML loader를 확장해 `[layer_stack]`와 `[[layer_stack.layers]]`를 파싱하고 builder로 전달하도록 구현했다.
  - serializer/composer 경로를 갱신해 dict/json round-trip 및 extend/subset compose 경로에서도 `layer_stack` 데이터 유실이 없도록 했다.
  - 테스트 추가/확장: 5계층 TOML 로드, 3계층 TOML 로드, builder/serializer/composer/types 경로의 layer stack 보존 검증.
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-profile/src/ea_profile/types.py`
  - `packages/ea-profile/src/ea_profile/builder.py`
  - `packages/ea-profile/src/ea_profile/loader.py`
  - `packages/ea-profile/src/ea_profile/serializer.py`
  - `packages/ea-profile/src/ea_profile/composer.py`
  - `packages/ea-profile/tests/test_types.py`
  - `packages/ea-profile/tests/test_builder.py`
  - `packages/ea-profile/tests/test_loader.py`
  - `packages/ea-profile/tests/test_serializer.py`
  - `packages/ea-profile/tests/test_composer.py`
- **Learnings:**
  - Patterns discovered
    - 계층 구조 같은 중첩 선언형 메타데이터는 단일 tuple 필드보다 `set(stack-level) + add(entry-level)` builder API로 분리하면 loader 파싱/검증 로직이 단순해지고 재사용성이 높다.
  - Gotchas encountered
    - `uv run ruff/mypy`는 샌드박스에서 `~/.cache/uv` 권한 오류가 발생할 수 있어 `.venv/bin/ruff`, `.venv/bin/mypy`로 대체 검증이 필요했다.
---

## 2026-02-20 - US-004
- What was implemented
  - `ProfileProcessUnit` frozen dataclass를 추가하고, `KernelProfile`에 `process_units` 필드를 기본값 `()`로 확장했다.
  - `ProfileBuilder`에 `add_process_unit(name, phase, description, input_artifacts, output_artifacts)` 메서드와 내부 누적 저장소를 추가했다.
  - TOML loader를 확장해 `[[process_units]]` 섹션을 파싱하고 builder로 전달하도록 구현했다(필수 필드 `name`, `phase` 검증 포함).
  - serializer/composer 경로를 갱신해 dict/json round-trip 및 extend/subset compose에서도 `process_units` 데이터 유실이 없도록 반영했다.
  - 테스트 추가/확장: loader TOML process_units 로드 검증, builder/types/serializer/composer 경로의 process_units 보존 검증.
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-profile/src/ea_profile/types.py`
  - `packages/ea-profile/src/ea_profile/builder.py`
  - `packages/ea-profile/src/ea_profile/loader.py`
  - `packages/ea-profile/src/ea_profile/serializer.py`
  - `packages/ea-profile/src/ea_profile/composer.py`
  - `packages/ea-profile/tests/test_types.py`
  - `packages/ea-profile/tests/test_builder.py`
  - `packages/ea-profile/tests/test_loader.py`
  - `packages/ea-profile/tests/test_serializer.py`
  - `packages/ea-profile/tests/test_composer.py`
- **Learnings:**
  - Patterns discovered
    - 프로세스 유닛처럼 입력/출력 아티팩트 배열을 갖는 선언형 스키마는 loader에서 `str/list` 정규화를 먼저 수행하면 builder/dataclass 타입을 단순 tuple로 유지할 수 있다.
  - Gotchas encountered
    - 패키지 전체 `ruff`는 기존 테스트 코드의 선행 lint 이슈로 실패할 수 있어, 스토리 변경 파일 단위 검증과 전체 `pytest` 통과를 분리해 확인하는 것이 안정적이었다.
---

## 2026-02-20 - US-005
- What was implemented
  - `ea_profile/profile_validator.py` 모듈을 추가하고 `validate_state_transitions`, `validate_artifact_types`, `validate_layer_stack`, `validate_process_units`, `validate_profile`를 구현했다.
  - `ProfileValidationResult` dataclass를 추가해 4개 검증 결과를 통합 반환하도록 구성했다.
  - 상태전이 검증에서 `from_state`/`to_state`가 프로파일 `elements`에 존재하는지 검사하고, wildcard `*`는 허용했다.
  - artifact type 검증에서 `kernel_element_pattern`이 프로파일 elements(이름/커널타입, @Category/#Layer/글롭 패턴 포함) 중 최소 1개와 매칭되는지 검사했다.
  - layer stack 검증에서 `order` 중복, unknown dependency, depends_on 순환(DFS)을 검출하도록 구현했다.
  - process unit 검증에서 `input_artifacts`/`output_artifacts`가 `artifact_types.name`에 존재하는지 검사했다.
  - 테스트를 추가해 유효 프로파일 통과, 레이어 순환 의존 실패, 없는 상태 참조 실패 및 artifact/process unit 참조 실패 케이스를 검증했다.
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-profile/src/ea_profile/profile_validator.py`
  - `packages/ea-profile/tests/test_profile_validator.py`
- **Learnings:**
  - Patterns discovered
    - 정적 validator를 pure function으로 분리하고 통합 리포트 타입(`ProfileValidationResult`)을 두면 호출자가 실패 정책(즉시 예외/누적 리포트)을 선택할 수 있어 이후 도메인 확장에 유리하다.
  - Gotchas encountered
    - Mypy strict 환경에서는 새 테스트 함수에도 `-> None` 반환 타입 주석이 필요해, 테스트 파일도 구현 코드와 동일한 타입 엄격도를 맞춰야 한다.
---

## 2026-02-20 - US-006
- What was implemented
  - `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/20-decision.toml`에 `[[state_transitions]]` 섹션을 추가해 Decision 상태전이를 선언형으로 정의했다(`PROPOSED→ACCEPTED`, `PROPOSED→REJECTED`, `*→DEPRECATED` 포함, lifecycle 호환 전이도 함께 선언).
  - `ea_decision/lifecycle.py`의 하드코딩 전이 맵을 제거하고, decision 프로파일(`layer_path("decision")`)에서 상태전이를 로드/캐시해 검증하는 `ensure_profile_transition` 기반 로직으로 교체했다.
  - `DesignDecision.approve()`, `DesignReport.finalize_execution()`, `Topic.finalize_plan()`, `Topic.revise_report()`가 모두 프로파일 전이 검증을 거치도록 변경했다.
  - 테스트를 보강해 프로파일 기반 전이(와일드카드 deprecate), 금지 전이 에러, unknown 상태 에러를 검증했다.
  - 품질 검증: `uv run pytest packages/ -x -q` 전체 통과(3101 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/20-decision.toml`
  - `packages/ea-decision/src/ea_decision/lifecycle.py`
  - `packages/ea-decision/src/ea_decision/topic.py`
  - `packages/ea-decision/tests/test_lifecycle.py`
  - `packages/ea-decision/tests/test_topic.py`
- **Learnings:**
  - Patterns discovered
    - 상태전이 검증을 lifecycle 모듈의 단일 함수로 중앙화하면, aggregate 내부 여러 메서드가 동일 규칙/동일 에러 포맷을 공유해 회귀 테스트 작성이 쉬워진다.
  - Gotchas encountered
    - 전이 상태 토큰은 Enum 값(`accepted`)과 프로파일 토큰(`ACCEPTED`)의 대소문자/표현이 다를 수 있어, 비교 전에 공통 정규화(upper-case canonicalization)가 필요했다.
---

## 2026-02-20 - US-007
- What was implemented
  - `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/30-needs.toml`에 `[[state_transitions]]` 섹션을 추가해 Needs 상태전이(`DRAFT→EXPRESSED→ACKNOWLEDGED→ADDRESSED`, 그리고 각 단계의 `→WITHDRAWN`)를 선언형으로 정의했다.
  - `ea_needs/lifecycle.py`를 추가해 needs 프로파일(`layer_path("needs")`)에서 상태전이를 로드/캐시하고 검증하는 `ensure_profile_transition`/`allowed_profile_targets` 단일 진입점을 구현했다.
  - `ea_needs/catalog.py`의 하드코딩 `_VALID_TRANSITIONS`를 제거하고 `Need.transition_to()`가 프로파일 기반 검증을 사용하도록 교체해 기존 에러 메시지 포맷(`Cannot transition ...`)을 유지했다.
  - `ea-needs/tests/test_lifecycle.py`를 추가해 프로파일 기반 허용/금지 전이 동작을 검증했다.
  - 품질 검증: `uv run pytest packages/ea-needs/tests/test_catalog.py packages/ea-needs/tests/test_lifecycle.py -q`, `uv run pytest packages/ -x -q` 통과(3104 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/30-needs.toml`
  - `packages/ea-needs/src/ea_needs/lifecycle.py`
  - `packages/ea-needs/src/ea_needs/catalog.py`
  - `packages/ea-needs/tests/test_lifecycle.py`
- **Learnings:**
  - Patterns discovered
    - Needs 상태머신도 Decision과 동일하게 `profile -> lifecycle(single entry) -> domain mutator` 구조를 쓰면 M1 하드코딩 제거와 규칙 중앙화가 동시에 가능하다.
  - Gotchas encountered
    - `catalog.py`는 기존에 strict mypy 이슈가 누적된 파일이라, 신규 변경 영향 검증은 새 모듈/테스트 단위 mypy + 전체 pytest 통과로 분리해 확인하는 것이 현실적이었다.
---

## 2026-02-20 - US-008
- What was implemented
  - `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/70-projection.toml`에 `[[artifact_types]]` 선언을 추가해 `api_endpoint`, `page`, `tool`, `identifier`, `contract`, `event`, `data_schema`, `configuration`을 프로파일 메타데이터로 정의했다.
  - `packages/ea-projection/src/ea_projection/artifacts.py`의 `ArtifactType` 정적 `StrEnum`을 프로파일 로드 기반 동적 레지스트리로 교체했다(`lru_cache` 로드, 중복/빈 이름 가드, enum-like 메타클래스 facade).
  - `SurfaceArtifact`/`ArtifactExtractionRule`의 `__post_init__`에서 `ArtifactType.ensure()`를 공통 호출하도록 해, 프로파일에 없는 artifact type 사용 시 즉시 `ValueError`가 발생하도록 강제했다.
  - 기본 추출 규칙(`DEFAULT_EXTRACTION_RULES`)은 프로파일 registry를 통해 artifact type을 resolve하도록 갱신해 기존 추출 동작을 유지했다.
  - `packages/ea-projection/tests/test_artifacts.py`를 확장해 레지스트리가 projection 프로파일 선언과 동기화되는지, 미정의 artifact type 사용 시 에러가 나는지 검증했다.
  - 품질 검증: `.venv/bin/ruff check`, `.venv/bin/mypy`, `uv run pytest packages/ea-projection/tests/test_artifacts.py -q`, `uv run pytest packages/ -x -q` (3106 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/70-projection.toml`
  - `packages/ea-projection/src/ea_projection/artifacts.py`
  - `packages/ea-projection/tests/test_artifacts.py`
- **Learnings:**
  - Patterns discovered
    - 프로파일 기반 레지스트리 치환 시 기존 enum 사용감(`ArtifactType.PAGE`, iteration)을 메타클래스 facade로 보존하면 호출부 수정을 최소화하면서 선언적 스키마 전환이 가능하다.
  - Gotchas encountered
    - 샌드박스에서 `uv run ruff/mypy`는 `~/.cache/uv` 접근 오류가 발생할 수 있어 `.venv/bin/ruff`, `.venv/bin/mypy`로 대체 실행이 필요했다.
---

## 2026-02-20 - US-009
- What was implemented
  - `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/00-layer-stack.toml`을 추가해 6개 레이어(`infra`, `decision`, `needs`, `kernel`, `flow`, `governance`)의 `name/order/depends_on/responsibility/model_perspective`를 선언했다.
  - 같은 TOML에 `definition_flow`, `runtime_flow`, `feedback_flow`를 명시적으로 선언해 거버넌스 도메인 레이어 구조의 M1 설계 결정을 문서화했다.
  - `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/layer_stack.py` 모듈을 추가해 layer stack TOML 로드(`lru_cache`), 메타데이터 접근, 의존 방향 검증, 순환 포함 정적 검증(`validate_layer_stack`)을 제공하도록 구현했다.
  - 테스트를 추가해 레이어 정의 로드, 의존 방향 검증 통과, 순환 없음/validator 통과를 확인했다.
  - 품질 검증: `.venv/bin/ruff check`, `.venv/bin/mypy`, `uv run pytest packages/ea-kernel/tests/test_ea_sys_layer_stack_profile.py -q`, `uv run pytest packages/ -x -q` (3109 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/00-layer-stack.toml`
  - `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/layer_stack.py`
  - `packages/ea-kernel/tests/test_ea_sys_layer_stack_profile.py`
- **Learnings:**
  - Patterns discovered
    - 레이어 스택은 커널 도메인 로직과 분리된 독립 프로파일로 두고 전용 로더 모듈에서 재사용하면, ProfileGraph/API가 필요할 때 동일 메타를 안정적으로 참조할 수 있다.
  - Gotchas encountered
    - `ea_kernel.profile_loader`는 `ea_profile.loader` 재-export라 mypy에서 속성 추론이 실패할 수 있어, 새 모듈에서는 정적 타입 안정성을 위해 `ea_profile.loader.load_profile`를 직접 import하는 편이 안전했다.
---

## 2026-02-20 - US-010
- What was implemented
  - `ea_profile.profile_validator.validate_state_transitions`를 확장해 상태 토큰 canonicalization과 상태형 요소명 alias(`NeedStatusDraft` -> `DRAFT`)를 함께 인식하도록 구현해, Needs/Decision 전이 네이밍 차이를 통합 검증에서 흡수했다.
  - `packages/ea-kernel/tests/test_governance_profile_integration_gate.py`를 추가해 US-010 수용조건(Decision/Needs 전이 프로파일 유래, Projection ArtifactType 프로파일 유래, LayerStack TOML 로드, 전체 거버넌스 도메인 프로파일 validator 통과)을 단일 통합 게이트로 검증했다.
  - `packages/ea-profile/tests/test_profile_validator.py`에 상태 alias 인식 회귀 테스트를 추가했다.
  - 품질 검증: `.venv/bin/ruff check`, `.venv/bin/mypy`, `uv run pytest packages/ea-profile/tests/test_profile_validator.py packages/ea-kernel/tests/test_governance_profile_integration_gate.py -q`, `uv run pytest packages/ -x -q` (3115 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-profile/src/ea_profile/profile_validator.py`
  - `packages/ea-profile/tests/test_profile_validator.py`
  - `packages/ea-kernel/tests/test_governance_profile_integration_gate.py`
- **Learnings:**
  - Patterns discovered
    - 전이 토큰 검증은 단순 exact-name 매칭보다 `canonical token + state alias`를 함께 지원해야 다중 레이어 프로파일의 표현 차이(예: `NeedStatus*` vs `DRAFT`)를 통합 게이트에서 안정적으로 수용할 수 있다.
  - Gotchas encountered
    - 개별 레이어 기준 artifact pattern 검증은 오탐이 날 수 있어, 통합 게이트에서는 거버넌스 도메인 전체 프로파일을 합성한 뒤 validator를 적용해야 실제 운영 문맥과 일치한다.
---

## 2026-02-20 - US-011
- What was implemented
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/00-layer-stack.toml`를 추가해 SDLC 대칭 레이어 6개(`DevInfra`, `ArchDecision`, `Requirements`, `DomainModel`, `Pipeline`, `DevGovernance`)의 `order/depends_on/responsibility/model_perspective`를 선언했다.
  - 같은 TOML에 거버넌스 도메인과 동일한 패턴의 `definition_flow/runtime_flow/feedback_flow`를 SDLC 레이어명으로 매핑해 명시했다.
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`, `packages/ea-kernel/src/ea_kernel/profiles/sdlc/layer_stack.py`를 추가해 SDLC 레이어 스택 전용 로드/검증 진입점(`load_layer_stack_profile`, `validate_loaded_layer_stack`)을 구성했다.
  - `packages/ea-kernel/tests/test_sdlc_layer_stack_profile.py`를 추가해 레이어 순서, 의존 방향, 순환/validator 통과를 자동 검증했다.
  - 품질 검증: `.venv/bin/ruff check packages/ea-kernel/src/ea_kernel/profiles/sdlc packages/ea-kernel/tests/test_sdlc_layer_stack_profile.py`, `.venv/bin/mypy packages/ea-kernel/src/ea_kernel/profiles/sdlc/layer_stack.py packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py packages/ea-kernel/tests/test_sdlc_layer_stack_profile.py`, `uv run pytest packages/ea-kernel/tests/test_sdlc_layer_stack_profile.py -q`, `uv run pytest packages/ -x -q` (3118 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/00-layer-stack.toml`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/layer_stack.py`
  - `packages/ea-kernel/tests/test_sdlc_layer_stack_profile.py`
- **Learnings:**
  - Patterns discovered
    - 레이어 스택 대칭 매핑은 기존 도메인의 flow/의존성 골격을 유지한 채 레이어명과 책임만 치환하면 validator/테스트 재사용성이 높아진다.
  - Gotchas encountered
    - 대칭 매핑에서도 `DevGovernance` 같은 관리 레이어를 포함하지 않으면 runtime/feedback flow 패턴이 기존 거버넌스 도메인과 어긋나므로, 5 core + 1 governance 구성을 유지해야 패턴 일치성이 보장된다.
---

## 2026-02-20 - US-012
- What was implemented
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc_native/00-layer-stack.toml`을 추가해 SDLC 고유 5계층(`Planning`, `Implementation`, `Verification`, `Deployment`, `Monitoring`)의 `order/depends_on/responsibility/model_perspective`를 선언했다.
  - 동일 TOML에 대칭 매핑과 다른 `definition_flow/runtime_flow/feedback_flow`를 정의해 SDLC native 도메인 구조가 별도 의존 그래프를 갖도록 구성했다.
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc_native/__init__.py`, `packages/ea-kernel/src/ea_kernel/profiles/sdlc_native/layer_stack.py`를 추가해 native 레이어 스택 전용 로드/검증 진입점(`load_layer_stack_profile`, `validate_loaded_layer_stack`)을 구성했다.
  - `packages/ea-kernel/tests/test_sdlc_native_layer_stack_profile.py`를 추가해 native 레이어 로드/의존 방향 검증, 거버넌스 도메인 대비 레이어 수/의존 그래프 차이, 그리고 대칭 SDLC + native SDLC가 동일 커널 M2 검증기에서 모두 유효함을 검증했다.
  - 품질 검증: `.venv/bin/ruff check`, `.venv/bin/mypy`, `uv run pytest packages/ea-kernel/tests/test_sdlc_native_layer_stack_profile.py -q`, `uv run pytest packages/ -x -q`.
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc_native/00-layer-stack.toml`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc_native/__init__.py`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc_native/layer_stack.py`
  - `packages/ea-kernel/tests/test_sdlc_native_layer_stack_profile.py`
- **Learnings:**
  - Patterns discovered
    - 동일 M2에서 다중 도메인 레이어 스택(대칭/고유)을 공존시키려면 각 도메인을 독립 `layer_stack` 패키지로 분리하고, 공통 validator를 재사용해 적합성만 교차 검증하는 방식이 확장성과 회귀 안정성 모두에 유리하다.
  - Gotchas encountered
    - `거버넌스 대비 다른 의존 방향`은 상위→하위 역방향이 아니라, `order 제약(낮은 순서 의존)`을 지키면서도 그래프 형태(팬인/팬아웃, 관리 레이어 유무)를 명확히 다르게 설계해야 validator를 통과하면서 차별성을 확보할 수 있다.
---

## 2026-02-20 - US-013
- What was implemented
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/20-arch-decision.toml`을 추가해 SDLC 아키텍처 의사결정 프로파일을 정의했다.
  - SDLC 의사결정 요소 `ArchDecisionRecord`(ADR), `TechRadarEntry`, `DesignReviewItem`을 포함하고, 상태형 요소(`ArchDecisionStatus*`)를 함께 선언해 전이 토큰을 M2 validator에서 해석 가능하게 구성했다.
  - 상태전이를 `PROPOSED -> REVIEW -> ACCEPTED -> SUPERSEDED -> DEPRECATED` 체인으로 선언했다.
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`에 `arch-decision` 프로파일 매핑을 추가했다.
  - `packages/ea-kernel/tests/test_sdlc_arch_decision_profile.py`를 추가해
    - 필수 SDLC decision 요소/전이 선언 확인
    - 거버넌스 decision 대비 REVIEW 단계 추가 차이 검증
    - 두 프로파일이 동일 `validate_profile`(M2)에서 모두 통과함을 검증
    을 자동화했다.
  - 품질 검증: `.venv/bin/ruff check`, `.venv/bin/mypy`, `uv run pytest packages/ea-kernel/tests/test_sdlc_arch_decision_profile.py -q`, `uv run pytest packages/ -x -q` (3125 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/20-arch-decision.toml`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`
  - `packages/ea-kernel/tests/test_sdlc_arch_decision_profile.py`
- **Learnings:**
  - Patterns discovered
    - 상태전이 차별 검증은 프로파일 간 전이 edge-set을 직접 비교하고, 동시에 동일 `validate_profile` 통과를 확인하면 도메인별 특화와 공통 M2 적합성을 함께 보장할 수 있다.
  - Gotchas encountered
    - 전이 토큰을 `PROPOSED/REVIEW/...`처럼 별도 표기로 쓸 때는 이를 해석할 상태형 요소(`*StatusProposed` 등)를 프로파일 요소에 함께 선언해야 상태전이 validator에서 unknown 상태 오류를 피할 수 있다.
---

## 2026-02-20 - US-014
- What was implemented
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/30-requirements.toml`을 추가해 SDLC Requirements 프로파일을 정의했다.
  - 요구 요소 `UserStory`, `AcceptanceCriteria`, `Epic`, `TechnicalDebt`, `BugReport`를 포함했다.
  - 상태전이를 `BACKLOG -> GROOMED -> SPRINT -> IN_PROGRESS -> REVIEW -> DONE -> CLOSED` 체인으로 선언했다.
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`에 `requirements` 프로파일 매핑을 추가했다.
  - `packages/ea-kernel/tests/test_sdlc_requirements_profile.py`를 추가해
    - SDLC requirements 필수 요소/전이 검증
    - 거버넌스 Needs(5상태) 대비 SDLC requirements(7상태) 차이 검증
    - 두 프로파일이 동일 `validate_profile`(M2)에서 모두 통과함을 검증
    을 자동화했다.
  - 품질 검증: `.venv/bin/ruff check`, `.venv/bin/mypy`, `uv run pytest packages/ea-kernel/tests/test_sdlc_requirements_profile.py -q`, `uv run pytest packages/ -x -q` (3128 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/30-requirements.toml`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`
  - `packages/ea-kernel/tests/test_sdlc_requirements_profile.py`
- **Learnings:**
  - Patterns discovered
    - SDLC/거버넌스처럼 도메인이 달라도 상태머신 차별성은 `상태 수 + edge-set 비교`, M2 적합성은 `validate_profile 동시 통과`로 분리 검증하면 회귀 포인트가 명확해진다.
  - Gotchas encountered
    - `IN_PROGRESS` 같은 underscore 토큰은 상태명 alias 추출이 단어 마지막 토큰만 잡는 케이스가 있어, transition token과 동일한 상태 element를 명시해 validator unknown-state를 방지해야 했다.
---

## 2026-02-20 - US-015
- What was implemented
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/40-domain-model.toml`을 추가해 SDLC DomainModel 프로파일을 정의했다.
  - SDLC 도메인 핵심 요소 `Module`, `Interface`, `Endpoint`, `DataModel`, `Repository`, `Service`를 선언했다.
  - 요구 관계 `implements`, `calls`, `stores`, `exposes`, `depends_on`를 선언했다.
  - 아키텍처 규칙으로 `Service -> Repository -> DataModel` 경로를 allow하고, `Service -> DataModel` 직접 접근(`depends_on/calls/stores`)을 explicit deny로 정의했다.
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`에 `domain-model` 프로파일 매핑을 추가했다.
  - `packages/ea-kernel/tests/test_sdlc_domain_model_profile.py`를 추가해 필수 요소/관계 선언, repository 매개 접근 규칙, `validate_profile + check_profile_quality` 통과를 검증했다.
  - 품질 검증: `.venv/bin/ruff check`, `.venv/bin/mypy`, `uv run pytest packages/ea-kernel/tests/test_sdlc_domain_model_profile.py -q`, `uv run pytest packages/ -x -q` (3131 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/40-domain-model.toml`
  - `packages/ea-kernel/tests/test_sdlc_domain_model_profile.py`
- **Learnings:**
  - Patterns discovered
    - 도메인 모델 접근 제약은 단일 deny 규칙보다 `허용 경로 + 우회 deny`를 함께 선언하고 테스트로 쌍 검증할 때 의도(중간 계층 강제)가 더 명확히 고정된다.
  - Gotchas encountered
    - `ea_kernel.profile_quality_gate` 재-export는 mypy에서 `attr-defined`가 날 수 있어, 테스트에서는 `ea_profile.quality_gate`를 직접 import하는 편이 타입 안정적이었다.
---

## 2026-02-20 - US-016
- What was implemented
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/50-pipeline.toml`을 추가해 SDLC Pipeline(Flow) 프로파일을 정의했다.
  - SDLC 파이프라인 핵심 요소 `BuildStep`, `TestSuite`, `DeployTarget`, `RollbackProcedure`, `ApprovalGate`를 선언하고 `StageStep`을 추가해 단계 체인 표현을 명시했다.
  - 상태전이를 `QUEUED -> BUILDING -> TESTING -> STAGING -> PRODUCTION -> ROLLED_BACK` 체인으로 선언했다.
  - `next` 규칙을 `BuildStep -> TestSuite -> StageStep -> DeployTarget`으로 선언해 Build→Test→Stage→Deploy 순서를 고정했다.
  - `ApprovalGate -> DeployTarget(constrains)`, `DeployTarget -> RollbackProcedure(triggers)` 규칙을 추가해 승인 게이트/롤백 절차를 분리 표현했다.
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`에 `pipeline` 프로파일 매핑을 추가했다.
  - `packages/ea-kernel/tests/test_sdlc_pipeline_profile.py`를 추가해 필수 요소/상태전이/next 규칙/`validate_profile` 통과를 검증했다.
  - 품질 검증: `.venv/bin/ruff check ...`, `.venv/bin/mypy ...`, `uv run pytest packages/ea-kernel/tests/test_sdlc_pipeline_profile.py -q`, `uv run pytest packages/ -x -q` (3134 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/50-pipeline.toml`
  - `packages/ea-kernel/tests/test_sdlc_pipeline_profile.py`
- **Learnings:**
  - Patterns discovered
    - 파이프라인 도메인에서는 순차 실행(`next`)과 통제/복구(`constrains`/`triggers`)를 분리 선언하면 상태전이/규칙/요소 테스트를 각각 안정적으로 고정할 수 있다.
  - Gotchas encountered
    - 수용조건의 Stage 단계는 필수 요소 목록에 직접 포함되지 않아, `StageStep`을 별도 요소로 명시해 `Build→Test→Stage→Deploy` 체인 검증의 모호성을 제거했다.
---

## 2026-02-20 - US-017
- What was implemented
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/60-projection.toml`를 추가해 SDLC Projection 프로파일을 정의했다.
  - `[[artifact_types]]`에 `repository`, `pull_request`, `ci_pipeline`, `deployment`, `api_doc`, `test_report`, `monitoring_dashboard`를 선언했다.
  - tier 매핑을 `repository -> data`, `ci_pipeline -> function`, `monitoring_dashboard -> ui`를 포함한 SDLC 관점으로 정의하고, 각 `kernel_element_pattern`이 매칭될 projection 요소를 함께 선언했다.
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`에 `projection` 프로파일 매핑을 추가했다.
  - `packages/ea-kernel/tests/test_sdlc_projection_profile.py`를 추가해 필수 artifact type/tier 매핑, 거버넌스 projection 대비 disjoint artifact set, SDLC projection `validate_profile` 통과를 검증했다.
  - 품질 검증: `.venv/bin/ruff check`, `.venv/bin/mypy`, `uv run pytest packages/ea-kernel/tests/test_sdlc_projection_profile.py -q`, `uv run pytest packages/ -x -q` (3137 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/__init__.py`
  - `packages/ea-kernel/src/ea_kernel/profiles/sdlc/60-projection.toml`
  - `packages/ea-kernel/tests/test_sdlc_projection_profile.py`
- **Learnings:**
  - Patterns discovered
    - Projection 도메인 확장 검증은 artifact set 차별성(disjoint)과 신규 도메인 validator 통과를 분리 검증하면, 기존 프로파일 제약과 독립적으로 M2 적합성을 안정적으로 증명할 수 있다.
  - Gotchas encountered
    - 기존 거버넌스 `70-projection.toml`은 단일 프로파일 기준 `@Page`, `@Assessment` 패턴 검증에서 실패할 수 있어, 이번 스토리 테스트는 수용조건에 맞춰 SDLC validator 통과와 cross-domain artifact set 차별성에 초점을 맞췄다.
---

## 2026-02-20 - US-018
- What was implemented
  - `packages/sdlc-domain` 신규 워크스페이스 패키지를 생성하고 `ea-kernel`, `ea-profile` 의존을 연결했다.
  - `sdlc_store.py`에 `SDLCStore` ABC, `InMemorySDLCStore`, `SQLiteSDLCStore`를 구현해 S3 Recording 3-tier 패턴을 SDLC 도메인으로 인스턴스화했다.
  - 저장 시점에 SDLC 프로파일(`ea_kernel.profiles.sdlc.profile_path`)의 `[[state_transitions]]`를 로드/캐시하고, `profile_id + lineage_id`의 직전 스냅샷 상태와의 전이를 검증하도록 구현했다.
  - CRUD 기능(`store/get/query/count/delete`)과 query 필터/페이지네이션을 InMemory/SQLite 모두에 제공했다.
  - 테스트를 추가해 CRUD, 유효/무효 전이, unknown 상태 거부, 전이 정의가 없는 프로파일 거부를 검증했다.
  - 품질 검증: `.venv/bin/ruff check`, `.venv/bin/mypy`, `uv run pytest packages/sdlc-domain/tests/test_sdlc_store.py -q`, `uv run pytest packages/ -x -q` (3149 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `pyproject.toml`
  - `uv.lock`
  - `packages/sdlc-domain/README.md`
  - `packages/sdlc-domain/pyproject.toml`
  - `packages/sdlc-domain/src/sdlc_domain/__init__.py`
  - `packages/sdlc-domain/src/sdlc_domain/sdlc_store.py`
  - `packages/sdlc-domain/tests/test_sdlc_store.py`
- **Learnings:**
  - Patterns discovered
    - 상태전이 검증은 라이프사이클 객체 밖(Store 경계)에서도 프로파일 로드 + canonicalization + 직전 상태 조회 조합으로 동일하게 재사용할 수 있다.
  - Gotchas encountered
    - `ea_profile.loader.load_profile`는 `validate` 인자를 받지 않으므로, 검증 정책 분리는 호출자가 아닌 후속 validator/전이 검증 로직에서 처리해야 했다.
---

## 2026-02-20 - US-019
- What was implemented
  - `sdlc_analyzer.py`를 추가해 SDLC Store 기반 S4 분석 엔진(`SDLCAnalyzer`)과 리포트/지표 타입(`SDLCAnalysisReport`, `SDLCProfileMetric`, `SDLCProfileDimension`)을 구현했다.
  - 분석 차원은 SDLC 프로파일 `elements`/`state_transitions`를 런타임 로드해 동적으로 컴파일하도록 구성했다(요소 카테고리 분류, 상태 alias 정규화, terminal/success/depth 추론).
  - 리포트에 요구 지표를 반영했다: `requirements_throughput`, `pipeline_success_rate`, `adr_effectiveness`.
  - `__init__.py` export를 갱신해 analyzer 타입을 패키지 퍼블릭 API에 노출했다.
  - `test_sdlc_analyzer.py`를 추가해
    - 프로파일 요소 기반 차원 추출(하드코딩 배제)
    - SDLC 스냅샷 시나리오 기반 리포트 수치 검증
    - 빈 저장소 리포트 검증
    을 자동화했다.
  - 품질 검증: `.venv/bin/ruff check`, `.venv/bin/mypy`, `uv run pytest packages/sdlc-domain/tests/test_sdlc_store.py packages/sdlc-domain/tests/test_sdlc_analyzer.py -q`, `uv run pytest packages/ -x -q` (3152 passed).
- Files changed
  - `.ralph-tui/progress.md`
  - `packages/sdlc-domain/src/sdlc_domain/sdlc_analyzer.py`
  - `packages/sdlc-domain/src/sdlc_domain/__init__.py`
  - `packages/sdlc-domain/tests/test_sdlc_analyzer.py`
- **Learnings:**
  - Patterns discovered
    - Analyzer 차원은 프로파일에서 직접 계산한 상태 graph(depth/terminal/success)와 요소 분류(active/passive/behavior/governance)를 결합하면 도메인별 하드코딩 없이도 동일 분석 파이프라인을 재사용할 수 있다.
  - Gotchas encountered
    - SDLC `arch-decision`은 상태 요소명(`ArchDecisionStatus*`)과 전이 토큰(`PROPOSED/REVIEW/...`)이 달라, 분석기에서도 상태 alias canonicalization을 적용해야 전이 기반 지표가 정확히 계산된다.
---
