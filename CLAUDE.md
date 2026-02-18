# EA-Sys2 — Architecture Guide

> 정규 레이어 정의: `packages/ea-kernel/docs/system_spec_layers.md`

## Project Vision

경량 커널 메타모델 기반의 **거버넌스 모델링 프레임워크**. 각 레이어는 자기 관점의 전문성과 검증 규칙을 가진 독립 시스템으로 동작하며, 자기 프로파일에서 다른 레이어를 자기 관점으로 정의한다(6x6 `*ModelPort`). 정책/제약 모델은 중앙집중이 아니라 각 레이어 내부에서 독립적으로 관리한다.

## Layer Architecture

### 메인 모델 (5계층)

모델 정의 순서: `infra > decision > needs > kernel > flow` — 구현 호출 순서가 아니라 모델 정의 책임의 상위-하위 체계.

| 계층 | 핵심 책임 | 모델 관점 |
|------|----------|----------|
| **Infra** (00) | row 데이터 설계 | 저장소, 상태, 인덱싱, 입출력 데이터 관리 모델 |
| **Decision** (20) | 의사결정 메타-메타 모델 정의 | 의사결정 활동/상태/옵션/평가/결론 구조 어휘와 전이 규칙 |
| **Needs** (30) | 요구 모델 정의 | 목표/요구/백로그/컨텍스트의 정형 표현 |
| **Kernel** (40) | 도메인 핵심 모델 정의 | 존재론(요소/관계)과 유효성 규칙 |
| **Flow** (50) | 실행/데이터 흐름 모델 + 구체적 데이터 스키마 스펙 소유 | 단계 순서, 입출력 소비/생산, 트리거/전이, **구체적 데이터 형상(JSON Schema·DB Schema·I/O 계약·데이터 카탈로그)**. 6x6 계약 소유(`FlowLayerContractMatrix`) |

### Governance (별도 관리 시스템)

`Governance`는 위 5개 레이어 전체를 관리하는 별도 관리 시스템이다. 거버넌스 자체의 운영 방식도 메타-메타 모델로 먼저 설계하고, 그 모델대로 운영한다. 즉 거버넌스는 다른 레이어의 관리자인 동시에 자기 운영 모델의 메타-메타 모델 설계이기도 하다.

- 각 레이어 스펙을 이해하고 입력 인터페이스 제공·레이어별 데이터 적합화·진입점 설계를 담당
- 모델 등록/버전/활성 상태 관리, 검증 실행 이력 및 진화(승격/폐기) 관리
- **6단계 라이프사이클 주입**: 각 레이어는 자기 도메인 어휘·규칙만 소유하고, 그 규칙/모델의 작성→판단→기록→분석→진화→전파 라이프사이클은 Governance가 `TransactionManager` + `GovernanceSystem` + 레이어별 Ops를 통해 외부에서 주입·제어한다
- `Infra`가 메타-메타 계약(저장 포트/스키마 계약)을 정의하고, 그 위 제어 구현은 `Governance`가 담당
- 시스템 진입점(`GovernanceEntryPort`)을 통해 다른 레이어를 핸들링
- 2단계 분리:
  - **거버넌스 운영 메타-메타 모델** (공통 어휘·운영 구조 설계): `src/ea_kernel/profiles/governance_profile_stack/00-governance-meta-model.toml`
  - **시스템별 운영 프로파일** (설계된 모델대로 구체화): `src/ea_kernel/profiles/ea_sys/10-governance.toml`, `governance_profile_stack/20-external-governance.toml`

### 계층 흐름

```
모델 정의 흐름:       infra -> decision -> needs -> kernel -> flow
거버넌스 관리 흐름:    governance -> {infra, decision, needs, kernel, flow}
런타임 엔트리포인트:   decision -> needs -> kernel -> flow
피드백 흐름:          flow -> kernel -> governance -> decision
```

- **모델 정의**: infra가 데이터 관리 모델을 제공 → decision이 메타-메타 구조 정형화 → needs가 요구 정형화 → kernel이 핵심 의미 체계 고정 → flow가 실행 가능한 절차/데이터 전이 표현 + **구체적 데이터 스키마 스펙**(JSON Schema, DB Schema, I/O 계약, 데이터 카탈로그) 소유
- **런타임 엔트리포인트**: infra/governance는 체인 노드가 아니라 각각 row 데이터 설계/시스템 진입점 설계 담당
- **피드백**: flow 이력/결과 → kernel 제약 해석 → governance 버전/검증 이력 축적 → decision 모델 보정 환류

### 시뮬레이션 우선 검증

런타임 실행 이전에 모델 자체의 정합성을 정적 시뮬레이션으로 검증한다.

- **Layer-local relation integrity**: 각 레이어 규칙이 내부 relation 정의와 일치하는지
- **Decision coverage**: flow 주요 단계가 decision 메타-메타 규칙으로 통제되는지
- **Data availability**: `consumes` 입력이 `produces`/초기 데이터로 충족되는지
- **Sequence integrity**: `next` 체인이 단절되지 않는지

## Package Overview

| Package | 대응 레이어 | 의존성 | 상세 문서 |
|---------|-----------|--------|----------|
| `packages/ea-profile` | Profile — kernel-agnostic 프로파일 프레임워크 | Pure Python, zero dep | → `packages/ea-profile/CLAUDE.md` |
| `packages/ea-kernel` | Kernel — 경량 커널 메타모델 (KerML 설계 철학) | ea-profile | → `packages/ea-kernel/CLAUDE.md` |
| `packages/ea-needs` | Needs — 목표/요구/백로그/컨텍스트 정형 표현 | ea-kernel | → `packages/ea-needs/CLAUDE.md` |
| `packages/ea-decision` | Decision — 의사결정 활동/상태/옵션/평가/결론 어휘·전이 규칙 | ea-kernel, ea-needs | → `packages/ea-decision/CLAUDE.md` |
| `packages/ea-flow` | Flow — 실행 흐름 + 구체적 데이터 스키마 스펙, 6x6 계약 소유 | ea-kernel, ea-decision | → `packages/ea-flow/CLAUDE.md` |
| `packages/ea-governance` | Governance — 5개 레이어 관리 시스템 (등록/버전/활성/진입점) | ea-kernel, ea-decision, ea-flow, ea-needs | → `packages/ea-governance/CLAUDE.md` |
| `packages/ea-infra` | Infra — row 데이터 설계, 저장소/인덱싱/입출력 관리 모델 | ea-profile | → `packages/ea-infra/CLAUDE.md` |
| `web-kernel-viz/` | 커널 토폴로지 시각화 (독립 프론트엔드) | Vite + React + @xyflow/react | |

## Dependency Graph

```
web-kernel-viz (독립, Node)

ea-profile (프로파일 프레임워크, zero dep)
    ↑                  ↑
ea-infra (row 데이터)   ea-kernel (도메인 핵심 모델)
                           ↑
                       ea-needs (요구 모델)
                           ↑
                       ea-decision (의사결정 메타-메타 모델, + needs)
                           ↑
                       ea-flow (실행/데이터 흐름 모델, + decision)
                           ↑
                       ea-governance (관리 시스템, + decision + flow + needs)
```

## Workspace Setup

uv workspace 기반 모노레포. 패키지 간 의존성은 workspace 로컬 해결.

```bash
uv sync          # 전체 설치
make test        # 전체 테스트
make test-kernel # ea-kernel만
```

## Package Isolation

- ea-infra는 row 데이터 설계를 담당하며 ea-profile에만 의존 (M1 파이프라인용)
- web-kernel-viz는 Python 패키지와 무관 (독립 Node 앱)
- ea-governance는 5개 레이어 전체를 관리하는 별도 시스템 (단순 파사드가 아님)
