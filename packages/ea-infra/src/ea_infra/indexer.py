import os
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Generator, Optional

@dataclass
class Resource:
    uri: str
    path: str
    name: str
    content_type: str
    last_modified: str
    content: Optional[str] = None

class ResourceIndexer:
    """
    Scans directories and indexes files into Resource objects.
    Acts as the ingestion engine for Layer 1.
    """
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def scan(self, sub_paths: List[str] = None, extensions: List[str] = None) -> Generator[Resource, None, None]:
        """
        Yields Resource objects found in the root_dir.
        Optionally filters by sub_paths and file extensions.
        """
        search_dirs = [self.root_dir / p for p in sub_paths] if sub_paths else [self.root_dir]
        valid_exts = set(extensions) if extensions else None

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
                
            for root, _, files in os.walk(search_dir):
                for file_name in files:
                    if valid_exts and not any(file_name.endswith(ext) for ext in valid_exts):
                        continue
                    
                    file_path = Path(root) / file_name
                    yield self._create_resource(file_path)

    def _create_resource(self, file_path: Path) -> Resource:
        """Creates a Resource object from a file path."""
        # Calculate relative path for stable URI
        try:
            rel_path = file_path.relative_to(self.root_dir)
        except ValueError:
            rel_path = file_path # Fallback if outside root
            
        uri = f"file://{rel_path}"
        stat = file_path.stat()
        last_modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
        
        # Determine content type (simple heuristic)
        ext = file_path.suffix.lower()
        content_type = "text/plain"
        if ext in [".md", ".markdown"]:
            content_type = "text/markdown"
        elif ext in [".py"]:
            content_type = "text/x-python"
        elif ext in [".json"]:
            content_type = "application/json"
            
        return Resource(
            uri=uri,
            path=str(file_path),
            name=file_path.name,
            content_type=content_type,
            last_modified=last_modified
        )
