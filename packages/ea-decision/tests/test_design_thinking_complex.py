
import pytest
from ea_decision.topic import Evaluation, Topic


def test_complex_design_thinking_workflow():
    # 1. Diverge
    topic = Topic("Complex Arch", "High availability design")

    # Multiple research
    topic.add_research("Pattern A details", source="Ref A")
    topic.add_research("Pattern B details", source="Ref B")

    # Q&A Thread
    topic.ask("Is latency critical?", asked_by="dev1")
    q = topic.questions[0]
    q.reply("Yes, < 50ms", responder="architect")

    # 2. Options
    topic.add_option("Opt A", "Sync replication")
    topic.add_option("Opt B", "Async replication")

    opt_a = topic.options[0]
    opt_b = topic.options[1]

    # 3. Converge (Evaluation)
    opt_a.evaluation = Evaluation(
        pros=["Strong consistency"],
        cons=["Higher latency"],
        score=7
    )
    opt_b.evaluation = Evaluation(
        pros=["Low latency"],
        cons=["Eventual consistency"],
        score=8,
        comment="Preferred for performance"
    )

    # 4. Validation (Try to decide on non-existent option)
    with pytest.raises(ValueError):
        topic.finalize_plan("Title", "Summary", "fake-id", "Rationale")

    # 5. Finalize Plan
    report = topic.finalize_plan(
        title="HA Strategy",
        summary="Use Async Replication",
        selected_option_id=opt_b.id,
        rationale="Latency requirements dictate async."
    )

    # 6. Verify State
    assert topic.status == "completed"
    assert report.decision.selected_option_id == opt_b.id
    assert report.decision.rationale == "Latency requirements dictate async."

    # Verify Q&A persistence in memory
    assert topic.questions[0].answer == "Yes, < 50ms"
