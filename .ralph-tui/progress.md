# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- KernelProfile에 새 tuple 필드를 추가할 때는 `types -> builder -> loader(TOML) -> serializer(dict/json) -> composer` 경로를 함께 갱신해야 값 손실 없이 round-trip/compose가 유지된다.

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
