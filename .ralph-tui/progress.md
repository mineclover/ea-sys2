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
