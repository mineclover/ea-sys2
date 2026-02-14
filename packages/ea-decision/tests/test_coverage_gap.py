import pytest
from ea_decision.topic import Topic, DesignDecision, DesignReport, ModelingAction
from ea_decision.types import DecisionStatus

def test_decision_approval():
    decision = DesignDecision(
        selected_option_id="OPT1",
        rationale="Because",
        complexity="LOW"
    )
    assert decision.status == DecisionStatus.PROPOSED
    assert decision.approver is None
    
    decision.approve(approver="Boss")
    assert decision.status == DecisionStatus.ACCEPTED
    assert decision.approver == "Boss"
    assert decision.approved_at is not None

def test_topic_from_dict_with_history():
    data = {
        "id": "T1",
        "title": "Title",
        "description": "Description",
        "author": "Author",
        "status": "OPEN",
        "report_history": [
            {
                "title": "Old Report",
                "decision": {
                    "selected_option_id": "OPT1",
                    "rationale": "Old rational",
                    "complexity": "TRIVIAL"
                },
                "modeling_actions": [
                    {"action_type": "ADD", "target": "P1", "description": "Action Desc"}
                ],
                "summary": "Old summary"
            }
        ]
    }
    
    import json
    topic = Topic.from_json(json.dumps(data))
    assert len(topic.report_history) == 1
    assert topic.report_history[0].decision.selected_option_id == "OPT1"
    assert len(topic.report_history[0].modeling_actions) == 1
    assert topic.report_history[0].modeling_actions[0].target == "P1"
