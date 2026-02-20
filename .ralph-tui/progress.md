# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- KernelProfile에 새 tuple 필드를 추가할 때는 `types -> builder -> loader(TOML) -> serializer(dict/json) -> composer` 경로를 함께 갱신해야 값 손실 없이 round-trip/compose가 유지된다.
- 중첩 TOML 배열 테이블(`[[layer_stack.layers]]`)은 loader에서 `doc["layer_stack"]["layers"]`로 파싱되므로, builder에서 stack 메타(`set_*`)와 항목 누적(`add_*`)을 분리하면 확장 스키마를 안정적으로 수용할 수 있다.

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
