"""Flow projection extension — enrich projection views with pipeline/plane metadata.

Implements ProjectionExtension protocol to inject:
- 3-plane classification (P1 Spec / P2 Coordination / P3 Realization)
- 8-step pipeline ordering
- DataFlowEdge supplementary edges at L4
"""

from __future__ import annotations

from typing import Any

# 8-step pipeline: canonical execution order
_PIPELINE_STEPS: dict[str, int] = {
    "ContextIngestStep": 1,
    "NormalizeNeedStep": 2,
    "BuildKernelInputStep": 3,
    "MapKernelSpecStep": 4,
    "ExecuteKernelAction": 5,
    "VerifyOutcomeStep": 6,
    "PersistFlowStateStep": 7,
    "PublishFlowOutcomeAction": 8,
}

# Plane classification by category/description pattern
_P1_CATEGORIES = frozenset({"Composite"})
_P1_DESCRIPTION_HINT = "P1"
_P2_DESCRIPTION_HINT = "P2"
_P3_DESCRIPTION_HINT = "P3"

# Data-related categories for tier classification
_DATA_CATEGORIES = frozenset({"PassiveStructure"})
_DECISION_NAME_PATTERNS = ("Decision",)
_EVIDENCE_NAME_PATTERNS = ("AnalysisReport", "Evidence", "Provenance", "Audit")


def _classify_plane(name: str, category: str, description: str) -> str | None:
    """Classify a flow element into P1/P2/P3 plane."""
    desc_lower = description.lower()
    if _P1_DESCRIPTION_HINT.lower() in desc_lower:
        return "P1"
    if _P2_DESCRIPTION_HINT.lower() in desc_lower:
        return "P2"
    if _P3_DESCRIPTION_HINT.lower() in desc_lower:
        return "P3"
    return None


class FlowProjectionExtension:
    """ProjectionExtension implementation for the Flow layer."""

    @property
    def layer_key(self) -> str:
        return "flow"

    def enrich_nodes(
        self,
        nodes: list[dict[str, Any]],
        level: str,
        tier: str | None,
    ) -> list[dict[str, Any]]:
        """Add pipeline order, plane, and step_category metadata at L3/L4."""
        if level not in ("l3", "l4"):
            return nodes
        enriched: list[dict[str, Any]] = []
        for node in nodes:
            node = dict(node)
            name = str(node.get("name", ""))
            category = str(node.get("category", ""))
            description = str(node.get("description", ""))

            pipeline_order = _PIPELINE_STEPS.get(name)
            if pipeline_order is not None:
                node["pipeline_order"] = pipeline_order
                node["step_category"] = "pipeline"

            plane = _classify_plane(name, category, description)
            if plane is not None:
                node["plane"] = plane

            enriched.append(node)
        return enriched

    def enrich_edges(
        self,
        edges: list[dict[str, Any]],
        nodes: list[dict[str, Any]],
        level: str,
    ) -> list[dict[str, Any]]:
        """Add pipeline_order to 'next' edges at L3, data_schema ref at L4."""
        if level not in ("l3", "l4"):
            return edges

        node_pipeline: dict[str, int] = {}
        for node in nodes:
            name = str(node.get("name", ""))
            order = _PIPELINE_STEPS.get(name)
            if order is not None:
                node_pipeline[name] = order

        enriched: list[dict[str, Any]] = []
        for edge in edges:
            edge = dict(edge)
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))
            relation = str(edge.get("relation", ""))

            if relation == "next" and source in node_pipeline and target in node_pipeline:
                edge["pipeline_order"] = (node_pipeline[source], node_pipeline[target])

            if level == "l4" and relation in ("produces", "consumes"):
                edge["data_schema"] = f"{source}:{relation}:{target}"

            enriched.append(edge)
        return enriched

    def supplementary_edges(
        self,
        nodes: list[dict[str, Any]],
        level: str,
        tier: str | None,
    ) -> list[dict[str, Any]]:
        """Generate implicit data flow edges from pipeline step ordering."""
        if level != "l4":
            return []

        pipeline_nodes: list[tuple[str, int]] = []
        for node in nodes:
            name = str(node.get("name", ""))
            order = _PIPELINE_STEPS.get(name)
            if order is not None:
                pipeline_nodes.append((name, order))

        pipeline_nodes.sort(key=lambda x: x[1])
        edges: list[dict[str, Any]] = []
        for i in range(len(pipeline_nodes) - 1):
            src_name, src_order = pipeline_nodes[i]
            tgt_name, tgt_order = pipeline_nodes[i + 1]
            edges.append({
                "source": src_name,
                "target": tgt_name,
                "relation": "next",
                "edge_origin": "supplementary",
                "pipeline_order": (src_order, tgt_order),
                "priority": 40,
            })
        return edges

    def classify_tier(
        self,
        name: str,
        category: str,
        metadata: dict[str, Any] | None,
    ) -> str | None:
        """Domain-specific tier override for flow elements."""
        name_lower = name.lower()
        description = str((metadata or {}).get("description", ""))

        # P1 Spec elements → function tier
        if _P1_DESCRIPTION_HINT.lower() in description.lower() and category in _P1_CATEGORIES:
            return "function"

        # Data-related elements in P2
        if category in _DATA_CATEGORIES:
            # Check evidence patterns first
            if any(pat.lower() in name_lower for pat in _EVIDENCE_NAME_PATTERNS):
                return "evidence"
            return "data"

        # Decision-related names
        if any(pat.lower() in name_lower for pat in _DECISION_NAME_PATTERNS):
            return "decision"

        return None
