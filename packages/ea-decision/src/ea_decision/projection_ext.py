"""Decision projection extension — enrich projection views with decision phase/gate metadata.

Implements ProjectionExtension protocol to inject:
- Decision phase classification (diverge/converge/utilize)
- Gate type annotation for Assessment/Governance nodes
- Phase transition edges and evidence justification at L4
"""

from __future__ import annotations

from typing import Any

from ea_projection.deds import GATE_NAME_PATTERNS, GATE_CATEGORIES, GateType

# Decision phase patterns: name substring → phase
_DECISION_PHASE_PATTERNS: dict[str, str] = {
    "capturecontext": "diverge",
    "capture": "diverge",
    "diverge": "diverge",
    "buildoption": "diverge",
    "research": "diverge",
    "evaluate": "converge",
    "converge": "converge",
    "finalize": "utilize",
    "execute": "utilize",
    "publish": "utilize",
    "utilize": "utilize",
    "persist": "utilize",
    "map": "utilize",
}

# Evidence name patterns for supplementary edge generation
_EVIDENCE_NAME_PATTERNS = ("Evidence", "Provenance", "Audit", "AnalysisReport")


def _classify_decision_phase(name: str, description: str) -> str | None:
    """Classify a decision element into diverge/converge/utilize phase."""
    name_lower = name.lower()
    for pattern, phase in _DECISION_PHASE_PATTERNS.items():
        if pattern in name_lower:
            return phase
    return None


def _classify_gate_type(name: str) -> GateType | None:
    """Classify a gate node by name pattern."""
    name_lower = name.lower()
    for pattern, gate_type in GATE_NAME_PATTERNS.items():
        if pattern in name_lower:
            return gate_type
    return None


class DecisionProjectionExtension:
    """ProjectionExtension implementation for the Decision layer."""

    @property
    def layer_key(self) -> str:
        return "decision"

    def enrich_nodes(
        self,
        nodes: list[dict[str, Any]],
        level: str,
        tier: str | None,
    ) -> list[dict[str, Any]]:
        """Add decision_phase and gate metadata at L3/L4."""
        if level not in ("l3", "l4"):
            return nodes
        enriched: list[dict[str, Any]] = []
        for node in nodes:
            node = dict(node)
            name = str(node.get("name", ""))
            category = str(node.get("category", ""))
            description = str(node.get("description", ""))

            # Decision phase for Assessment/Goal nodes or any step-like node
            if category in ("Assessment", "Goal", "Behavior", "Executable"):
                phase = _classify_decision_phase(name, description)
                if phase is not None:
                    node["decision_phase"] = phase

            # Gate annotation for Assessment/Governance nodes
            if category in GATE_CATEGORIES:
                gate_type = _classify_gate_type(name)
                if gate_type is not None:
                    node["decision_gate"] = True
                    node["gate_type"] = str(gate_type)

            enriched.append(node)
        return enriched

    def enrich_edges(
        self,
        edges: list[dict[str, Any]],
        nodes: list[dict[str, Any]],
        level: str,
    ) -> list[dict[str, Any]]:
        """Add phase_transition and gate_constraint metadata at L3/L4."""
        if level not in ("l3", "l4"):
            return edges

        # Build node phase/gate lookup
        node_phase: dict[str, str] = {}
        node_gate: dict[str, bool] = {}
        for node in nodes:
            name = str(node.get("name", ""))
            if "decision_phase" in node:
                node_phase[name] = node["decision_phase"]
            if node.get("decision_gate"):
                node_gate[name] = True

        enriched: list[dict[str, Any]] = []
        for edge in edges:
            edge = dict(edge)
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))
            relation = str(edge.get("relation", ""))

            # Phase transition between different phases
            src_phase = node_phase.get(source)
            tgt_phase = node_phase.get(target)
            if src_phase and tgt_phase and src_phase != tgt_phase:
                edge["phase_transition"] = f"{src_phase}->{tgt_phase}"

            # Gate constraint edges
            if relation == "constrains" and source in node_gate:
                edge["gate_constraint"] = True

            enriched.append(edge)
        return enriched

    def supplementary_edges(
        self,
        nodes: list[dict[str, Any]],
        level: str,
        tier: str | None,
    ) -> list[dict[str, Any]]:
        """Generate phase sequence and evidence justification edges at L4."""
        if level != "l4":
            return []

        edges: list[dict[str, Any]] = []

        # Collect phase nodes
        phase_nodes: dict[str, list[str]] = {"diverge": [], "converge": [], "utilize": []}
        evidence_nodes: list[str] = []
        decision_target_nodes: list[str] = []

        for node in nodes:
            name = str(node.get("name", ""))
            category = str(node.get("category", ""))
            phase = node.get("decision_phase")
            if phase in phase_nodes:
                phase_nodes[phase].append(name)
            # Evidence pattern nodes
            name_lower = name.lower()
            if category == "PassiveStructure" and any(
                pat.lower() in name_lower for pat in _EVIDENCE_NAME_PATTERNS
            ):
                evidence_nodes.append(name)
            if category in ("Assessment", "Goal"):
                decision_target_nodes.append(name)

        # Phase sequence edges: diverge → converge → utilize
        phase_order = ["diverge", "converge", "utilize"]
        for i in range(len(phase_order) - 1):
            src_phase = phase_order[i]
            tgt_phase = phase_order[i + 1]
            src_nodes = phase_nodes[src_phase]
            tgt_nodes = phase_nodes[tgt_phase]
            if src_nodes and tgt_nodes:
                edges.append({
                    "source": src_nodes[0],
                    "target": tgt_nodes[0],
                    "relation": "next",
                    "edge_origin": "supplementary",
                    "phase_transition": f"{src_phase}->{tgt_phase}",
                    "priority": 40,
                })

        # Evidence justification edges
        for ev_name in evidence_nodes:
            for dt_name in decision_target_nodes:
                edges.append({
                    "source": ev_name,
                    "target": dt_name,
                    "relation": "constrains",
                    "edge_origin": "supplementary",
                    "evidence_justification": True,
                    "priority": 40,
                })

        return edges

    def classify_tier(
        self,
        name: str,
        category: str,
        metadata: dict[str, Any] | None,
    ) -> str | None:
        """Domain-specific tier override for decision elements."""
        name_lower = name.lower()

        # PassiveStructure + evidence name → evidence tier
        if category == "PassiveStructure" and any(
            pat.lower() in name_lower for pat in _EVIDENCE_NAME_PATTERNS
        ):
            return "evidence"

        # Assessment/Goal → decision tier
        if category in ("Assessment", "Goal"):
            return "decision"

        return None
