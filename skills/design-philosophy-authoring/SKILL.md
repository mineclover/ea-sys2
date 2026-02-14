---
name: design-philosophy-authoring
description: "패키지 설계 철학 문서(CLAUDE.md) 작성 스킬. 벤치마크 CLAUDE.md에서 섹션 메타모델을 추출하고, 대상 패키지 코드를 탐색하여, 메타모델에 적합한 CLAUDE.md를 생성·평가·반복한다. 새 패키지에 CLAUDE.md를 작성하거나, 기존 CLAUDE.md를 벤치마크 품질로 끌어올릴 때 사용한다."
---

# Design Philosophy Authoring

벤치마크 CLAUDE.md의 구조를 메타모델로 추출하고, 대상 패키지 코드 탐색 결과를 메타모델 슬롯에 채워 설계 철학 문서를 작성하는 5-Phase 워크플로우.

## Workflow

5단계 순차 실행. Phase 4~5는 반복 가능.

```
Phase 1: Benchmark Extraction  →  섹션 스키마 추출
Phase 2: Target Exploration    →  코드 팩트 수집
Phase 3: Document Authoring    →  CLAUDE.md 작성
Phase 4: Model-based Eval      →  메타모델 대비 평가
Phase 5: Iteration             →  결함 수정 + 재평가
```

상세 절차: [references/process.md](references/process.md)

## Meta-Model

모든 CLAUDE.md는 7개 섹션(S1~S7)으로 구성된다. 각 섹션의 슬롯·규칙·평가 기준은 TOML로 정의:

→ [references/meta-model.toml](references/meta-model.toml)

핵심 규칙 요약:

| Section | 필수 제약 |
|---------|----------|
| S1 Title | 정체성·기반·의존성 3요소 one-liner |
| S2 Philosophy | Layer 모델 + **핵심 원칙 정확히 한 줄** |
| S3 Domain | 패키지 고유 원칙 bullets (S2에서 분리) |
| S4 Structure | 파일 트리 + Layer 태그. 미성숙 시 한계/목표 서브섹션 |
| S5 Import | 절대 경로 + 코드 예시 2줄 |
| S6 Typing | 한 줄 고정 |
| S7 Rules | File Size + Dep Direction(화살표+산문 3줄) + Test Convention |

## Phase 1: Benchmark Extraction

1. 벤치마크 CLAUDE.md를 읽는다
2. `meta-model.toml`의 섹션 스키마와 대조하여 구조를 확인한다
3. 벤치마크에만 있는 패키지 고유 섹션(ea-kernel의 Profile Design Principles 등)을 식별한다

## Phase 2: Target Exploration

대상 패키지 `src/{pkg}/` 아래 모든 `.py` 파일을 읽고 팩트를 수집한다:

- 파일별 주요 클래스/타입, `frozen` 여부
- 파일 간 import 관계 (의존성 방향)
- 외부 패키지 import 여부 (ea-kernel 등)
- 고아 모듈 (어디서도 import되지 않는 파일)
- 중복 정의 (같은 개념의 다른 이름)

## Phase 3: Document Authoring

메타모델 슬롯을 팩트로 채운다. 3가지 핵심 판단:

1. **핵심 원칙 집약** — 코드에서 관통하는 하나의 인사이트를 한 문장으로 압축. 나머지는 S3로.
2. **Layer 모델 설계** — 코드의 자연스러운 계층을 식별하고 접두사(L/N/P 등) + 번호 + 이름 부여.
3. **성숙도 판단** — current = target이면 서브섹션 없이, current ≠ target이면 한계/목표 서브섹션.

## Phase 4: Model-based Evaluation

`meta-model.toml`의 `[evaluation.criteria]` 10개 항목으로 평가한다:

```
severity=error   →  반드시 수정
severity=warning →  정당화하거나 수정
```

평가 산출물: 속성별 적합성 테이블 (`✅` / `⚠️` / `❌`)

차이가 발견되면 **정당한 차이**(패키지 성숙도, 고유 도메인 등)와 **결함**을 구분한다.

## Phase 5: Iteration

error를 수정하고 Phase 4를 재실행한다. 전체 criteria 통과 시 종료.
