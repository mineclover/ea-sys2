"""Tests for ea_decision.repository module."""

import json

from ea_decision.repository import DecisionRepository
from ea_decision.topic import Topic


def _make_topic(title="Test Topic"):
    """Create a minimal Topic for testing."""
    t = Topic(title=title, description="Test description")
    return t


class TestDecisionRepository:
    """Test DecisionRepository file-based persistence."""

    def test_init_creates_dirs(self, tmp_path):
        repo = DecisionRepository(tmp_path / "data")
        assert (tmp_path / "data" / "topics").is_dir()

    def test_save_and_get_topic(self, tmp_path):
        repo = DecisionRepository(tmp_path / "data")
        topic = _make_topic("Save Test")

        topic_id = repo.save_topic(topic)

        assert topic_id == topic.id
        loaded = repo.get_topic(topic_id)
        assert loaded is not None
        assert loaded.title == "Save Test"
        assert loaded.id == topic.id

    def test_get_topic_not_found(self, tmp_path):
        repo = DecisionRepository(tmp_path / "data")
        assert repo.get_topic("nonexistent") is None

    def test_save_creates_json_file(self, tmp_path):
        repo = DecisionRepository(tmp_path / "data")
        topic = _make_topic()

        repo.save_topic(topic)

        file_path = tmp_path / "data" / "topics" / f"{topic.id}.json"
        assert file_path.exists()
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert data["title"] == "Test Topic"

    def test_list_topics_empty(self, tmp_path):
        repo = DecisionRepository(tmp_path / "data")
        assert repo.list_topics() == []

    def test_list_topics_multiple(self, tmp_path):
        repo = DecisionRepository(tmp_path / "data")
        t1 = _make_topic("Topic 1")
        t2 = _make_topic("Topic 2")
        t3 = _make_topic("Topic 3")
        repo.save_topic(t1)
        repo.save_topic(t2)
        repo.save_topic(t3)

        topics = repo.list_topics()
        assert len(topics) == 3
        titles = {t.title for t in topics}
        assert titles == {"Topic 1", "Topic 2", "Topic 3"}

    def test_save_overwrites_existing(self, tmp_path):
        repo = DecisionRepository(tmp_path / "data")
        topic = _make_topic("Original")

        repo.save_topic(topic)

        # Modify topic and save again
        topic.title = "Updated"
        repo.save_topic(topic)

        loaded = repo.get_topic(topic.id)
        assert loaded is not None
        assert loaded.title == "Updated"

    def test_roundtrip_preserves_data(self, tmp_path):
        repo = DecisionRepository(tmp_path / "data")
        topic = _make_topic("Roundtrip")
        topic.add_research("Research content", source="http://example.com")
        topic.add_option("Option A", "First option")

        repo.save_topic(topic)
        loaded = repo.get_topic(topic.id)

        assert loaded is not None
        assert loaded.title == "Roundtrip"
        assert len(loaded.research_notes) == 1
        assert len(loaded.options) == 1
        assert loaded.research_notes[0].content == "Research content"
        assert loaded.options[0].title == "Option A"
