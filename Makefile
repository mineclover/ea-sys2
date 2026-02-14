.PHONY: install dev test test-kernel test-needs test-decision test-flow test-governance test-infra test-kernel-governance-db test-kernel-governance-reference review-kernel-alignment review-kernel-self-alignment check-kernel-governance-drift rehearse-kernel-governance-recovery build-kernel-governance-reference verify-kernel-governance-reference gate-kernel-governance-db gate-kernel-governance-reference lint format typecheck web-dev web-build

# Installation
install:
	uv sync

dev:
	uv sync --dev

# Testing (all packages)
test:
	uv run pytest packages/ea-kernel/tests packages/ea-needs/tests packages/ea-decision/tests packages/ea-flow/tests packages/ea-governance/tests packages/ea-infra/tests -v

# Testing (individual packages)
test-kernel:
	uv run pytest packages/ea-kernel/tests -v

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

review-kernel-alignment:
	uv run python packages/ea-kernel/src/ea_kernel/scripts/review_ralph_tui_kernel_alignment.py \
		--strict \
		--output-json packages/ea-kernel/docs/reference/kernel_ralph_tui_kernel_alignment.latest.json

review-kernel-self-alignment:
	uv run python packages/ea-kernel/src/ea_kernel/scripts/review_kernel_self_alignment.py \
		--strict \
		--output-json packages/ea-kernel/docs/reference/kernel_self_alignment.latest.json

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

gate-kernel-governance-db: check-kernel-governance-drift rehearse-kernel-governance-recovery test-kernel-governance-db

gate-kernel-governance-reference: build-kernel-governance-reference verify-kernel-governance-reference test-kernel-governance-reference

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
