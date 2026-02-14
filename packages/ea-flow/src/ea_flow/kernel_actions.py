from typing import Any, Dict, Optional
from ea_flow.spec import StepSpec
from ea_flow.schema import SchemaSpec

class AddRuleStepSpec(StepSpec):
    """Declarative spec for adding a new rule."""
    
    def __init__(self, action_id: str, rule_asset_data: Dict[str, Any], anchor: str = None):
        self._action_id = action_id
        self._data = rule_asset_data
        self._anchor = anchor

    @property
    def name(self) -> str:
        return f"add_rule:{self._action_id}"

    @property
    def kernel_anchor(self) -> str:
        return self._anchor or "ea:kernel:rule_creation"

    @property
    def rule_data(self) -> Dict[str, Any]:
        return self._data

class DeprecateRuleStepSpec(StepSpec):
    """Declarative spec for deprecating a rule."""
    
    def __init__(self, rule_id: str, anchor: str = None):
        self._rule_id = rule_id
        self._anchor = anchor

    @property
    def name(self) -> str:
        return f"deprecate_rule:{self._rule_id}"

    @property
    def kernel_anchor(self) -> str:
        return self._anchor or f"ea:kernel:rule:{self._rule_id}"

    @property
    def rule_id(self) -> str:
        return self._rule_id
