
import pytest
import json
from ea_decision.topic import Topic
from ea_decision.repository import DecisionRepository

def test_persistence_integrity(tmp_path):
    """Ensure data survives repository reload."""
    repo1 = DecisionRepository(tmp_path)
    topic = Topic(title="Persistence Test", description="Testing reload.")
    topic.add_research("Note 1")
    repo1.save_topic(topic)
    
    # Reload from disk
    repo2 = DecisionRepository(tmp_path)
    loaded = repo2.get_topic(topic.id)
    
    assert loaded is not None
    assert loaded.id == topic.id
    assert loaded.title == "Persistence Test"
    assert len(loaded.research_notes) == 1
    assert loaded.research_notes[0].content == "Note 1"

def test_missing_topic(tmp_path):
    """Ensure None is returned for non-existent topics."""
    repo = DecisionRepository(tmp_path)
    assert repo.get_topic("non-existent-id") is None

def test_corrupted_file(tmp_path):
    """Ensure errors are raised or handled for corrupted files."""
    repo = DecisionRepository(tmp_path)
    
    # Create a corrupted JSON file
    bad_file = tmp_path / "topics" / "bad-topic.json"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_text("{ this is not json }")
    
    # Should raise JSONDecodeError
    with pytest.raises(json.JSONDecodeError):
        repo.get_topic("bad-topic")

def test_list_topics(tmp_path):
    """Ensure listing works correctly."""
    repo = DecisionRepository(tmp_path)
    
    t1 = Topic("T1", "D1")
    t2 = Topic("T2", "D2")
    
    repo.save_topic(t1)
    repo.save_topic(t2)
    
    topics = repo.list_topics()
    assert len(topics) == 2
    ids = {t.id for t in topics}
    assert t1.id in ids
    assert t2.id in ids
