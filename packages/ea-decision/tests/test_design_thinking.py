
import pytest
from ea_decision.topic import Topic
from ea_decision.types import DecisionStatus
from ea_decision.repository import DecisionRepository


def test_design_thinking_lifecycle(tmp_path):
    # 1. Setup repository
    repo = DecisionRepository(tmp_path)
    
    # 2. Create a Topic (Diverge)
    topic = Topic(
        title="Frontend Data Access",
        description="We need to decide how the frontend accesses the database."
    )
    
    # 3. Add Research & Questions (Explore)
    topic.add_research("Direct access exposes credentials (CVE-2023-XYZ).", source="OWASP")
    topic.ask("Is performance a critical factor?", asked_by="dev-lead")
    
    # 4. Add Options
    topic.add_option("Direct Access", "Frontend queries DB directly.")
    topic.add_option("API Gateway", "Backend-for-Frontend pattern.")
    
    # 5. Evaluate Options (Converge)
    from ea_decision.topic import Evaluation
    topic.options[1].evaluation = Evaluation(
        pros=["Secure", "Decoupled"],
        cons=["More complex"],
        score=9,
        comment="Best for security"
    )
    
    # 6. Make Decision & Plan (Decide + Plan)
    # Find option ID
    gateway_option = topic.options[1]
    report = topic.finalize_plan(
        title="Frontend Data Access Strategy",
        summary="Adopt API Gateway to ensure security.",
        selected_option_id=gateway_option.id,
        rationale="Security is paramount."
    )
    
    # Add Modeling Actions
    report.add_action("create_rule", "rule:no-direct-db", "Deny direct DB access from Layer 4.")
    
    # 7. Persist
    repo.save_topic(topic)
    
    # 8. Verification (Reload)
    loaded_topic = repo.get_topic(topic.id)
    assert loaded_topic is not None
    assert loaded_topic.title == "Frontend Data Access"
    assert len(loaded_topic.research_notes) == 1
    assert len(loaded_topic.questions) == 1
    assert len(loaded_topic.options) == 2
    
    # Verify Report
    assert loaded_topic.report is not None
    assert loaded_topic.report.title == "Frontend Data Access Strategy"
    assert loaded_topic.report.decision.selected_option_id == gateway_option.id
    assert loaded_topic.report.decision.status == DecisionStatus.PROPOSED
    
    # Verify Modeling Plan
    assert len(loaded_topic.report.modeling_actions) == 1
    assert loaded_topic.report.modeling_actions[0].action_type == "create_rule"
    assert loaded_topic.status == "completed"
