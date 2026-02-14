"""Tests for ea_needs.repository — file-based persistence."""

import pytest
from ea_needs.catalog import NeedCatalog
from ea_needs.repository import NeedRepository
from ea_needs.types import NeedPriority, NeedRelationType, NeedStatus


@pytest.fixture
def repo(tmp_path):
    return NeedRepository(data_dir=tmp_path)


@pytest.fixture
def sample_catalog() -> NeedCatalog:
    catalog = NeedCatalog(name="Persistence Test", description="repo test")
    sh = catalog.add_stakeholder("CTO", "executive")
    n1 = catalog.express_need(
        sh.id, "migrate", "db", target="cloud",
        justifications=[{"type": "because", "description": "outages"}],
        priority=NeedPriority.HIGH,
    )
    n1.express()
    n2 = catalog.express_need(sh.id, "add", "monitoring")
    catalog.relate_needs(n1.id, n2.id, NeedRelationType.DEPENDS_ON)
    return catalog


class TestNeedRepository:
    def test_save_and_get(self, repo: NeedRepository, sample_catalog: NeedCatalog):
        catalog_id = repo.save_catalog(sample_catalog)
        restored = repo.get_catalog(catalog_id)

        assert restored is not None
        assert restored.id == sample_catalog.id
        assert restored.name == sample_catalog.name
        assert len(restored.stakeholders) == 1
        assert len(restored.needs) == 2
        assert len(restored.relations) == 1
        assert restored.needs[0].status == NeedStatus.EXPRESSED

    def test_get_nonexistent(self, repo: NeedRepository):
        assert repo.get_catalog("nonexistent") is None

    def test_list_catalogs(self, repo: NeedRepository):
        c1 = NeedCatalog(name="Catalog A")
        c2 = NeedCatalog(name="Catalog B")

        repo.save_catalog(c1)
        repo.save_catalog(c2)

        catalogs = repo.list_catalogs()
        assert len(catalogs) == 2
        names = {c.name for c in catalogs}
        assert names == {"Catalog A", "Catalog B"}

    def test_overwrite_catalog(self, repo: NeedRepository, sample_catalog: NeedCatalog):
        repo.save_catalog(sample_catalog)

        # Mutate and re-save
        sample_catalog.needs[1].express()
        repo.save_catalog(sample_catalog)

        restored = repo.get_catalog(sample_catalog.id)
        assert restored.needs[1].status == NeedStatus.EXPRESSED

    def test_empty_list(self, repo: NeedRepository):
        assert repo.list_catalogs() == []

    def test_creates_directory(self, tmp_path):
        new_dir = tmp_path / "nested" / "data"
        NeedRepository(data_dir=new_dir)
        assert (new_dir / "catalogs").exists()


class TestKernelBridge:
    """Basic smoke tests for kernel_bridge (lazy import)."""

    def test_validate_kernel_refs_with_real_kernel(self):
        from ea_needs.kernel_bridge import validate_kernel_refs

        result = validate_kernel_refs(["element", "nonexistent_entity"])
        # "element" is a real kernel entity (lowercase in schema)
        assert result["element"] is True
        assert result["nonexistent_entity"] is False

    def test_kernel_entity_summary(self):
        from ea_needs.kernel_bridge import kernel_entity_summary

        summary = kernel_entity_summary("element")
        assert summary is not None
        assert summary["name"] == "element"

    def test_kernel_entity_summary_not_found(self):
        from ea_needs.kernel_bridge import kernel_entity_summary

        assert kernel_entity_summary("NonExistentEntity") is None
