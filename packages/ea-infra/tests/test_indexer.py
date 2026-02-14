import pytest
from pathlib import Path
from ea_infra.indexer import ResourceIndexer

def test_indexer_scan(tmp_path):
    # Setup test files
    (tmp_path / "test.md").write_text("# Test")
    (tmp_path / "code.py").write_text("print('hello')")
    (tmp_path / "ignored.txt").write_text("ignore me")
    
    indexer = ResourceIndexer(tmp_path)
    
    # Test 1: Scan all
    resources = list(indexer.scan())
    assert len(resources) == 3
    
    # Test 2: Filter by extension
    resources = list(indexer.scan(extensions=[".md", ".py"]))
    assert len(resources) == 2
    uris = [r.uri for r in resources]
    assert "file://test.md" in uris
    assert "file://code.py" in uris
    
    # Test 3: Metadata
    res = next(r for r in resources if r.name == "test.md")
    assert res.content_type == "text/markdown"
    assert res.path == str(tmp_path / "test.md")
    assert res.last_modified is not None
