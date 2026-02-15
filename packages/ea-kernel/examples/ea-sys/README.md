# EA System Independent Layer Profiles

This directory is the canonical location for system-level layer models.
Each file is an independently valid `ea-kernel` profile.
There is no merge/composition step.

All six layers share kernel category/relation vocabulary, but each file models a different responsibility and implementation focus.
Policy/constraint ownership is also layer-local: each layer defines and manages its own control semantics.

- `00-infra.toml` - row 데이터 설계
- `10-governance.toml` - 위 5개 레이어 전체를 관리하는 관리 시스템으로 동작한다
- `20-decision.toml` - 의사결정 메타-메타 모델 정의
- `30-needs.toml` - 요구 모델 정의
- `40-kernel.toml` - 도메인 핵심 모델 정의
- `50-flow.toml` - 실행/데이터 흐름 모델 정의

Main model order:

- `infra > decision > needs > kernel > flow`

Governance role:

- Governance manages meta-meta/meta/instance control for all layer models.
- Infra defines row-data contracts and persistence-oriented structure/ports.
- Governance defines system entrypoint contracts and routing/control workflows.
- Runtime/API model entrypoint chain is:
  - `decision > needs > kernel > flow`
  - requests enter via `GovernanceEntryPort` and are routed according to the chain above.
- Governance also models `/models/*` API as explicit endpoint contracts:
  - endpoints: `ModelRegisterEndpoint`, `ModelValidateEndpoint`, `ModelActivateEndpoint`, `ModelStateEndpoint`
  - records: request/response/error/transaction contracts are modeled as passive structures in `10-governance.toml`

## Validate Layers

Validate all layers:

```bash
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ea_sys_layers.py
```

Validate one layer:

```bash
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ea_sys_layers.py --layer governance
```

Run static data-flow simulation (no runtime execution):

```bash
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ea_sys_layers.py --simulate
```

Simulation includes:

- governance entrypoint contract check
- governance model API contract check (`/models/*` endpoint/record flow)
- 6x6 delegated contract check (`ea-flow` owns matrix/coordination, other layers keep port declarations)
