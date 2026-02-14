

from ea_kernel.graph_view import TopologyGraph


class DiagramExporter:
    """Exports TopologyGraph to visual diagrams (Mermaid)."""

    def __init__(self, graph: TopologyGraph):
        self.graph = graph


    def generate_mermaid(self, show_judgment: bool = True) -> str:
        """Generate Mermaid.js diagram source code."""
        lines = ["graph LR"]

        # Metadata
        meta = self.graph.metadata
        info_label = (
            f"<b>{meta['domain'].title()} Topology</b><br/>"
            f"Version: {meta['version']}<br/>"
            f"Entities: {meta['entities']}, Edges: {meta['edges']}<br/>"
            f"Generated: {meta['generated_at']}"
        )

        lines.append("    subgraph Metadata")
        lines.append("        direction TB")
        lines.append(f"        Info[\"{info_label}\"]")
        lines.append("        style Info fill:#fff,stroke:#333,stroke-dasharray: 5 5")
        lines.append("    end")

        # Styles
        lines.append("    %% Nodes")
        lines.append("    classDef detailed fill:#f9f,stroke:#333,stroke-width:2px;")

        # Nodes
        for entity_name in self.graph.entities:
            # Try to fetch display_name and description for labeling
            entity_meta = self.graph._schema.get_entity(entity_name)

            # Default label is the ID
            display_str = entity_name
            desc_str = ""

            if entity_meta:
                # 1. Determine Display Name
                dname = entity_meta.display_name
                if isinstance(dname, dict):
                    display_str = dname.get("ko") or dname.get("en") or list(dname.values())[0]
                elif dname:
                    display_str = dname

                # 2. Determine Description
                desc = entity_meta.description
                if isinstance(desc, dict):
                    desc_str = desc.get("ko") or desc.get("en") or list(desc.values())[0]
                else:
                    desc_str = desc

            label = f"<b>{display_str}</b>"
            if desc_str:
                label += f"<br/>{desc_str}"

            lines.append(f"    {entity_name}[\"{label}\"]")

        # Edges
        lines.append("    %% Edges")
        added_edges = set()

        for source in self.graph.entities:
            edges = self.graph.outgoing(source)
            for edge in edges:
                key = (source, edge.target, edge.relation)
                if key in added_edges:
                    continue
                added_edges.add(key)

                # Determine arrow type based on judgment
                arrow = "-->" # Default solid
                if show_judgment and edge.judgment:
                    arrow = "-.->" if not edge.judgment.verdict else "-->"

                # Syntax: Source -->|Label| Target
                line = f"    {source} {arrow}|{edge.relation}| {edge.target}"
                lines.append(line)

        return "\n".join(lines)
