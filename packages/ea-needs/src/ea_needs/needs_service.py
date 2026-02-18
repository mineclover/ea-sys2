"""Service layer for needs catalog queries.

Pure functions returning structured dicts — suitable for CLI, MCP, or API consumption.
Follows §3 service layer conventions: keyword-only args, dict[str, Any] return,
error dicts instead of exceptions.
"""

from __future__ import annotations

from typing import Any

from ea_needs.catalog import NeedCatalog


def list_stakeholders(*, catalog: NeedCatalog) -> dict[str, Any]:
    """List all stakeholders in the catalog."""
    return {
        "count": len(catalog.stakeholders),
        "stakeholders": [
            {
                "id": s.id,
                "name": s.name,
                "role": s.role,
                "context": s.context,
            }
            for s in catalog.stakeholders
        ],
    }


def list_use_cases(*, catalog: NeedCatalog) -> dict[str, Any]:
    """List all use cases in the catalog."""
    return {
        "count": len(catalog.use_cases),
        "use_cases": [
            {
                "id": uc.id,
                "title": uc.title,
                "actor": uc.actor,
                "situation": uc.situation,
                "purpose": uc.purpose,
                "outcome": uc.outcome,
                "tags": list(uc.tags),
                "version": uc.version,
            }
            for uc in catalog.use_cases
        ],
    }


def list_needs(
    *, catalog: NeedCatalog, status: str | None = None,
) -> dict[str, Any]:
    """List needs in the catalog, optionally filtered by status."""
    needs = catalog.needs
    if status is not None:
        needs = [n for n in needs if n.status.value == status]
    return {
        "count": len(needs),
        "filter": {"status": status},
        "needs": [
            {
                "id": n.id,
                "lineage_id": n.lineage_id,
                "version": n.version,
                "status": n.status.value,
                "priority": n.priority.value,
                "kernel_change_phase": n.kernel_change_phase.value,
                "action": n.statement.desire.action,
                "subject": n.statement.desire.subject,
                "target": n.statement.desire.target,
                "stakeholder_id": n.statement.stakeholder_id,
            }
            for n in needs
        ],
    }


def describe_need(
    *, catalog: NeedCatalog, need_id: str,
) -> dict[str, Any] | None:
    """Describe a single need with statement, process units, and decision evidence."""
    need = catalog.get_need(need_id)
    if need is None:
        return None

    process_units = catalog.process_units_for_need(need_id)

    return {
        "id": need.id,
        "lineage_id": need.lineage_id,
        "version": need.version,
        "status": need.status.value,
        "priority": need.priority.value,
        "kernel_change_phase": need.kernel_change_phase.value,
        "created_at": need.created_at,
        "updated_at": need.updated_at,
        "statement": {
            "stakeholder_id": need.statement.stakeholder_id,
            "desire": {
                "action": need.statement.desire.action,
                "subject": need.statement.desire.subject,
                "target": need.statement.desire.target,
            },
            "justifications": [
                {"type": j.type.value, "description": j.description}
                for j in need.statement.justifications
            ],
            "kernel_refs": list(need.statement.kernel_refs),
            "tags": list(need.statement.tags),
            "purpose": need.statement.purpose,
            "cause_types": [c.value for c in need.statement.cause_types],
            "complexity": need.statement.complexity.value,
        },
        "process_units": [
            {
                "id": pu.id,
                "stage": pu.stage.value,
                "label": pu.label,
                "description": pu.description,
                "sequence": pu.sequence,
            }
            for pu in process_units
        ],
        "decision_ref": need.decision_ref,
        "decision_evidence_refs": list(need.decision_evidence_refs),
        "inherited_from_decisions": list(need.inherited_from_decisions),
    }


def need_lineage(
    *, catalog: NeedCatalog, lineage_id: str,
) -> dict[str, Any] | None:
    """Return all versions of a need lineage."""
    versions = catalog.need_versions(lineage_id)
    if not versions:
        return None

    return {
        "lineage_id": lineage_id,
        "count": len(versions),
        "versions": [
            {
                "id": n.id,
                "version": n.version,
                "status": n.status.value,
                "priority": n.priority.value,
                "kernel_change_phase": n.kernel_change_phase.value,
                "action": n.statement.desire.action,
                "subject": n.statement.desire.subject,
                "created_at": n.created_at,
            }
            for n in versions
        ],
    }


def catalog_summary(*, catalog: NeedCatalog) -> dict[str, Any]:
    """Catalog overview: stakeholder count, need count, status distribution."""
    status_dist: dict[str, int] = {}
    for need in catalog.needs:
        key = need.status.value
        status_dist[key] = status_dist.get(key, 0) + 1

    return {
        "name": catalog.name,
        "description": catalog.description,
        "stakeholder_count": len(catalog.stakeholders),
        "use_case_count": len(catalog.use_cases),
        "need_count": len(catalog.needs),
        "relation_count": len(catalog.relations),
        "process_unit_count": len(catalog.process_units),
        "status_distribution": status_dist,
    }
