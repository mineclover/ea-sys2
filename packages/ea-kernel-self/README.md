# ea-kernel-self

`ea-kernel-self` is a practical runtime checker built on top of `ea-kernel`.

It validates a self-model profile through three stages:

1. Alignment review against `ea-kernel` source evidence
2. Model registration/validation/activation lifecycle
3. Runtime judgment checks with raw vs compiled profile rules

## Run

```bash
uv run ea-kernel-self --output-json ./ea-kernel-self-report.json
```

Use `--strict` to return non-zero when `status` is not `ok` (warnings/errors).

Workspace gate:

```bash
make gate-kernel-self
```
