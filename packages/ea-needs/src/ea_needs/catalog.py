"""NeedCatalog aggregate root (N2).

Mutable container managing stakeholders, needs, and their relations.
Need wraps immutable NeedStatement with mutable status/priority lifecycle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ea_needs.types import (
    Desire,
    Justification,
    JustificationType,
    NeedPriority,
    NeedRelationType,
    NeedStatement,
    NeedStatus,
    Stakeholder,
    _generate_id,
    _now,
)

# ---------------------------------------------------------------------------
# Valid state transitions
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[NeedStatus, list[NeedStatus]] = {
    NeedStatus.DRAFT: [NeedStatus.EXPRESSED, NeedStatus.WITHDRAWN],
    NeedStatus.EXPRESSED: [NeedStatus.ACKNOWLEDGED, NeedStatus.WITHDRAWN],
    NeedStatus.ACKNOWLEDGED: [NeedStatus.ADDRESSED, NeedStatus.WITHDRAWN],
    NeedStatus.ADDRESSED: [],
    NeedStatus.WITHDRAWN: [],
}


# ---------------------------------------------------------------------------
# Need — mutable wrapper around frozen NeedStatement
# ---------------------------------------------------------------------------

@dataclass
class Need:
    """Mutable lifecycle wrapper around an immutable NeedStatement.

    The statement itself (stakeholder_id, desire, justifications) never changes.
    Only status, priority, decision_ref, and timestamps are mutable.
    """
    id: str
    statement: NeedStatement
    status: NeedStatus = NeedStatus.DRAFT
    priority: NeedPriority = NeedPriority.MEDIUM
    decision_ref: str | None = None  # link to ea-decision topic id
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def transition_to(self, new_status: NeedStatus) -> None:
        """Transition to a new status, enforcing valid transitions."""
        allowed = _VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from {self.status.value} to {new_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        self.status = new_status
        self.updated_at = _now()

    def express(self) -> None:
        self.transition_to(NeedStatus.EXPRESSED)

    def acknowledge(self) -> None:
        self.transition_to(NeedStatus.ACKNOWLEDGED)

    def address(self, decision_ref: str | None = None) -> None:
        self.transition_to(NeedStatus.ADDRESSED)
        if decision_ref:
            self.decision_ref = decision_ref

    def withdraw(self) -> None:
        self.transition_to(NeedStatus.WITHDRAWN)


# ---------------------------------------------------------------------------
# NeedRelation — directed relationship between needs
# ---------------------------------------------------------------------------

@dataclass
class NeedRelation:
    """Directed relationship between two needs."""
    id: str
    source_id: str
    target_id: str
    type: NeedRelationType
    description: str = ""
    created_at: str = field(default_factory=_now)


# ---------------------------------------------------------------------------
# NeedCatalog — aggregate root
# ---------------------------------------------------------------------------

@dataclass
class NeedCatalog:
    """Aggregate root containing stakeholders, needs, and relations.

    All mutations go through catalog methods to maintain consistency.
    """
    name: str
    description: str = ""
    stakeholders: list[Stakeholder] = field(default_factory=list)
    needs: list[Need] = field(default_factory=list)
    relations: list[NeedRelation] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: _generate_id("catalog"))

    # -- Stakeholder management --

    def add_stakeholder(self, name: str, role: str, context: str = "") -> Stakeholder:
        """Register a stakeholder in this catalog."""
        sh = Stakeholder(id=_generate_id("sh"), name=name, role=role, context=context)
        self.stakeholders.append(sh)
        self.updated_at = _now()
        return sh

    def get_stakeholder(self, stakeholder_id: str) -> Stakeholder | None:
        return next((s for s in self.stakeholders if s.id == stakeholder_id), None)

    # -- Need expression --

    def express_need(
        self,
        stakeholder_id: str,
        action: str,
        subject: str,
        target: str | None = None,
        justifications: list[dict[str, str]] | None = None,
        priority: NeedPriority = NeedPriority.MEDIUM,
        kernel_refs: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> Need:
        """Express a new need from a stakeholder.

        Args:
            stakeholder_id: ID of a registered stakeholder.
            action: What the stakeholder wants to do.
            subject: What the action applies to.
            target: Optional destination / goal object.
            justifications: List of dicts with 'type' and 'description' keys.
            priority: Urgency level.
            kernel_refs: ea-kernel entity IDs related to this need.
            tags: Free-form labels.

        Returns:
            The newly created Need (status=DRAFT).
        """
        if not self.get_stakeholder(stakeholder_id):
            raise ValueError(f"Stakeholder {stakeholder_id} not found in catalog")

        justs = []
        for j in (justifications or []):
            justs.append(Justification(
                type=JustificationType(j["type"]),
                description=j["description"],
            ))

        statement = NeedStatement(
            stakeholder_id=stakeholder_id,
            desire=Desire(action=action, subject=subject, target=target),
            justifications=justs,
            kernel_refs=kernel_refs or [],
            tags=tags or [],
        )

        need = Need(
            id=_generate_id("need"),
            statement=statement,
            priority=priority,
        )
        self.needs.append(need)
        self.updated_at = _now()
        return need

    # -- Relations --

    def relate_needs(
        self,
        source_id: str,
        target_id: str,
        relation_type: NeedRelationType,
        description: str = "",
    ) -> NeedRelation:
        """Create a directed relationship between two needs."""
        if not self.get_need(source_id):
            raise ValueError(f"Source need {source_id} not found")
        if not self.get_need(target_id):
            raise ValueError(f"Target need {target_id} not found")

        rel = NeedRelation(
            id=_generate_id("rel"),
            source_id=source_id,
            target_id=target_id,
            type=relation_type,
            description=description,
        )
        self.relations.append(rel)
        self.updated_at = _now()
        return rel

    # -- Queries --

    def get_need(self, need_id: str) -> Need | None:
        return next((n for n in self.needs if n.id == need_id), None)

    def needs_by_stakeholder(self, stakeholder_id: str) -> list[Need]:
        return [n for n in self.needs if n.statement.stakeholder_id == stakeholder_id]

    def needs_by_status(self, status: NeedStatus) -> list[Need]:
        return [n for n in self.needs if n.status == status]

    def needs_by_priority(self, priority: NeedPriority) -> list[Need]:
        return [n for n in self.needs if n.priority == priority]

    def get_relations_for(self, need_id: str) -> list[NeedRelation]:
        return [r for r in self.relations if r.source_id == need_id or r.target_id == need_id]

    def get_timeline(self) -> list[dict[str, Any]]:
        """Return chronological events across all needs."""
        events: list[dict[str, Any]] = []
        for n in self.needs:
            events.append({
                "type": "need_created",
                "date": n.created_at,
                "need_id": n.id,
                "status": n.status.value,
                "action": n.statement.desire.action,
                "subject": n.statement.desire.subject,
            })
        for r in self.relations:
            events.append({
                "type": "relation_created",
                "date": r.created_at,
                "relation_id": r.id,
                "source_id": r.source_id,
                "target_id": r.target_id,
                "relation_type": r.type.value,
            })
        return sorted(events, key=lambda x: x["date"])

    # -- Serialization --

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "stakeholders": [
                {"id": s.id, "name": s.name, "role": s.role, "context": s.context}
                for s in self.stakeholders
            ],
            "needs": [
                {
                    "id": n.id,
                    "status": n.status.value,
                    "priority": n.priority.value,
                    "decision_ref": n.decision_ref,
                    "created_at": n.created_at,
                    "updated_at": n.updated_at,
                    "statement": {
                        "stakeholder_id": n.statement.stakeholder_id,
                        "desire": {
                            "action": n.statement.desire.action,
                            "subject": n.statement.desire.subject,
                            "target": n.statement.desire.target,
                        },
                        "justifications": [
                            {"type": j.type.value, "description": j.description}
                            for j in n.statement.justifications
                        ],
                        "kernel_refs": list(n.statement.kernel_refs),
                        "tags": list(n.statement.tags),
                        "expressed_at": n.statement.expressed_at,
                    },
                }
                for n in self.needs
            ],
            "relations": [
                {
                    "id": r.id,
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "type": r.type.value,
                    "description": r.description,
                    "created_at": r.created_at,
                }
                for r in self.relations
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> NeedCatalog:
        """Deserialize from JSON string."""
        data = json.loads(json_str)

        catalog = cls(
            name=data["name"],
            description=data.get("description", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            id=data.get("id", _generate_id("catalog")),
        )

        # Hydrate stakeholders
        for s_data in data.get("stakeholders", []):
            catalog.stakeholders.append(Stakeholder(**s_data))

        # Hydrate needs
        for n_data in data.get("needs", []):
            stmt_data = n_data["statement"]
            desire = Desire(
                action=stmt_data["desire"]["action"],
                subject=stmt_data["desire"]["subject"],
                target=stmt_data["desire"].get("target"),
            )
            justifications = [
                Justification(
                    type=JustificationType(j["type"]),
                    description=j["description"],
                )
                for j in stmt_data.get("justifications", [])
            ]
            statement = NeedStatement(
                stakeholder_id=stmt_data["stakeholder_id"],
                desire=desire,
                justifications=justifications,
                kernel_refs=stmt_data.get("kernel_refs", []),
                tags=stmt_data.get("tags", []),
                expressed_at=stmt_data.get("expressed_at", ""),
            )
            need = Need(
                id=n_data["id"],
                statement=statement,
                status=NeedStatus(n_data.get("status", "draft")),
                priority=NeedPriority(n_data.get("priority", "medium")),
                decision_ref=n_data.get("decision_ref"),
                created_at=n_data.get("created_at", ""),
                updated_at=n_data.get("updated_at", ""),
            )
            catalog.needs.append(need)

        # Hydrate relations
        for r_data in data.get("relations", []):
            catalog.relations.append(NeedRelation(
                id=r_data["id"],
                source_id=r_data["source_id"],
                target_id=r_data["target_id"],
                type=NeedRelationType(r_data["type"]),
                description=r_data.get("description", ""),
                created_at=r_data.get("created_at", ""),
            ))

        return catalog
