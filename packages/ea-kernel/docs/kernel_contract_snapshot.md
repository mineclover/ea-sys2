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
make test-kernel-contract-snapshot
```

## 벡터 정책

`kernel_judgment_vectors.snapshot.json`은 최소 allow/deny 대표 triple 세트를 포함한다.
각 벡터는 다음을 고정한다.

- `expected_verdict`
- `expected_confidence`
- `expected_winner_rule_id`

즉, 커널 버전 변경으로 룰 우선순위/판단 결과가 달라지면 `verify`가 실패하며,
이는 `ea-web` 연동 계약 재검토 신호로 사용한다.
