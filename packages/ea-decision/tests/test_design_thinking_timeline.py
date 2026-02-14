
from ea_decision.topic import Topic
from ea_decision.types import DecisionStatus


def test_timeline_ordering():
    """Verify events are returned in chronological order."""
    topic = Topic("Timeline Test", "Testing order")

    # Simulate time gaps
    topic.add_research("Note 1") # t0
    # topic.options[0] doesn't have created_at yet in our simple impl replacement

    topic.ask("Question 1", "User A") # t1
    q = topic.questions[0]
    q.reply("Answer 1", "User B") # t2 (now)

    timeline = topic.get_timeline()

    assert len(timeline) == 3 # Note, Question, Answer
    assert timeline[0]["type"] == "research"
    assert timeline[1]["type"] == "question"
    assert timeline[2]["type"] == "answer"

def test_revision_workflow():
    """Verify finalizing -> revising -> finalizing again."""
    topic = Topic("Rev Test", "Desc")
    topic.add_option("Opt A", "Desc A")
    topic.add_option("Opt B", "Desc B")

    # 1. First Decision
    topic.finalize_plan("Plan A", "Summary A", topic.options[0].id, "Rationale A")
    assert topic.status == "completed"
    assert topic.report.title == "Plan A"
    assert len(topic.report_history) == 0

    # 2. Re-open (Revise)
    topic.revise_report()
    assert topic.status == "active"
    assert topic.report is None
    assert len(topic.report_history) == 1
    assert topic.report_history[0].title == "Plan A"
    assert topic.report_history[0].decision.status == DecisionStatus.DEPRECATED

    # 3. New Decision
    topic.finalize_plan("Plan B", "Summary B", topic.options[1].id, "Rationale B")
    assert topic.status == "completed"
    assert topic.report.title == "Plan B"
    assert len(topic.report_history) == 1 # Old one is history

    # 4. JSON Roundtrip
    json_str = topic.to_json()
    loaded = Topic.from_json(json_str)

    assert loaded.report.title == "Plan B"
    assert len(loaded.report_history) == 1
    assert loaded.report_history[0].title == "Plan A"
