from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from ea_flow.schema import SchemaSpec
from ea_flow.types import I18nString

@dataclass(frozen=True)
class ExecutionContext:
    """Context passed around during workflow execution."""
    execution_id: str
    variables: Dict[str, Any]

@dataclass(frozen=True)
class StepResultSpec:
    """Specification for the expected structure of a step's result."""
    output_schema: Optional[SchemaSpec] = None
    expected_log_patterns: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class FlowMetaStep:
    """Formal definition of a reusable logic pattern (Meta-Data for Flow)."""
    name: I18nString
    description: I18nString
    input_schema: Optional[SchemaSpec] = None
    output_schema: Optional[SchemaSpec] = None
    kernel_type_requirement: Optional[str] = None # e.g., "action" or "step" in kernel

class StepSpec(ABC):
    """Declarative definition of a single actionable step (The 'What', not the 'How')."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier for the step."""
        pass

    @property
    def meta_type(self) -> Optional[FlowMetaStep]:
        """The formal pattern definition this step conforms to."""
        return None

    @property
    @abstractmethod
    def kernel_anchor(self) -> Optional[str]:
        """Reference to the ea-kernel element this step grounds."""
        pass

    @property
    def input_schema(self) -> Optional[SchemaSpec]:
        """Declarative input schema for this step."""
        return self.meta_type.input_schema if self.meta_type else None

    @property
    def output_schema(self) -> Optional[SchemaSpec]:
        """Declarative output schema for this step."""
        return self.meta_type.output_schema if self.meta_type else None

class KernelGroundedStepSpec(StepSpec):
    """A step spec that is natively anchored to a Kernel element."""

    def __init__(self, anchor: str, meta_type: FlowMetaStep):
        self._anchor = anchor
        self._meta_type = meta_type

    @property
    def name(self) -> str:
        return f"{self._meta_type.name} on {self._anchor}"

    @property
    def kernel_anchor(self) -> str:
        return self._anchor

    @property
    def meta_type(self) -> FlowMetaStep:
        return self._meta_type

class WorkflowSpec(ABC):
    """Declarative definition of a sequence or graph of steps."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the workflow."""
        pass

    @property
    @abstractmethod
    def kernel_anchor(self) -> Optional[str]:
        """Kernel anchoring point for this behavior."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Optional[SchemaSpec]:
        """Global input schema for the workflow."""
        pass

    @property
    @abstractmethod
    def output_schema(self) -> Optional[SchemaSpec]:
        """Global output schema for the workflow."""
        pass

    @abstractmethod
    def get_steps(self) -> List[StepSpec]:
        """Return the declarative sequence of steps."""
        pass


class UseCaseSpec(WorkflowSpec):
    """
    A First-Class Citizen of the Process Layer.
    Purely declarative business process definition.
    """
    def __init__(
        self,
        name: I18nString,
        description: I18nString,
        primary_actor: str,
        success_criteria: List[I18nString],
        steps: List[StepSpec],
        input_schema: Optional[SchemaSpec] = None,
        output_schema: Optional[SchemaSpec] = None,
        kernel_anchor: Optional[str] = None
    ):
        self._name = name
        self._description = description
        self._primary_actor = primary_actor
        self._success_criteria = success_criteria
        self._steps = steps
        self._input_schema = input_schema
        self._output_schema = output_schema
        self._kernel_anchor = kernel_anchor

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def primary_actor(self) -> str:
        return self._primary_actor

    @property
    def success_criteria(self) -> List[I18nString]:
        return self._success_criteria

    @property
    def kernel_anchor(self) -> Optional[str]:
        return self._kernel_anchor

    @property
    def input_schema(self) -> Optional[SchemaSpec]:
        return self._input_schema

    @property
    def output_schema(self) -> Optional[SchemaSpec]:
        return self._output_schema

    def get_steps(self) -> List[StepSpec]:
        return self._steps

@dataclass(frozen=True)
class FlowGenerationRule:
    """
    A specific rule for generating a Flow specification from a Kernel entity.
    Encapsulates specific logic conditions, keeping the Kernel entity pure.
    """
    source_kernel_type: str # e.g., "Entity", "Relation"
    target_flow_type: str   # e.g., "ReviewFlow", "ApprovalFlow"
    naming_pattern: str     # e.g., "{target_flow_type} for {source_name}"
    required_steps: List[str] = field(default_factory=list) # List of FlowMetaStep names

    # Logic Encapsulation: "When does this flow apply?"
    logic_conditions: Dict[str, Any] = field(default_factory=dict) # e.g., {"amount": {">=": 100000}}

@dataclass(frozen=True)
class FlowTopology:
    """
    Describes the declarative structure of a process.
    Can act as a concrete instance or a generative template.
    """
    name: str
    steps: List[StepSpec] = field(default_factory=list)
    entry_point: Optional[str] = None
    exit_points: List[str] = field(default_factory=list)
    transition_rules: Dict[str, str] = field(default_factory=dict) # step_name -> next_step_name

    # Meta-Modeling Support
    generation_rules: List[FlowGenerationRule] = field(default_factory=list)
