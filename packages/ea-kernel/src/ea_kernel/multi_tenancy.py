"""Multi-tenancy support for Governance System.

This module provides the MultiTenantManager, which orchestrates multiple
isolated GovernanceSystem instances, and utilities for cross-tenant analysis.
"""

from __future__ import annotations

from pathlib import Path

from ea_kernel.governance import GovernanceSystem
from ea_kernel.types import KernelSchema


class MultiTenantManager:
    """Manages multiple GovernanceSystem instances for multi-tenancy.

    Responsibilities:
    1. Tenant Isolation: Provide isolated data directories per tenant.
    2. Shared Kernel: Distribute the shared KernelSchema to all tenants.
    3. Cross-Tenant Analysis: Aggregate data across tenants.
    """

    def __init__(self, base_data_dir: Path, shared_schema: KernelSchema) -> None:
        self.base_data_dir = base_data_dir
        self.base_data_dir.mkdir(parents=True, exist_ok=True)
        self.shared_schema = shared_schema
        self._tenants: dict[str, GovernanceSystem] = {}

    def get_tenant(self, tenant_id: str) -> GovernanceSystem:
        """Get or create a GovernanceSystem instance for a specific tenant."""
        if tenant_id not in self._tenants:
            # Create isolated environment for tenant
            tenant_dir = self.base_data_dir / tenant_id
            self._tenants[tenant_id] = GovernanceSystem(tenant_dir, self.shared_schema)
        return self._tenants[tenant_id]

    def list_tenants(self) -> list[str]:
        """List all active tenant IDs."""
        return list(self._tenants.keys())

    def sync_shared_schema(self, new_schema: KernelSchema) -> None:
        """Update the shared schema across all active tenants."""
        self.shared_schema = new_schema
        for sys in self._tenants.values():
            sys._base_schema = new_schema
            sys._rebuild_corpus()

    # ── Cross-Tenant Analysis ─────────────────────────────────────

    def aggregate_rule_adoption(self) -> dict[str, int]:
        """Count how many tenants have adopted each rule ID."""
        counts: dict[str, int] = {}
        for sys in self._tenants.values():
            active = sys.rule_store.active_rules()
            for asset in active:
                rid = asset.rule.id
                counts[rid] = counts.get(rid, 0) + 1
        return counts

    def find_common_patterns(self, min_adoption: int = 2) -> list[str]:
        """Identify rules widely adopted across tenants (Potential Standards)."""
        adoption = self.aggregate_rule_adoption()
        return [rid for rid, count in adoption.items() if count >= min_adoption]

    def cross_tenant_conflicts(self) -> list[str]:
        """Detect if different tenants have conflicting rules for same ID."""
        # This requires comparing rule definitions, not just IDs.
        # For simplicity, we check if same ID has different logic (hash/validity).
        definitions: dict[str, set[tuple[bool, int]]] = {} # id -> {(valid, priority)}

        for sys in self._tenants.values():
            active = sys.rule_store.active_rules()
            for asset in active:
                rid = asset.rule.id
                key = (asset.rule.valid, asset.rule.priority)
                definitions.setdefault(rid, set()).add(key)

        conflicts = []
        for rid, versions in definitions.items():
            if len(versions) > 1:
                conflicts.append(f"Rule {rid} has conflicting definitions across tenants: {versions}")

        return conflicts
