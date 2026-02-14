import pytest
import json
from ea_decision.topic import ResearchNote, Topic
from ea_decision.types import Reference

def test_reference_serialization():
    ref = Reference(uri="file://test.md", title="Test Doc", citation="L10")
    note = ResearchNote(content="Based on this", references=[ref])
    
    topic = Topic(title="Test Topic", description="Desc")
    topic.research_notes.append(note)
    
    # Serialize
    json_str = topic.to_json()
    data = json.loads(json_str)
    
    assert data["research_notes"][0]["references"][0]["uri"] == "file://test.md"
    
    # Deserialize
    hydrated_topic = Topic.from_json(json_str)
    hydrated_ref = hydrated_topic.research_notes[0].references[0]
    
    assert isinstance(hydrated_ref, Reference)
    assert hydrated_ref.uri == "file://test.md"
    assert hydrated_ref.title == "Test Doc"
