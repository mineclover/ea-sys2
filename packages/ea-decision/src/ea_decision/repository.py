import json
from typing import Optional, Union, List
from pathlib import Path

from ea_decision.topic import Topic


class DecisionRepository:
    """File-based repository for persisting Design Thinking topics."""
    
    def __init__(self, data_dir: Union[str, Path]):
        self.data_dir = Path(data_dir)
        self.topic_dir = self.data_dir / "topics"
        self.topic_dir.mkdir(parents=True, exist_ok=True)
        
    def save_topic(self, topic: Topic) -> str:
        """Saves a Topic object (with all its research, options, etc.) to a JSON file."""
        file_path = self.topic_dir / f"{topic.id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(topic.to_json())
        return topic.id

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        """Retrieves a Topic object by ID."""
        file_path = self.topic_dir / f"{topic_id}.json"
        if not file_path.exists():
            return None
            
        with open(file_path, "r", encoding="utf-8") as f:
            return Topic.from_json(f.read())

    def list_topics(self) -> List[Topic]:
        """Lists all topics."""
        topics = []
        for file_path in self.topic_dir.glob("*.json"):
            with open(file_path, "r", encoding="utf-8") as f:
                topics.append(Topic.from_json(f.read()))
        return topics

