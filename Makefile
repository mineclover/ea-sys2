.PHONY: install dev test test-kernel test-kernel-contract test-kernel-self test-needs test-decision test-flow test-governance test-infra test-kernel-governance-db test-kernel-governance-reference test-kernel-contract-snapshot review-kernel-alignment review-kernel-self-alignment run-kernel-self-check run-kernel-self-check-strict gate-kernel-self check-kernel-governance-drift rehearse-kernel-governance-recovery build-kernel-governance-reference verify-kernel-governance-reference build-kernel-contract-snapshots verify-kernel-contract-snapshots gate-kernel-governance-db gate-kernel-governance-reference lint-kernel-governance typecheck-kernel-governance gate-kernel-stability lint format typecheck web-dev web-build

# Installation
install:
	uv sync

dev:
	uv sync --dev

# Testing (all packages)
test:
	uv run pytest packages/ea-kernel/tests packages/ea-kernel-contract/tests packages/ea-needs/tests packages/ea-decision/tests packages/ea-flow/tests packages/ea-governance/tests packages/ea-infra/tests -v

# Testing (individual packages)
test-kernel:
	uv run pytest packages/ea-kernel/tests -v

test-kernel-contract:
	uv run pytest packages/ea-kernel-contract/tests -v

test-kernel-self:
	uv run pytest packages/ea-kernel-self/tests -v

test-needs:
	uv run pytest packages/ea-needs/tests -v

test-decision:
	uv run pytest packages/ea-decision/tests -v

test-flow:
	uv run pytest packages/ea-flow/tests -v

test-governance:
	uv run pytest packages/ea-governance/tests -v

test-infra:
	uv run pytest packages/ea-infra/tests -v

test-kernel-governance-db:
	uv run pytest \
		packages/ea-kernel/tests/test_kernel_governance_migrations.py \
		packages/ea-kernel/tests/test_kernel_governance_registration.py \
		packages/ea-kernel/tests/test_kernel_governance_drift_script.py \
		packages/ea-kernel/tests/test_kernel_governance_recovery.py \
		packages/ea-governance/tests/test_transaction_persistence.py \
		-q

test-kernel-governance-reference:
	uv run pytest \
		packages/ea-kernel/tests/test_kernel_governance_reference_snapshot.py \
		-q

test-kernel-contract-snapshot:
	uv run pytest \
		packages/ea-kernel/tests/test_kernel_contract_snapshot.py \
		-q

review-kernel-alignment:
	uv run python packages/ea-kernel/src/ea_kernel/scripts/review_ralph_tui_kernel_alignment.py \
		--strict \
		--output-json packages/ea-kernel/docs/reference/kernel_ralph_tui_kernel_alignment.latest.json

review-kernel-self-alignment:
	uv run python packages/ea-kernel/src/ea_kernel/scripts/review_kernel_self_alignment.py \
		--strict \
		--output-json packages/ea-kernel/docs/reference/kernel_self_alignment.latest.json

run-kernel-self-check:
	uv run ea-kernel-self \
		--output-json packages/ea-kernel/docs/reference/ea_kernel_self.latest.json

run-kernel-self-check-strict:
	uv run ea-kernel-self \
		--strict \
		--output-json packages/ea-kernel/docs/reference/ea_kernel_self.latest.json

gate-kernel-self: test-kernel-self run-kernel-self-check-strict

check-kernel-governance-drift:
	@tmp_dir=$$(mktemp -d 2>/dev/null || mktemp -d -t ea-kernel-drift); \
	uv run python -c "from pathlib import Path; from ea_kernel.migrations.kernel_governance import apply_kernel_governance_migrations; apply_kernel_governance_migrations(Path(\"$$tmp_dir\"))"; \
	uv run python packages/ea-kernel/src/ea_kernel/scripts/check_kernel_governance_drift.py --data-dir "$$tmp_dir"; \
	rm -rf "$$tmp_dir"

rehearse-kernel-governance-recovery:
	@tmp_data=$$(mktemp -d 2>/dev/null || mktemp -d -t ea-kernel-recovery-data); \
	tmp_backup=$$(mktemp -d 2>/dev/null || mktemp -d -t ea-kernel-recovery-backup); \
	uv run python packages/ea-kernel/src/ea_kernel/scripts/rehearse_kernel_governance_recovery.py --data-dir "$$tmp_data" --backup-dir "$$tmp_backup"; \
	rm -rf "$$tmp_data" "$$tmp_backup"

build-kernel-governance-reference:
	uv run python packages/ea-kernel/src/ea_kernel/scripts/kernel_governance_reference_snapshot.py build --force-reset

verify-kernel-governance-reference:
	uv run python packages/ea-kernel/src/ea_kernel/scripts/kernel_governance_reference_snapshot.py verify

build-kernel-contract-snapshots:
	uv run python packages/ea-kernel/src/ea_kernel/scripts/kernel_contract_snapshot.py build

verify-kernel-contract-snapshots:
	uv run python packages/ea-kernel/src/ea_kernel/scripts/kernel_contract_snapshot.py verify

gate-kernel-governance-db: check-kernel-governance-drift rehearse-kernel-governance-recovery test-kernel-governance-db

gate-kernel-governance-reference: build-kernel-governance-reference verify-kernel-governance-reference test-kernel-governance-reference

lint-kernel-governance:
	uv run ruff check \
		packages/ea-kernel/src/ea_kernel/governance.py \
		packages/ea-kernel/src/ea_kernel/migrations/kernel_governance.py \
		packages/ea-kernel/src/ea_kernel/model_registration.py \
		packages/ea-kernel/src/ea_kernel/scripts/check_kernel_governance_drift.py \
		packages/ea-kernel/src/ea_kernel/scripts/rehearse_kernel_governance_recovery.py \
		packages/ea-kernel/src/ea_kernel/scripts/kernel_governance_reference_snapshot.py \
		packages/ea-kernel/examples/validate_ralph_tui_layers.py \
		packages/ea-governance/src/ea_governance/transaction.py \
		packages/ea-governance/src/ea_governance/execution_service.py \
		packages/ea-governance/src/ea_governance/facade.py \
		packages/ea-governance/tests/test_transaction_persistence.py \
		packages/ea-kernel/tests/test_validate_ralph_tui_layers.py

typecheck-kernel-governance:
	uv run mypy --follow-imports=skip \
		packages/ea-kernel/src/ea_kernel/governance.py \
		packages/ea-kernel/src/ea_kernel/migrations/kernel_governance.py \
		packages/ea-kernel/src/ea_kernel/model_registration.py \
		packages/ea-kernel/src/ea_kernel/scripts/check_kernel_governance_drift.py \
		packages/ea-kernel/src/ea_kernel/scripts/rehearse_kernel_governance_recovery.py \
		packages/ea-kernel/src/ea_kernel/scripts/kernel_governance_reference_snapshot.py \
		packages/ea-kernel/examples/validate_ralph_tui_layers.py \
		packages/ea-governance/src/ea_governance/transaction.py \
		packages/ea-governance/src/ea_governance/execution_service.py \
		packages/ea-governance/src/ea_governance/facade.py

gate-kernel-stability: review-kernel-alignment review-kernel-self-alignment gate-kernel-self gate-kernel-governance-db gate-kernel-governance-reference lint-kernel-governance typecheck-kernel-governance test-kernel

# Linting
lint:
	uv run ruff check packages/

format:
	uv run ruff format packages/

# Type checking
typecheck:
	uv run mypy packages/

# Web (kernel-viz)
web-dev:
	cd web-kernel-viz && npm run dev

web-build:
	cd web-kernel-viz && npm run build

web-install:
	cd web-kernel-viz && npm install
