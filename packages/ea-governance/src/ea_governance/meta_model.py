from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from ea_decision.types import DecisionTopic, DecisionType, ActivationStatus, EvidenceReference
from ea_flow.topology import ProcessSpec, StepDefinition, FlowStepCategory, SchemaDefinition, StepSchemaUsage
from ea_flow.spec import FlowTopology

@dataclass
class GenerationSuggestion:
    """A suggestion for how to concretize an intent into Ontology artifacts."""
    suggested_decision: Optional[DecisionTopic] = None
    suggested_kernel_actions: List[str] = field(default_factory=list)
    suggested_flow_spec: Optional[ProcessSpec] = None
    suggested_flow_topology: Optional[str] = None

class MetaGenerator:
    """
    The Engine of the Concretization Chain.
    Takes abstract Intent -> Suggests Concrete Ontology Instances.
    """
    def __init__(self):
        self._flow_topologies: List[FlowTopology] = []

    def register_flow_topology(self, topology: FlowTopology):
        """Register a FlowTopology for intent-based matching."""
        self._flow_topologies.append(topology)

    def suggest_from_intent(self, intent_text: str, context: str = "general") -> GenerationSuggestion:
        """
        Analyzes the intent and context to suggest the best Ontology structures.
        """
        
        # 1. Decision Ontology Suggestion
        intent_lower = intent_text.lower()
        decision_type = DecisionType.STRATEGIC_DIRECTION
        
        if "trade-off" in intent_lower or "vs" in intent_lower:
            decision_type = DecisionType.TRADE_OFF_RESOLUTION
        elif "compliance" in intent_lower or "regulatory" in intent_lower:
            decision_type = DecisionType.COMPLIANCE_CHECK
        elif "architecture" in intent_lower or "refactor" in intent_lower:
            decision_type = DecisionType.ARCHITECTURE_SELECTION

        suggested_decision = DecisionTopic(
            id="generated-decision-id", # Placeholder
            title=f"Decision for: {intent_text[:50]}...",
            description=intent_text,
            decision_type=decision_type,
            status=ActivationStatus.DRAFT,
            decision_date=datetime.now(),
            supporting_evidence=[
                EvidenceReference(
                    resource_uri="file:///docs/architecture_guidelines.md",
                    description="Standard Architecture Guidelines"
                )
            ]
        )

        # 2. Flow Ontology Suggestion (Heuristic)
        suggested_flow = None
        if "process" in intent_lower or "flow" in intent_lower:
            
            # Define a placeholder schema if process involves data
            schemas = []
            if "payment" in intent_lower or "data" in intent_lower:
                schemas.append(SchemaDefinition(
                    id="schema-payment-data",
                    name="PaymentData",
                    definition={"type": "object", "properties": {"amount": {"type": "number"}}}
                ))
            
            suggested_flow = ProcessSpec(
                id="generated-flow-id",
                name=f"Flow for: {intent_text[:30]}",
                version="1.0.0",
                defined_schemas=schemas,
                steps=[
                    StepDefinition(
                        id="step-1",
                        name="Start",
                        category=FlowStepCategory.EVENT,
                        description="Process Trigger",
                        # Example usage of schema if available
                        schema_usage=StepSchemaUsage(output_schema_id=schemas[0].id) if schemas else None
                    )
                ]
            )

        # 3. Kernel Actions (Pure Structure)
        suggested_kernel_actions = []
        if decision_type == DecisionType.COMPLIANCE_CHECK:
            suggested_kernel_actions.append("Define RuleAsset for Compliance")
        if suggested_flow:
            suggested_kernel_actions.append("Define Process Entity")

        # 4. Match registered Flow Topologies
        matched_topology_name: Optional[str] = None
        for topology in self._flow_topologies:
            for rule in topology.generation_rules:
                if rule.target_flow_type.lower() in intent_lower:
                    matched_topology_name = topology.name
                    suggested_kernel_actions.insert(
                        0,
                        f"Define {rule.source_kernel_type} for {rule.target_flow_type}"
                    )
                    break
            if matched_topology_name:
                break

        return GenerationSuggestion(
            suggested_decision=suggested_decision,
            suggested_kernel_actions=suggested_kernel_actions,
            suggested_flow_spec=suggested_flow,
            suggested_flow_topology=matched_topology_name,
        )
