"""NeedCatalog aggregate root (N2).

Mutable container managing use-cases, stakeholders, needs, and process-model units.
Need wraps immutable NeedStatement with mutable status/priority/version lifecycle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ea_needs.types import (
    Desire,
    Justification,
    JustificationType,
    NeedCauseType,
    NeedPriority,
    NeedPurpose,
    NeedKernelChangePhase,
    NeedProcessStage,
    NeedProcessUnit,
    NeedRelationType,
    NeedResolutionComplexity,
    NeedStatement,
    NeedStatus,
    Stakeholder,
    UseCase,
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

_UNSET = object()


# ---------------------------------------------------------------------------
# Internal normalizers
# ---------------------------------------------------------------------------

def _normalize_cause_types(values: list[NeedCauseType | str] | None) -> list[NeedCauseType]:
    if not values:
        return []
    normalized: list[NeedCauseType] = []
    for value in values:
        if isinstance(value, NeedCauseType):
            normalized.append(value)
        else:
            normalized.append(NeedCauseType(value))
    return normalized


def _normalize_complexity(
    value: NeedResolutionComplexity | str | None,
) -> NeedResolutionComplexity:
    if value is None:
        return NeedResolutionComplexity.PROCEDURAL
    if isinstance(value, NeedResolutionComplexity):
        return value
    return NeedResolutionComplexity(value)


def _normalize_kernel_change_phase(
    value: NeedKernelChangePhase | str | None,
) -> NeedKernelChangePhase:
    if value is None:
        return NeedKernelChangePhase.PLANNED
    if isinstance(value, NeedKernelChangePhase):
        return value
    return NeedKernelChangePhase(value)


def _default_change_phase_for_status(status: NeedStatus) -> NeedKernelChangePhase:
    if status == NeedStatus.ADDRESSED:
        return NeedKernelChangePhase.APPLIED
    if status == NeedStatus.WITHDRAWN:
        return NeedKernelChangePhase.SUPERSEDED
    return NeedKernelChangePhase.PLANNED


def _normalize_priority(value: NeedPriority | str | None) -> NeedPriority:
    if value is None:
        return NeedPriority.MEDIUM
    if isinstance(value, NeedPriority):
        return value

    raw = value.strip()
    if not raw:
        return NeedPriority.MEDIUM

    token = raw.lower().replace("-", "_").replace(" ", "_")
    if token.startswith("need_priority_"):
        token = token[len("need_priority_"):]
    elif token.startswith("needpriority"):
        token = token[len("needpriority"):].lstrip("_")

    try:
        return NeedPriority(token)
    except ValueError as err:
        allowed = ", ".join(item.value for item in NeedPriority)
        raise ValueError(
            f"Invalid priority '{value}'. Allowed priority values: {allowed}"
        ) from err


def _normalize_purpose(
    value: NeedPurpose | str | None,
    *,
    allow_legacy_unknown: bool = False,
) -> NeedPurpose:
    if value is None:
        return NeedPurpose.UNSPECIFIED
    if isinstance(value, NeedPurpose):
        return value

    raw = value.strip()
    if not raw:
        return NeedPurpose.UNSPECIFIED

    token = raw.lower().replace("-", "_").replace(" ", "_")
    if token.startswith("need_purpose_"):
        token = token[len("need_purpose_"):]
    elif token.startswith("needpurpose"):
        token = token[len("needpurpose"):].lstrip("_")

    try:
        return NeedPurpose(token)
    except ValueError as err:
        if allow_legacy_unknown:
            return NeedPurpose.UNSPECIFIED
        allowed = ", ".join(item.value for item in NeedPurpose)
        raise ValueError(
            f"Invalid purpose '{value}'. Allowed purpose values: {allowed}"
        ) from err


def _normalize_stage(value: NeedProcessStage | str) -> NeedProcessStage:
    if isinstance(value, NeedProcessStage):
        return value
    return NeedProcessStage(value)


def _build_justifications(justifications: list[dict[str, str]] | None) -> list[Justification]:
    result: list[Justification] = []
    for payload in justifications or []:
        result.append(
            Justification(
                type=JustificationType(payload["type"]),
                description=payload["description"],
            )
        )
    return result


# ---------------------------------------------------------------------------
# Need — mutable wrapper around frozen NeedStatement
# ---------------------------------------------------------------------------

@dataclass
class Need:
    """Mutable lifecycle wrapper around an immutable NeedStatement.

    The statement itself (stakeholder_id, desire, justifications) never changes.
    Status, priority, decision link/evidence, and timestamps are mutable.
    """

    id: str
    statement: NeedStatement
    status: NeedStatus = NeedStatus.DRAFT
    priority: NeedPriority = NeedPriority.MEDIUM
    kernel_change_phase: NeedKernelChangePhase = NeedKernelChangePhase.PLANNED
    decision_ref: str | None = None  # link to ea-decision topic/report id
    decision_evidence_refs: list[str] = field(default_factory=list)
    inherited_from_decisions: list[str] = field(default_factory=list)
    use_case_id: str | None = None
    lineage_id: str = ""
    version: int = 1
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.lineage_id:
            self.lineage_id = self.id

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
        self.kernel_change_phase = NeedKernelChangePhase.PLANNED
        self.updated_at = _now()

    def acknowledge(self) -> None:
        self.transition_to(NeedStatus.ACKNOWLEDGED)
        self.kernel_change_phase = NeedKernelChangePhase.PLANNED
        self.updated_at = _now()

    def address(self, decision_ref: str | None = None) -> None:
        self.transition_to(NeedStatus.ADDRESSED)
        self.kernel_change_phase = NeedKernelChangePhase.APPLIED
        if decision_ref:
            self.decision_ref = decision_ref

    def withdraw(self) -> None:
        self.transition_to(NeedStatus.WITHDRAWN)
        self.kernel_change_phase = NeedKernelChangePhase.SUPERSEDED

    def set_kernel_change_phase(self, phase: NeedKernelChangePhase | str) -> None:
        self.kernel_change_phase = _normalize_kernel_change_phase(phase)
        self.updated_at = _now()

    def inherit_decision_evidence(self, decision_id: str, refs: list[str]) -> None:
        """Merge decision evidence references into this need."""
        for ref in refs:
            if ref not in self.decision_evidence_refs:
                self.decision_evidence_refs.append(ref)
        if decision_id and decision_id not in self.inherited_from_decisions:
            self.inherited_from_decisions.append(decision_id)
        self.updated_at = _now()


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
    """Aggregate root containing use-cases, stakeholders, needs, and relations.

    All mutations go through catalog methods to maintain consistency.
    """

    name: str
    description: str = ""
    use_cases: list[UseCase] = field(default_factory=list)
    stakeholders: list[Stakeholder] = field(default_factory=list)
    needs: list[Need] = field(default_factory=list)
    relations: list[NeedRelation] = field(default_factory=list)
    process_units: list[NeedProcessUnit] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: _generate_id("catalog"))

    # -- Use-case modeling --

    def add_use_case(
        self,
        title: str,
        actor: str,
        situation: str,
        purpose: str,
        outcome: str = "",
        tags: list[str] | None = None,
    ) -> UseCase:
        """Register a structured use-case for downstream need expression."""
        use_case = UseCase(
            id=_generate_id("uc"),
            title=title,
            actor=actor,
            situation=situation,
            purpose=purpose,
            outcome=outcome,
            tags=list(tags or []),
        )
        self.use_cases.append(use_case)
        self.updated_at = _now()
        return use_case

    def get_use_case(self, use_case_id: str) -> UseCase | None:
        return next((u for u in self.use_cases if u.id == use_case_id), None)

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
        priority: NeedPriority | str = NeedPriority.MEDIUM,
        kernel_refs: list[str] | None = None,
        tags: list[str] | None = None,
        use_case_id: str | None = None,
        cause_types: list[NeedCauseType | str] | None = None,
        purpose: NeedPurpose | str | None = NeedPurpose.UNSPECIFIED,
        complexity: NeedResolutionComplexity | str = NeedResolutionComplexity.PROCEDURAL,
        kernel_change_phase: NeedKernelChangePhase | str | None = None,
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
            use_case_id: Optional use-case linkage.
            cause_types: Need-generating cause domains.
            purpose: Intended objective from this need.
            complexity: Expected resolution complexity.

        Returns:
            The newly created Need (status=DRAFT, version=1).
        """
        if not self.get_stakeholder(stakeholder_id):
            raise ValueError(f"Stakeholder {stakeholder_id} not found in catalog")
        if use_case_id and not self.get_use_case(use_case_id):
            raise ValueError(f"Use-case {use_case_id} not found in catalog")

        statement = NeedStatement(
            stakeholder_id=stakeholder_id,
            desire=Desire(action=action, subject=subject, target=target),
            justifications=_build_justifications(justifications),
            kernel_refs=list(kernel_refs or []),
            tags=list(tags or []),
            use_case_id=use_case_id,
            purpose=_normalize_purpose(purpose),
            cause_types=_normalize_cause_types(cause_types),
            complexity=_normalize_complexity(complexity),
        )

        need = Need(
            id=_generate_id("need"),
            statement=statement,
            priority=_normalize_priority(priority),
            kernel_change_phase=_normalize_kernel_change_phase(kernel_change_phase),
            use_case_id=use_case_id,
            lineage_id="",
            version=1,
        )
        self.needs.append(need)
        self.updated_at = _now()
        return need

    def revise_need(
        self,
        need_id: str,
        *,
        action: str | None = None,
        subject: str | None = None,
        target: str | None | object = _UNSET,
        justifications: list[dict[str, str]] | None | object = _UNSET,
        priority: NeedPriority | str | None = None,
        kernel_refs: list[str] | None | object = _UNSET,
        tags: list[str] | None | object = _UNSET,
        use_case_id: str | None | object = _UNSET,
        cause_types: list[NeedCauseType | str] | None | object = _UNSET,
        purpose: NeedPurpose | str | None | object = _UNSET,
        complexity: NeedResolutionComplexity | str | object = _UNSET,
        kernel_change_phase: NeedKernelChangePhase | str | None | object = _UNSET,
        clone_process_units: bool = True,
    ) -> Need:
        """Create a new version from an existing need lineage."""
        current = self.get_need(need_id)
        if current is None:
            raise ValueError(f"Need {need_id} not found")

        if use_case_id is not _UNSET and use_case_id is not None and not self.get_use_case(use_case_id):
            raise ValueError(f"Use-case {use_case_id} not found in catalog")

        if justifications is _UNSET:
            next_justifications = [
                {"type": j.type.value, "description": j.description}
                for j in current.statement.justifications
            ]
        else:
            next_justifications = justifications

        if kernel_refs is _UNSET:
            next_kernel_refs = list(current.statement.kernel_refs)
        else:
            next_kernel_refs = list(kernel_refs or [])

        next_tags = list(current.statement.tags) if tags is _UNSET else list(tags or [])

        if cause_types is _UNSET:
            next_cause_types: list[NeedCauseType | str] | None = list(current.statement.cause_types)
        else:
            next_cause_types = cause_types

        if purpose is _UNSET:
            next_purpose = current.statement.purpose
        elif purpose is None or isinstance(purpose, NeedPurpose | str):
            next_purpose = _normalize_purpose(purpose)
        else:
            next_purpose = _normalize_purpose(str(purpose))

        if complexity is _UNSET:
            next_complexity = current.statement.complexity
        else:
            next_complexity = _normalize_complexity(
                complexity if isinstance(complexity, NeedResolutionComplexity | str) else None
            )

        if target is _UNSET:
            next_target = current.statement.desire.target
        else:
            next_target = target if isinstance(target, str) or target is None else None

        if use_case_id is _UNSET:
            next_use_case_id = current.use_case_id
        else:
            next_use_case_id = use_case_id if isinstance(use_case_id, str) or use_case_id is None else None

        statement = NeedStatement(
            stakeholder_id=current.statement.stakeholder_id,
            desire=Desire(
                action=action if action is not None else current.statement.desire.action,
                subject=subject if subject is not None else current.statement.desire.subject,
                target=next_target,
            ),
            justifications=_build_justifications(next_justifications),
            kernel_refs=next_kernel_refs,
            tags=next_tags,
            use_case_id=next_use_case_id,
            purpose=next_purpose,
            cause_types=_normalize_cause_types(next_cause_types),
            complexity=next_complexity,
        )

        next_version = 1 + max(
            (n.version for n in self.needs if n.lineage_id == current.lineage_id),
            default=0,
        )

        revised = Need(
            id=_generate_id("need"),
            statement=statement,
            status=NeedStatus.DRAFT,
            priority=_normalize_priority(priority) if priority is not None else current.priority,
            kernel_change_phase=_normalize_kernel_change_phase(
                None if kernel_change_phase is _UNSET else kernel_change_phase
            ),
            decision_ref=current.decision_ref,
            decision_evidence_refs=list(current.decision_evidence_refs),
            inherited_from_decisions=list(current.inherited_from_decisions),
            use_case_id=next_use_case_id,
            lineage_id=current.lineage_id,
            version=next_version,
        )
        self.needs.append(revised)

        if clone_process_units:
            for unit in self.process_units_for_need(current.id):
                self.process_units.append(
                    NeedProcessUnit(
                        id=_generate_id("pu"),
                        need_id=revised.id,
                        stage=unit.stage,
                        label=unit.label,
                        description=unit.description,
                        sequence=unit.sequence,
                        metadata=dict(unit.metadata),
                    )
                )

        self.updated_at = _now()
        return revised

    def inherit_decision_evidence(
        self,
        need_id: str,
        decision_id: str,
        evidence_refs: list[str],
        kernel_change_phase: NeedKernelChangePhase | str | None = None,
    ) -> Need:
        """Inherit rationale/evidence references from a decision artifact."""
        need = self.get_need(need_id)
        if need is None:
            raise ValueError(f"Need {need_id} not found")
        need.inherit_decision_evidence(decision_id=decision_id, refs=evidence_refs)
        if kernel_change_phase is not None:
            need.set_kernel_change_phase(kernel_change_phase)
        self.updated_at = _now()
        return need

    # -- Process-unit modeling --

    def add_process_unit(
        self,
        need_id: str,
        stage: NeedProcessStage | str,
        label: str,
        description: str = "",
        sequence: int | None = None,
        metadata: dict[str, str] | None = None,
    ) -> NeedProcessUnit:
        """Attach a process-model unit to a need."""
        if not self.get_need(need_id):
            raise ValueError(f"Need {need_id} not found")

        normalized_stage = _normalize_stage(stage)
        if sequence is None:
            current = [
                u.sequence
                for u in self.process_units
                if u.need_id == need_id and u.stage == normalized_stage
            ]
            sequence = (max(current) + 1) if current else 1

        unit = NeedProcessUnit(
            id=_generate_id("pu"),
            need_id=need_id,
            stage=normalized_stage,
            label=label,
            description=description,
            sequence=sequence,
            metadata=dict(metadata or {}),
        )
        self.process_units.append(unit)
        self.updated_at = _now()
        return unit

    def process_units_for_need(
        self,
        need_id: str,
        stage: NeedProcessStage | str | None = None,
    ) -> list[NeedProcessUnit]:
        """List process units for a need, optionally filtering by stage."""
        if stage is None:
            units = [u for u in self.process_units if u.need_id == need_id]
        else:
            normalized_stage = _normalize_stage(stage)
            units = [
                u for u in self.process_units if u.need_id == need_id and u.stage == normalized_stage
            ]
        return sorted(units, key=lambda unit: (unit.stage.value, unit.sequence, unit.created_at))

    def process_units_by_stage(self, stage: NeedProcessStage | str) -> list[NeedProcessUnit]:
        normalized_stage = _normalize_stage(stage)
        units = [u for u in self.process_units if u.stage == normalized_stage]
        return sorted(units, key=lambda unit: (unit.need_id, unit.sequence, unit.created_at))

    def modeled_need_detail(self, need_id: str) -> dict[str, Any] | None:
        """Return an identified need with grouped process-model details."""
        need = self.get_need(need_id)
        if need is None:
            return None

        grouped: dict[str, list[dict[str, Any]]] = {
            NeedProcessStage.IDENTIFY.value: [],
            NeedProcessStage.QUERY.value: [],
            NeedProcessStage.MODEL_DETAIL.value: [],
        }
        for unit in self.process_units_for_need(need_id):
            grouped[unit.stage.value].append(
                {
                    "id": unit.id,
                    "label": unit.label,
                    "description": unit.description,
                    "sequence": unit.sequence,
                    "metadata": dict(unit.metadata),
                }
            )

        return {
            "need_id": need.id,
            "lineage_id": need.lineage_id,
            "version": need.version,
            "status": need.status.value,
            "priority": need.priority.value,
            "kernel_change_phase": need.kernel_change_phase.value,
            "use_case_id": need.use_case_id,
            "purpose": need.statement.purpose,
            "cause_types": [c.value for c in need.statement.cause_types],
            "complexity": need.statement.complexity.value,
            "process_units": grouped,
        }

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

    def identify_need(self, reference: str, version: int | None = None) -> Need | None:
        """Identify a need by exact id or by lineage id (+ optional version)."""
        exact = self.get_need(reference)
        if exact is not None:
            versions = self.need_versions(exact.lineage_id)
            if version is not None:
                if exact.version == version:
                    return exact
                return next((need for need in versions if need.version == version), None)
            return versions[-1] if versions else exact

        lineage = [n for n in self.needs if n.lineage_id == reference]
        if not lineage:
            return None
        if version is None:
            return max(lineage, key=lambda n: n.version)
        return next((n for n in lineage if n.version == version), None)

    def need_versions(self, lineage_id: str) -> list[Need]:
        """List all versions for a need lineage."""
        return sorted(
            [n for n in self.needs if n.lineage_id == lineage_id],
            key=lambda n: n.version,
        )

    def latest_need_version(self, lineage_id: str) -> Need | None:
        versions = self.need_versions(lineage_id)
        if not versions:
            return None
        return versions[-1]

    def needs_by_stakeholder(self, stakeholder_id: str) -> list[Need]:
        return [n for n in self.needs if n.statement.stakeholder_id == stakeholder_id]

    def needs_by_status(self, status: NeedStatus) -> list[Need]:
        return [n for n in self.needs if n.status == status]

    def needs_by_priority(self, priority: NeedPriority) -> list[Need]:
        return [n for n in self.needs if n.priority == priority]

    def needs_by_use_case(self, use_case_id: str) -> list[Need]:
        return [n for n in self.needs if n.use_case_id == use_case_id]

    def needs_by_kernel_ref(self, kernel_ref: str) -> list[Need]:
        """Find needs whose kernel_refs include the given reference."""
        return [n for n in self.needs if kernel_ref in n.statement.kernel_refs]

    def get_relations_for(self, need_id: str) -> list[NeedRelation]:
        return [r for r in self.relations if r.source_id == need_id or r.target_id == need_id]

    def get_timeline(self) -> list[dict[str, Any]]:
        """Return chronological events across use-cases, needs, relations, and process units."""
        events: list[dict[str, Any]] = []
        for use_case in self.use_cases:
            events.append(
                {
                    "type": "use_case_created",
                    "date": use_case.created_at,
                    "use_case_id": use_case.id,
                    "title": use_case.title,
                    "version": use_case.version,
                }
            )
        for need in self.needs:
            events.append(
                {
                    "type": "need_created",
                    "date": need.created_at,
                    "need_id": need.id,
                    "lineage_id": need.lineage_id,
                    "version": need.version,
                    "status": need.status.value,
                    "kernel_change_phase": need.kernel_change_phase.value,
                    "action": need.statement.desire.action,
                    "subject": need.statement.desire.subject,
                }
            )
        for relation in self.relations:
            events.append(
                {
                    "type": "relation_created",
                    "date": relation.created_at,
                    "relation_id": relation.id,
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                    "relation_type": relation.type.value,
                }
            )
        for unit in self.process_units:
            events.append(
                {
                    "type": "process_unit_modeled",
                    "date": unit.created_at,
                    "process_unit_id": unit.id,
                    "need_id": unit.need_id,
                    "stage": unit.stage.value,
                    "sequence": unit.sequence,
                    "label": unit.label,
                }
            )
        return sorted(events, key=lambda item: item["date"])

    # -- Serialization --

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "use_cases": [
                {
                    "id": use_case.id,
                    "title": use_case.title,
                    "actor": use_case.actor,
                    "situation": use_case.situation,
                    "purpose": use_case.purpose,
                    "outcome": use_case.outcome,
                    "tags": list(use_case.tags),
                    "version": use_case.version,
                    "created_at": use_case.created_at,
                    "updated_at": use_case.updated_at,
                }
                for use_case in self.use_cases
            ],
            "stakeholders": [
                {"id": s.id, "name": s.name, "role": s.role, "context": s.context}
                for s in self.stakeholders
            ],
            "needs": [
                {
                    "id": n.id,
                    "lineage_id": n.lineage_id,
                    "version": n.version,
                    "status": n.status.value,
                    "priority": n.priority.value,
                    "kernel_change_phase": n.kernel_change_phase.value,
                    "decision_ref": n.decision_ref,
                    "decision_evidence_refs": list(n.decision_evidence_refs),
                    "inherited_from_decisions": list(n.inherited_from_decisions),
                    "use_case_id": n.use_case_id,
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
                        "use_case_id": n.statement.use_case_id,
                        "purpose": n.statement.purpose,
                        "cause_types": [cause.value for cause in n.statement.cause_types],
                        "complexity": n.statement.complexity.value,
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
            "process_units": [
                {
                    "id": unit.id,
                    "need_id": unit.need_id,
                    "stage": unit.stage.value,
                    "label": unit.label,
                    "description": unit.description,
                    "sequence": unit.sequence,
                    "metadata": dict(unit.metadata),
                    "created_at": unit.created_at,
                }
                for unit in self.process_units
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

        # Hydrate use-cases
        for use_case_data in data.get("use_cases", []):
            catalog.use_cases.append(
                UseCase(
                    id=use_case_data["id"],
                    title=use_case_data["title"],
                    actor=use_case_data["actor"],
                    situation=use_case_data.get("situation", ""),
                    purpose=use_case_data.get("purpose", ""),
                    outcome=use_case_data.get("outcome", ""),
                    tags=list(use_case_data.get("tags", [])),
                    version=use_case_data.get("version", 1),
                    created_at=use_case_data.get("created_at", ""),
                    updated_at=use_case_data.get("updated_at", ""),
                )
            )

        # Hydrate stakeholders
        for stakeholder_data in data.get("stakeholders", []):
            catalog.stakeholders.append(Stakeholder(**stakeholder_data))

        # Hydrate needs
        for need_data in data.get("needs", []):
            statement_data = need_data["statement"]
            desire_data = statement_data["desire"]
            justifications = [
                Justification(
                    type=JustificationType(item["type"]),
                    description=item["description"],
                )
                for item in statement_data.get("justifications", [])
            ]
            cause_types = [
                NeedCauseType(value) for value in statement_data.get("cause_types", [])
            ]
            complexity = _normalize_complexity(statement_data.get("complexity", "procedural"))

            statement = NeedStatement(
                stakeholder_id=statement_data["stakeholder_id"],
                desire=Desire(
                    action=desire_data["action"],
                    subject=desire_data["subject"],
                    target=desire_data.get("target"),
                ),
                justifications=justifications,
                kernel_refs=list(statement_data.get("kernel_refs", [])),
                tags=list(statement_data.get("tags", [])),
                use_case_id=statement_data.get("use_case_id"),
                purpose=_normalize_purpose(
                    statement_data.get("purpose", NeedPurpose.UNSPECIFIED.value),
                    allow_legacy_unknown=True,
                ),
                cause_types=cause_types,
                complexity=complexity,
                expressed_at=statement_data.get("expressed_at", ""),
            )

            status = NeedStatus(need_data.get("status", "draft"))
            stored_phase = need_data.get("kernel_change_phase")
            if stored_phase is None:
                phase = _default_change_phase_for_status(status)
            else:
                phase = _normalize_kernel_change_phase(stored_phase)

            need = Need(
                id=need_data["id"],
                statement=statement,
                status=status,
                priority=NeedPriority(need_data.get("priority", "medium")),
                kernel_change_phase=phase,
                decision_ref=need_data.get("decision_ref"),
                decision_evidence_refs=list(need_data.get("decision_evidence_refs", [])),
                inherited_from_decisions=list(need_data.get("inherited_from_decisions", [])),
                use_case_id=need_data.get("use_case_id", statement.use_case_id),
                lineage_id=need_data.get("lineage_id", need_data["id"]),
                version=need_data.get("version", 1),
                created_at=need_data.get("created_at", ""),
                updated_at=need_data.get("updated_at", ""),
            )
            catalog.needs.append(need)

        # Hydrate relations
        for relation_data in data.get("relations", []):
            catalog.relations.append(
                NeedRelation(
                    id=relation_data["id"],
                    source_id=relation_data["source_id"],
                    target_id=relation_data["target_id"],
                    type=NeedRelationType(relation_data["type"]),
                    description=relation_data.get("description", ""),
                    created_at=relation_data.get("created_at", ""),
                )
            )

        # Hydrate process units
        for unit_data in data.get("process_units", []):
            catalog.process_units.append(
                NeedProcessUnit(
                    id=unit_data["id"],
                    need_id=unit_data["need_id"],
                    stage=NeedProcessStage(unit_data["stage"]),
                    label=unit_data["label"],
                    description=unit_data.get("description", ""),
                    sequence=unit_data.get("sequence", 0),
                    metadata=dict(unit_data.get("metadata", {})),
                    created_at=unit_data.get("created_at", ""),
                )
            )

        return catalog
