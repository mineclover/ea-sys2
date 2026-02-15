# EA-Sys2 — Architecture Guide

## Project Vision

경량 커널 메타모델 기반의 **거버넌스 모델링 프레임워크**. 각 레이어가 서로 다른 질문에 답하도록 분리하여 결합도를 낮추고, 레이어별 독립 검증과 진화를 가능하게 한 구조.

## Layer Architecture (6계층)

각 레이어는 고유한 관심사를 가지며, 대응하는 계약 정의(`packages/ea-kernel/examples/ea-sys/*.toml`)로 명세됨.

| 계층 | 핵심 질문 | 설명 |
|------|----------|------|
| **Infra** (00) | "어디에 어떻게 저장되는가?" | 데이터 관리 계층. 저장/버전/검증 이력 같은 영속 계약(스토어, 포트)을 정의. 비즈니스 의미 판단은 하지 않음 |
| **Governance** (10) | "누가 어떤 버전으로 승인되어 쓰이는가?" | 메타-메타모델의 핵심 계층. 각 레이어의 스펙을 이해하고, 입력 인터페이스 제공·레이어별 데이터 적합화·버전 관리·등록/검증/활성/변경 통제·DB 저장을 총괄. 진입점(`GovernanceEntryPort`)을 통해 다른 레이어를 핸들링 |
| **Decision** (20) | "결정 과정은 어떤 구조를 따르는가?" | 의사결정 메타-메타 계층. 결정 과정의 어휘/상태/평가 구조를 정의하고, 결정 근거의 구조적 정합성을 담당 |
| **Needs** (30) | "무엇이 필요한가?" | 요구 계층. 유스케이스/상황/제약/우선순위 니즈를 수집·정규화·버전화해서 downstream에 전달 |
| **Kernel** (40) | "도메인의 의미적 기준은 무엇인가?" | 핵심 의미 계층. 도메인 존재론(요소/관계)과 유효성 규칙의 기준면을 고정. 다른 레이어는 여기서 의미적 정당성을 얻음 |
| **Flow** (50) | "어떤 순서로 무엇을 실행하는가?" | 실행/데이터 흐름 계층. 단계 순서, 입출력 소비/생산, 검증/퍼시스트/퍼블리시를 구체화. 6x6 계약의 소유/조율도 flow에 위임(`FlowLayerContractMatrix`) |

### 핵심 분리 원칙

1. **모델 정의 순서**: `infra → decision → needs → kernel → flow`
2. **거버넌스 중심 조율**: `governance`가 각 레이어의 스펙을 이해하고 입력/버전/저장/활성을 총괄하는 메타-메타모델의 핵심
3. **실행 구체화 책임**: `flow` — 단계 조합과 데이터 흐름 구체화
4. **의미 기준 책임**: `kernel` — 모든 레이어의 의미적 정당성 원천

## Package Overview

| Package | 대응 레이어 | 의존성 | 상세 문서 |
|---------|-----------|--------|----------|
| `packages/ea-kernel` | Kernel — 경량 커널 메타모델 (KerML 설계 철학) | Pure Python, zero dep | → `packages/ea-kernel/CLAUDE.md` |
| `packages/ea-needs` | Needs — 니즈 수집·정규화·버전화 | ea-kernel | → `packages/ea-needs/CLAUDE.md` |
| `packages/ea-decision` | Decision — 의사결정 어휘·상태·평가 구조 | ea-kernel, ea-needs | |
| `packages/ea-flow` | Flow — 실행/데이터 흐름 구체화, 6x6 계약 조율 | ea-kernel, ea-decision | |
| `packages/ea-governance` | Governance — 레이어 스펙 이해·입력 인터페이스·버전/저장/활성 총괄 | ea-kernel, ea-decision, ea-flow | |
| `packages/ea-infra` | Infra — 영속 계약, 스토어/포트 정의 | chromadb | |
| `web-kernel-viz/` | 커널 토폴로지 시각화 (독립 프론트엔드) | Vite + React + @xyflow/react | |

## Dependency Graph

```
ea-infra (독립, 영속 계약)     web-kernel-viz (독립, Node)

ea-kernel (의미 기준, zero dep)
    ↑
ea-needs (요구 수집, depends on kernel)
    ↑
ea-decision (의사결정 구조, depends on kernel + needs)
    ↑
ea-flow (실행 구체화, depends on kernel + decision)
    ↑
ea-governance (메타-메타모델 핵심, depends on kernel + decision + flow)
```

## Workspace Setup

uv workspace 기반 모노레포. 패키지 간 의존성은 workspace 로컬 해결.

```bash
uv sync          # 전체 설치
make test        # 전체 테스트
make test-kernel # ea-kernel만
```

## Package Isolation

- ea-infra는 영속 계약만 정의하며 다른 ea-* 패키지와 무관 (독립)
- web-kernel-viz는 Python 패키지와 무관 (독립 Node 앱)
- ea-governance는 메타-메타모델의 핵심으로, 각 레이어 스펙을 이해하고 입력 인터페이스·버전 관리·저장·활성을 총괄 (단순 파사드가 아님)
