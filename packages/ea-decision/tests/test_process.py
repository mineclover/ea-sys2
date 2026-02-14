import pytest
from ea_decision.process import DesignThinkingProcess
from ea_decision.types import ChoiceOption

class TestDesignThinkingProcess:
    
    @pytest.fixture
    def process(self):
        return DesignThinkingProcess()

    def test_full_flow(self, process):
        # 1. Intent
        intent = process.define_intent(
            description="Optimize Workflow",
            direction="efficiency"
        )
        assert intent.description == "Optimize Workflow"
        
        # 2. Diverge
        options_data = [
            {"description": "Option A", "feasibility_score": 0.9, "alignment_score": 0.8},
            {"description": "Option B", "feasibility_score": 0.6, "alignment_score": 0.95},
        ]
        options = process.diverge(intent, options_data)
        assert len(options) == 2
        
        # 3. Converge
        def selector(opts):
            # Simple selector: max alignment
            return max(opts, key=lambda x: x.alignment_score)
            
        choice = process.converge(intent, options, selector)
        assert choice.intent_id == intent.id
        assert choice.distance == pytest.approx(0.05) # 1.0 - 0.95
        
        # 4. Utilize
        result = process.utilize(choice, outcome_artifact={"rule_id": "rule-123"})
        assert result.choice_id == choice.id
        assert result.outcome_artifact["rule_id"] == "rule-123"
