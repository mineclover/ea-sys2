# Kernel Model Alignment Review (Ralph TUI, Legacy)

> Legacy note:
> This document is retained for historical traceability only.
> Canonical EA-SYS layer modeling/reference now lives under
> `packages/ea-kernel/examples/ea-sys` and related `ea-sys` docs.

검토 일자: 2026-02-13

## 1) 세분화 검토 범위

- 커널 모델:
  - `packages/ea-kernel/examples/ralph_tui_layers/40-kernel.toml`
- 구현 기준:
  - `reference/src/`
- 매칭 기준:
  - 커널 요소명이 실제 구현의 클래스/핵심 함수에 근거를 가지는지 확인

## 2) 1차 검토 (모델 최신화 전)

핵심 갭:
1. `CommandRouter` / `PluginRegistry`는 구현의 실제 심볼(`handleSubcommand`, `AgentRegistry`, `TrackerRegistry`)과 직접 매칭이 약했다.
2. `PromptTemplateEngine`, `TuiRuntime`는 개념적으로는 맞지만, 커널 모델에 근거 포인트가 느슨했다.
3. 최신 핵심 컴포넌트가 모델에 누락되어 있었다.
   - `ConfigManager` (`src/config/index.ts`)
   - `RateLimitDetector` (`src/engine/rate-limit-detector.ts`)
   - `StructuredLogger` (`src/logs/structured-logger.ts`)
   - `RemoteServer` (`src/remote/server.ts`)

## 3) 모델 최신화 적용

업데이트 파일:
- `packages/ea-kernel/examples/ralph_tui_layers/40-kernel.toml`

적용 내용:
1. 커널 요소를 구현 심볼 중심으로 재정의
   - `CliEntryPoint`, `AgentRegistry`, `TrackerRegistry`, `ConfigManager`,
     `RateLimitDetector`, `StructuredLogger`, `RemoteServer` 추가/정렬
2. 커널 내부 관계 규칙 확장
   - `contains`, `coordinates`, `depends_on`, `constrains` 규칙을 구체화
3. 커널 규칙 수 확장
   - 검증 기준 규칙: 30개 (기존 대비 대폭 보강)

## 4) 2차 매칭 재검토 (최신화 후)

자동 검토 스크립트:
- `packages/ea-kernel/src/ea_kernel/scripts/review_ralph_tui_kernel_alignment.py`

리포트:
- `packages/ea-kernel/docs/reference/kernel_ralph_tui_kernel_alignment.latest.json`

결과:
- 커버리지: `13/13 (100.0%)`
- missing 요소: `0`
- unmapped 요소: `0`

대표 근거:
- `ExecutionEngine` -> `reference/src/engine/index.ts:144`
- `ParallelExecutor` -> `reference/src/parallel/index.ts:57`
- `AgentRegistry` -> `reference/src/plugins/agents/registry.ts:58`
- `TrackerRegistry` -> `reference/src/plugins/trackers/registry.ts:58`
- `ConfigManager` -> `reference/src/config/index.ts:523`, `reference/src/config/index.ts:616`
- `RemoteServer` -> `reference/src/remote/server.ts:228`

## 5) 결론

커널 모델이 최신 구현 구조와 정합되도록 갱신되었고, 재매칭 자동 검토에서 100% 정합성을 확인했다.
이 상태를 커널 레퍼런스 기준으로 유지하고, 타 레이어 확장 시 동일한 매칭 검토 절차를 반복 적용한다.
