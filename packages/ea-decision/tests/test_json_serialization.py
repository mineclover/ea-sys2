
from ea_decision.topic import Evaluation, Topic


def test_topic_serialization_roundtrip():
    # Create valid complex object
    topic = Topic("T", "D")
    topic.add_research("R1")
    topic.ask("Q1", "U1")
    topic.add_option("O1", "Desc1")

    # Nested evaluation
    topic.options[0].evaluation = Evaluation(["P1"], ["C1"], 5, "Comment")

    # Finalize
    report = topic.finalize_plan("RepTitle", "RepSum", topic.options[0].id, "Rationale")
    report.add_action("create", "target", "desc")

    # Serialize
    json_str = topic.to_json()

    # Deserialize
    loaded = Topic.from_json(json_str)

    # structural equality
    assert loaded.title == topic.title
    assert len(loaded.research_notes) == 1
    assert len(loaded.questions) == 1
    assert len(loaded.options) == 1
    assert loaded.options[0].evaluation.score == 5
    assert loaded.report.title == "RepTitle"
    assert len(loaded.report.modeling_actions) == 1

def test_serialization_empty_fields():
    """Ensure optional fields handle None/Empty correctly."""
    topic = Topic("T", "D")
    # minimal state

    json_str = topic.to_json()
    loaded = Topic.from_json(json_str)

    assert loaded.title == "T"
    assert loaded.report is None
    assert loaded.options == []
    assert loaded.research_notes == []

def test_date_format():
    """Ensure dates are ISO strings."""
    topic = Topic("T", "D")
    assert "T" in topic.created_at # simple check for ISO format like 2026-02-11T...
    assert topic.created_at.endswith("Z")
