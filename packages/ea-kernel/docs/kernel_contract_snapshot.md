# Kernel Contract Snapshot

`ea-kernel`의 의미론(스키마/룰/판단 벡터)을 외부 시스템(예: `ea-web`)이 안정적으로 소비할 수 있도록
결정적(deterministic) JSON 계약 산출물을 생성/검증한다.

## 산출물

기본 출력 경로:
- `packages/ea-kernel/docs/reference/contracts`

파일:
1. `kernel_schema.snapshot.json`
2. `kernel_rules.snapshot.json`
3. `kernel_judgment_vectors.snapshot.json`

`kernel_rules.snapshot.json`의 `layer_constraints`는 피드백 추적을 위해
deterministic `id`를 포함한다.

- 예: `lc-00-l4-l4-association`
- 의미: `{index}-{source_layer}-{target_layer}-{forbidden_relations}`

## 명령어

직접 실행:

```bash
uv run python packages/ea-kernel/src/ea_kernel/scripts/kernel_contract_snapshot.py build
uv run python packages/ea-kernel/src/ea_kernel/scripts/kernel_contract_snapshot.py verify
```

Make 타깃:

```bash
make build-kernel-contract-snapshots
make verify-kernel-contract-snapshots
make sync-kernel-contract-ts-sdk
make verify-kernel-contract-ts-sdk
make test-kernel-contract-snapshot
```

## SDK 공급

Snapshot 소비 SDK는 두 형태로 제공한다.

1. Python: `packages/ea-kernel-contract`
2. TypeScript: `packages/ea-kernel-contract-ts` (`@ea-sys2/kernel-contract-sdk`)

`build-kernel-contract-snapshots`는 snapshot 생성 후
TypeScript SDK의 `contracts/`도 자동 동기화한다.

## 벡터 정책

`kernel_judgment_vectors.snapshot.json`은 최소 allow/deny 대표 triple 세트를 포함한다.
각 벡터는 다음을 고정한다.

- `expected_verdict`
- `expected_confidence`
- `expected_winner_rule_id`

즉, 커널 버전 변경으로 룰 우선순위/판단 결과가 달라지면 `verify`가 실패하며,
이는 `ea-web` 연동 계약 재검토 신호로 사용한다.
