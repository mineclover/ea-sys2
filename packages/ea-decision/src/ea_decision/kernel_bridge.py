"""Kernel integration bridge (N3).

This is the only module that imports ea_kernel types (lazily).
All other modules use string-based ID references for Kernel entities.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def create_rule_provenance(decision_ref: str, report_ref: str) -> Dict[str, Any]:
    """Create a RuleProvenance-compatible dict linking back to a Decision.

    Uses lazy import to avoid hard dependency at module load time.
    """
    try:
        from ea_kernel.types import RuleProvenance
        return RuleProvenance(
            decision_ref=decision_ref,
            report_ref=report_ref,
        )
    except ImportError:
        # Fallback: return a plain dict when ea_kernel is not available
        return {"decision_ref": decision_ref, "report_ref": report_ref}


def decision_result_from_rule_asset(rule_asset: Any) -> Dict[str, Any]:
    """Extract decision-relevant metadata from a Kernel RuleAsset.

    Uses lazy import to avoid hard dependency at module load time.
    """
    try:
        from ea_kernel.types import RuleAsset
        if isinstance(rule_asset, RuleAsset):
            return {
                "rule_id": rule_asset.id,
                "rule_name": rule_asset.name,
                "lifecycle_state": rule_asset.lifecycle.state.value
                if hasattr(rule_asset, "lifecycle") and rule_asset.lifecycle
                else None,
            }
    except ImportError:
        pass
    return {"raw": str(rule_asset)}
