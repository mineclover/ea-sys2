# Governance Profile Stack

이 디렉터리는 거버넌스 레이어를 다음 2단계로 분리한 모델링 스택을 정의한다.

1. **Governance Meta-Meta Model** (공통 어휘/계약)
2. **System-specific Governance Profile** (시스템별 구체화)

구성:

- `00-governance-meta-model.toml`
  - 내부/외부 시스템이 공통으로 따르는 거버넌스 계약 어휘
  - entrypoint, endpoint, coordinator, policy, request/response/error/transaction/decision-trace contracts
  - 목적(goal) 중심 어휘: transparency, consistency, traceability, evolvability
- `../ea_sys/10-governance.toml`
  - `ea-sys` 내부용 거버넌스 프로파일 (운영 계약)
- `20-external-governance.toml`
  - 외부 연동(파트너/웹훅/API)용 거버넌스 프로파일 예시

검증:

```bash
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_governance_profile_stack.py --simulate
```

핵심 원칙:

- 공통 거버넌스 의미론은 meta-meta 모델에 고정한다.
- `ea-sys`/외부 시스템은 해당 의미론을 재사용해 시스템별로 구체화한다.
- 시스템별 구현 차이는 profile로 분리하고, 어휘 드리프트는 검증에서 경고/실패 처리한다.
- 목적(goal)과 계약(contract)의 연결 규칙은 meta-meta 모델에서 고정하고, 시스템 프로필은 해당 목적을 구현 규칙으로 구체화한다.
