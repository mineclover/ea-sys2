# EA-Sys2 — Architecture Guide

## Project Vision

경량 커널 메타모델 기반의 **거버넌스 모델링 프레임워크**. 구조(Kernel) → 의사결정(Decision) → 실행(Flow) → 통합(Governance) 4계층.

## Package Overview

| Package | 역할 | 의존성 | 상세 문서 |
|---------|------|--------|----------|
| `packages/ea-kernel` | 경량 커널 메타모델 (KerML 설계 철학) | Pure Python, zero dep | → `packages/ea-kernel/CLAUDE.md` |
| `packages/ea-needs` | 니즈 레이어 — Stakeholder Desires & Justifications | ea-kernel | → `packages/ea-needs/CLAUDE.md` |
| `packages/ea-decision` | 의사결정 레이어 — Design Thinking & Intent | ea-kernel, ea-needs | |
| `packages/ea-flow` | 실행 레이어 — Workflow & Automation | ea-kernel, ea-decision | |
| `packages/ea-governance` | 통합 레이어 — Kernel+Decision+Flow 파사드 | ea-kernel, ea-decision, ea-flow | |
| `packages/ea-infra` | 인프라 레이어 — 데이터베이스 | chromadb | |
| `web-kernel-viz/` | 커널 토폴로지 시각화 프론트엔드 | Vite + React + @xyflow/react | |

## Dependency Graph

```
ea-infra (독립)          web-kernel-viz (독립, Node)

ea-kernel (foundation, zero dep)
    ↑
ea-needs (depends on kernel)
    ↑
ea-decision (depends on kernel + needs)
    ↑
ea-flow (depends on kernel + decision)
    ↑
ea-governance (facade: kernel + decision + flow)
```

## Workspace Setup

uv workspace 기반 모노레포. 패키지 간 의존성은 workspace 로컬 해결.

```bash
uv sync          # 전체 설치
make test        # 전체 테스트
make test-kernel # ea-kernel만
```

## Package Isolation

- ea-infra는 다른 ea-* 패키지와 무관 (독립)
- web-kernel-viz는 Python 패키지와 무관 (독립 Node 앱)
- ea-governance는 나머지 3개(kernel, decision, flow) 통합 파사드
