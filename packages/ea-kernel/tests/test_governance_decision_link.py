from ea_decision.repository import DecisionRepository
from ea_decision.topic import Topic
from ea_kernel.governance_types import RuleAsset, RuleLifecycle, RuleLifecycleState, RuleProvenance
from ea_kernel.types import RuleCorpusEntry


def test_rule_decision_linkage(tmp_path):
    # 1. Setup ea-decision repository
    repo = DecisionRepository(tmp_path)

    # 2. Create and save a Topic (Rationale)
    topic = Topic(
        title="Experimental Rule TTL",
        description="We need to ensure all experimental rules have a Time-to-Live.",
        id="topic-123"
    )
    repo.save_topic(topic)

    # 3. Create a RuleAsset in ea-kernel linking to this Topic
    provenance = RuleProvenance(
        author="architect@company.com",
        source_type="manual",
        source_reference="governance_meeting_notes.md",
        decision_ref="topic-123",  # Link to the rationale
        created_at="2023-10-27T10:00:00Z"
    )

    # Mock entry for testing
    entry = RuleCorpusEntry(
        rule={"id": "rule-ttl", "type": "validity", "content": "..."},
        metadata={"domain": "core", "confidence": "empirical"}
    )

    asset = RuleAsset(
        entry=entry,
        provenance=provenance,
        lifecycle=RuleLifecycle(current_state=RuleLifecycleState.DRAFT)
    )

    # 4. Verification
    assert asset.provenance.decision_ref == "topic-123"

    # Verify we can retrieve the rationale using the link
    retrieved_topic = repo.get_topic(asset.provenance.decision_ref)
    assert retrieved_topic is not None
    assert retrieved_topic.description == "We need to ensure all experimental rules have a Time-to-Live."
