# Non-Kernel Technical Debt Plan (Draft v0.2)

작성일: 2026-02-14  
범위: `ea-infra`, `ea-governance`, `ea-decision`, `ea-needs`, `ea-flow`  
목표: 비커널 레이어의 기능 안정성과 구현 정합성을 커널 운영 기준에 맞춰 단계적으로 상향

## 1. 현재 기준선 (2026-02-14)

| Layer | Tests | Ruff | Mypy | 상태 요약 |
|---|---:|---:|---:|---|
| infra | 1 passed | 47 errors | 7 errors | 스타일/타입 부채 중심 |
| governance | 15 passed | 80 errors | 5 errors | 문서 대비 구현은 있으나 타입 정합성 잔여 |
| decision | 21 passed | 222 errors | 22 errors | 레거시 shim/구식 typing/무타입 함수 다수 |
| needs | 56 passed | 0 | 0 | 상대적으로 안정. 회귀 방지 중심 관리 |
| flow | 8 passed | 141 errors | 11 errors | 설계상 잔여 한계 + 타입 계약 위반 |
| **Total** | **101 passed** | **490 errors** | **45 errors** | 비커널 전반 정리 필요 |

참고 근거:
- `packages/ea-flow/CLAUDE.md`의 잔여 한계 섹션
- `packages/ea-decision/CLAUDE.md`의 잔여 한계 섹션
- `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/README.md`의 레이어 기준선

## 1.1 진행 결과 (2026-02-14)

| Layer | Ruff | Mypy | Tests |
|---|---:|---:|---:|
| infra | 0 | 0 | pass |
| governance | 0 | 0 | pass |
| decision | 0 | 0 | pass |
| needs | 0 | 0 | pass |
| flow | 0 | 0 | pass |
| **Total** | **0** | **0** | **101 passed** |

진척:
- Wave 1(스타일/기계적 부채): 완료
- Wave 2(타입 정합성): 완료
- Wave 4(최종 게이트 검증): 완료
- Wave 3(테스트 보강): 일부 잔여(저커버리지 모듈 중심 추가 보강 필요)
- Infra의 `vector_store` 구현은 제거 완료

## 2. 실행 우선순위 (고정)

요청 순서대로 고정:
1. Infra
2. Governance
3. Decision
4. Needs
5. Flow

주의:
- Governance의 일부 타입 오류는 Flow/Decision 타입 표면과 연결되어 있어, Governance 1차 정리 후 최종 클로징은 Flow 단계에서 재검증이 필요하다.

## 3. 레이어별 작업 초안

### 3.1 Infra (P0)

핵심 부채:
- 구식 typing (`List`, `Optional`) 및 공백/정렬 이슈
- 타입 시그니처의 Optional/반환 타입 정합성 부족
- 테스트가 `indexer` 중심으로 편중

작업 항목:
- Ruff auto-fix 가능한 항목 일괄 정리(import/whitespace/typing modernize)
- `indexer.py`의 `mypy` 오류 제거
- 인덱서 중심 검증 시나리오 보강

완료 기준:
- `uv run ruff check packages/ea-infra` 통과
- `uv run mypy packages/ea-infra/src` 통과
- `uv run pytest -q packages/ea-infra/tests` 통과

### 3.2 Governance (P1)

핵심 부채:
- import/공백/구식 typing 부채
- `meta_model.py` 반환 타입 누락
- Flow/Decision 인터페이스 변경 영향에 취약

작업 항목:
- 스타일/정렬/unused import 정리
- `meta_model.py`, `facade.py`, `execution_service.py` 타입 선언 정리
- Flow/Decision 경계 타입 계약을 명시 타입으로 고정

완료 기준:
- `uv run ruff check packages/ea-governance` 통과
- `uv run mypy packages/ea-governance/src` 통과
- `uv run pytest -q packages/ea-governance/tests` 통과

### 3.3 Decision (P1)

핵심 부채:
- 비중 큰 Ruff 부채(222건): import/typing/whitespace 중심
- `topic.py`, `process.py`, `registry.py`의 무타입 함수/옵셔널 타입 불일치
- shim 모듈과 신규 경로 혼재로 정합성 저하

작업 항목:
- 구식 typing 전면 현대화 (`list[]`, `dict[]`, `X | None`)
- `topic.py`/`process.py`/`registry.py` 함수 시그니처 정밀 타입화
- `kernel_bridge.py` Any 반환 경로 제거
- shim 모듈은 최소 표면만 유지하고 내부 참조는 canonical 모듈로 정리

완료 기준:
- `uv run ruff check packages/ea-decision` 통과
- `uv run mypy packages/ea-decision/src` 통과
- `uv run pytest -q packages/ea-decision/tests` 통과

### 3.4 Needs (P2, 유지보수)

핵심 상태:
- 현재 `ruff/mypy` 0건으로 안정 상태

작업 항목:
- 신규 변경 시 레이어 규칙(불변 N1, mutable N2) 회귀 검증 강화
- repository/kernel_bridge 경계 테스트 최소 1~2건 보강

완료 기준:
- 기존 0-error 상태 유지
- `uv run pytest -q packages/ea-needs/tests` 지속 통과

### 3.5 Flow (P1, 구조적 정합성)

핵심 부채:
- Ruff 141건 + Mypy 11건
- `StepImplementer` override 타입(LSP) 위반
- `spec/topology/runtime` 계약 불일치 및 export 표면 부정확
- 문서상 잔여 한계(그래프/조건 런타임 미연동)

작업 항목:
- 타입 계약 정리: `StepSpec`/implementer 메서드 시그니처 일치
- `definitions.py`/`ontology.py` shim export 정합성 보강
- `kernel_actions.py` Optional 인자 타입 정리
- 최소 실행 정합성 테스트 보강(실행 + rollback + anchor/type contract)

완료 기준:
- `uv run ruff check packages/ea-flow` 통과
- `uv run mypy packages/ea-flow/src` 통과
- `uv run pytest -q packages/ea-flow/tests` 통과

## 4. 단계별 실행 계획

### Wave 0: 기준선 고정
- 현재 수치와 실패 케이스를 문서화하고 CI 기준으로 고정

### Wave 1: 스타일/기계적 부채 제거
- Infra → Governance → Decision → Needs → Flow 순서로 Ruff 중심 정리
- 자동 수정 가능 항목 우선 처리

### Wave 2: 타입 정합성 클로징
- 동일 순서로 `mypy` 0-error 목표
- 인터페이스 경계(Flow↔Governance, Decision↔Governance) 우선

### Wave 3: 테스트 보강 및 회귀 차단
- Infra 인덱서, Flow 계약 테스트 추가
- 레이어별 독립 테스트 + 비커널 통합 테스트 상시 통과

### Wave 4: 최종 게이트
- 아래 게이트를 모두 통과하면 비커널 기술부채 1차 종료

```bash
uv run ruff check packages/ea-infra packages/ea-governance packages/ea-decision packages/ea-needs packages/ea-flow
uv run mypy packages/ea-infra/src packages/ea-governance/src packages/ea-decision/src packages/ea-needs/src packages/ea-flow/src
uv run pytest -q packages/ea-infra/tests packages/ea-governance/tests packages/ea-decision/tests packages/ea-needs/tests packages/ea-flow/tests
```

## 5. 리스크와 대응

- 리스크: Governance 오류가 Flow/Decision 정비 후 재발 가능  
  대응: Governance를 Wave 1/2에서 1차 정리하고 Wave 4에서 최종 재검증

- 리스크: 자동 포맷 대량 적용 시 의미 변경 가능성  
  대응: 레이어 단위 작은 커밋 + 레이어 단위 테스트 즉시 실행

- 리스크: shim 제거/축소 과정에서 하위 호환 깨짐  
  대응: shim 경로 호출 테스트 유지 후 단계적 정리

## 6. 산출물

- 본 문서 업데이트(수치/진척률)
- 레이어별 debt fix PR(또는 커밋) 기록
- 최종 비커널 품질 리포트(`ruff=0`, `mypy=0`, tests pass)
