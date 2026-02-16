"""Tests for BusinessService — CRUD operations and Indexing Spec derivation."""

from __future__ import annotations

import pytest

from ea_kernel.business_service import BusinessService


@pytest.fixture()
def svc(tmp_path):
    return BusinessService(tmp_path)


# ---- Business CRUD ----

class TestBusinessCRUD:
    def test_create_and_list(self, svc):
        biz = svc.create_business("Hotel Ops", "Hotel management")
        assert biz["bid"] == "hotel_ops"
        assert biz["name"] == "Hotel Ops"

        items = svc.list_businesses()
        assert len(items) == 1
        assert items[0]["bid"] == "hotel_ops"

    def test_create_duplicate_raises(self, svc):
        svc.create_business("test_biz")
        with pytest.raises(ValueError, match="already exists"):
            svc.create_business("test_biz")

    def test_get_business_detail(self, svc):
        svc.create_business("my_biz")
        detail = svc.get_business("my_biz")
        assert detail["bid"] == "my_biz"
        assert detail["tag_count"] == 0

    def test_get_nonexistent_raises(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.get_business("nope")

    def test_delete_business(self, svc):
        svc.create_business("to_delete")
        svc.delete_business("to_delete")
        assert len(svc.list_businesses()) == 0

    def test_invalid_bid_raises(self, svc):
        with pytest.raises(ValueError, match="Invalid bid"):
            svc.get_business("UPPER")


# ---- Tag-Schema CRUD ----

class TestTagSchemaCRUD:
    def test_create_and_list_tags(self, svc):
        svc.create_business("biz")
        tag = svc.create_tag("biz", {
            "tag": "room",
            "fields": [{"name": "floor", "type": "number"}],
        })
        assert tag["tag"] == "room"
        assert len(tag["fields"]) == 1

        tags = svc.list_tags("biz")
        assert len(tags) == 1

    def test_get_tag(self, svc):
        svc.create_business("biz")
        svc.create_tag("biz", {"tag": "guest", "fields": []})
        tag = svc.get_tag("biz", "guest")
        assert tag["tag"] == "guest"

    def test_update_tag(self, svc):
        svc.create_business("biz")
        svc.create_tag("biz", {"tag": "room", "fields": []})
        updated = svc.update_tag("biz", "room", {
            "fields": [{"name": "floor", "type": "number"}],
            "description": "Room data",
        })
        assert len(updated["fields"]) == 1
        assert updated["description"] == "Room data"

    def test_delete_tag(self, svc):
        svc.create_business("biz")
        svc.create_tag("biz", {"tag": "room", "fields": []})
        svc.delete_tag("biz", "room")
        assert len(svc.list_tags("biz")) == 0

    def test_create_tag_duplicate_raises(self, svc):
        svc.create_business("biz")
        svc.create_tag("biz", {"tag": "room", "fields": []})
        with pytest.raises(ValueError, match="already exists"):
            svc.create_tag("biz", {"tag": "room", "fields": []})

    def test_tag_on_nonexistent_bid_raises(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.create_tag("nope", {"tag": "room", "fields": []})


# ---- Indexing Spec Derivation ----

class TestIndexingSpec:
    def test_derive_empty_spec(self, svc):
        svc.create_business("biz")
        spec = svc.derive_indexing_spec("biz")
        assert spec["bid"] == "biz"
        assert spec["tables"] == {}
        assert spec["xmlHints"] == {}
        assert spec["promptHints"] == {}

    def test_derive_with_tags(self, svc):
        svc.create_business("hotel")
        svc.create_tag("hotel", {
            "tag": "room",
            "fields": [
                {"name": "floor", "type": "number", "required": True},
                {"name": "status", "type": "string", "enum": ["available", "occupied"]},
            ],
            "indexes": [{"name": "by_floor", "keyPath": "floor"}],
        })

        spec = svc.derive_indexing_spec("hotel")

        assert "room" in spec["tables"]
        table = spec["tables"]["room"]
        assert table["keyPath"] == "id"
        assert table["autoIncrement"] is True
        assert len(table["fields"]) == 2
        assert len(table["indexes"]) == 1

        assert "room" in spec["xmlHints"]
        assert spec["xmlHints"]["room"]["rootTag"] == "hotel:room"
        assert "floor" in spec["xmlHints"]["room"]["childTags"]

        assert "room" in spec["promptHints"]
        assert "hotel:room" in spec["promptHints"]["room"]

    def test_derive_nonexistent_raises(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.derive_indexing_spec("nope")
