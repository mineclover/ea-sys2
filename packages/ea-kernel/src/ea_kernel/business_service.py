"""Business Model & Tag-Schema Registry service.

Provides bid-scoped CRUD for business models and their tag-schema definitions,
plus derivation of browser-side Indexing Specs from registered tag schemas.

Storage layout:
    {data_dir}/business/{bid}/meta.json
    {data_dir}/business/{bid}/tags/{tag}.json
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BID_PATTERN = re.compile(r"^[a-z0-9_]{2,32}$")
TAG_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class BusinessService:
    """Manages business models and their tag-schema registries."""

    def __init__(self, data_dir: Path, kernel_schema: Any | None = None) -> None:
        self._base = data_dir / "business"
        self._base.mkdir(parents=True, exist_ok=True)
        self._kernel_schema = kernel_schema

    # ---- helpers ----

    def _bid_dir(self, bid: str) -> Path:
        return self._base / bid

    def _meta_path(self, bid: str) -> Path:
        return self._bid_dir(bid) / "meta.json"

    def _tags_dir(self, bid: str) -> Path:
        return self._bid_dir(bid) / "tags"

    def _tag_path(self, bid: str, tag: str) -> Path:
        return self._tags_dir(bid) / f"{tag}.json"

    def _validate_bid(self, bid: str) -> None:
        if not BID_PATTERN.match(bid):
            raise ValueError(
                f"Invalid bid '{bid}': must match [a-z0-9_]{{2,32}}"
            )

    def _validate_tag(self, tag: str) -> None:
        if not TAG_PATTERN.match(tag):
            raise ValueError(
                f"Invalid tag '{tag}': must match [a-z0-9_]{{1,64}}"
            )

    def _require_bid(self, bid: str) -> None:
        if not self._meta_path(bid).exists():
            raise KeyError(f"Business '{bid}' not found")

    def _require_tag(self, bid: str, tag: str) -> None:
        if not self._tag_path(bid, tag).exists():
            raise KeyError(f"Tag '{tag}' not found in business '{bid}'")

    # ---- Business CRUD ----

    def create_business(self, name: str, description: str = "") -> dict[str, Any]:
        bid = re.sub(r"[^a-z0-9_]", "_", name.lower().strip())[:32]
        if len(bid) < 2:
            bid = bid.ljust(2, "_")
        self._validate_bid(bid)

        meta_path = self._meta_path(bid)
        if meta_path.exists():
            raise ValueError(f"Business '{bid}' already exists")

        now = _now_iso()
        meta = {
            "bid": bid,
            "name": name,
            "description": description,
            "created_at": now,
        }
        _write_json(meta_path, meta)
        self._tags_dir(bid).mkdir(parents=True, exist_ok=True)
        logger.info("Created business '%s'", bid)
        return meta

    def list_businesses(self) -> list[dict[str, Any]]:
        result = []
        if not self._base.exists():
            return result
        for d in sorted(self._base.iterdir()):
            meta_path = d / "meta.json"
            if meta_path.exists():
                result.append(_read_json(meta_path))
        return result

    def get_business(self, bid: str) -> dict[str, Any]:
        self._validate_bid(bid)
        self._require_bid(bid)
        meta = _read_json(self._meta_path(bid))
        tags_dir = self._tags_dir(bid)
        tag_count = sum(1 for f in tags_dir.glob("*.json")) if tags_dir.exists() else 0
        return {**meta, "tag_count": tag_count}

    def delete_business(self, bid: str) -> None:
        self._validate_bid(bid)
        self._require_bid(bid)
        import shutil
        shutil.rmtree(self._bid_dir(bid))
        logger.info("Deleted business '%s'", bid)

    # ---- Tag-Schema CRUD ----

    def _validate_kernel_ref(self, kernel_ref: str | None) -> dict[str, Any] | None:
        """Validate kernel_ref against kernel schema if available.

        Returns validation info dict or None if no validation was done.
        """
        if not kernel_ref or not self._kernel_schema:
            return None

        schema = self._kernel_schema
        # Check if kernel_ref matches an entity name
        entity_names = {e.name for e in schema.entities}
        relation_names = {r.name for r in schema.relations}

        if kernel_ref in entity_names:
            return {"kind": "entity", "name": kernel_ref, "valid": True}
        if kernel_ref in relation_names:
            return {"kind": "relation", "name": kernel_ref, "valid": True}

        raise ValueError(
            f"kernel_ref '{kernel_ref}' not found in kernel schema. "
            f"Valid entities: {sorted(entity_names)[:10]}..."
        )

    def create_tag(self, bid: str, data: dict[str, Any]) -> dict[str, Any]:
        self._validate_bid(bid)
        self._require_bid(bid)
        tag = data.get("tag", "")
        self._validate_tag(tag)

        # Validate kernel_ref if provided
        kernel_ref = data.get("kernel_ref")
        validation = self._validate_kernel_ref(kernel_ref)

        tag_path = self._tag_path(bid, tag)
        if tag_path.exists():
            raise ValueError(f"Tag '{tag}' already exists in business '{bid}'")

        now = _now_iso()
        schema = {
            "tag": tag,
            "fields": data.get("fields", []),
            "indexes": data.get("indexes", []),
            "keyPath": data.get("keyPath", "id"),
            "autoIncrement": data.get("autoIncrement", True),
            "kernel_ref": data.get("kernel_ref"),
            "description": data.get("description", ""),
            "created_at": now,
            "updated_at": now,
        }
        _write_json(tag_path, schema)
        logger.info("Created tag '%s' in business '%s'", tag, bid)
        return schema

    def list_tags(self, bid: str) -> list[dict[str, Any]]:
        self._validate_bid(bid)
        self._require_bid(bid)
        tags_dir = self._tags_dir(bid)
        result = []
        if tags_dir.exists():
            for f in sorted(tags_dir.glob("*.json")):
                result.append(_read_json(f))
        return result

    def get_tag(self, bid: str, tag: str) -> dict[str, Any]:
        self._validate_bid(bid)
        self._require_bid(bid)
        self._validate_tag(tag)
        self._require_tag(bid, tag)
        return _read_json(self._tag_path(bid, tag))

    def update_tag(self, bid: str, tag: str, data: dict[str, Any]) -> dict[str, Any]:
        self._validate_bid(bid)
        self._require_bid(bid)
        self._validate_tag(tag)
        self._require_tag(bid, tag)

        # Validate kernel_ref if being updated
        if "kernel_ref" in data and data["kernel_ref"]:
            self._validate_kernel_ref(data["kernel_ref"])

        existing = _read_json(self._tag_path(bid, tag))
        for key in ("fields", "indexes", "keyPath", "autoIncrement", "kernel_ref", "description"):
            if key in data:
                existing[key] = data[key]
        existing["updated_at"] = _now_iso()

        _write_json(self._tag_path(bid, tag), existing)
        logger.info("Updated tag '%s' in business '%s'", tag, bid)
        return existing

    def delete_tag(self, bid: str, tag: str) -> None:
        self._validate_bid(bid)
        self._require_bid(bid)
        self._validate_tag(tag)
        self._require_tag(bid, tag)
        self._tag_path(bid, tag).unlink()
        logger.info("Deleted tag '%s' from business '%s'", tag, bid)

    # ---- Indexing Spec Derivation ----

    def derive_indexing_spec(self, bid: str) -> dict[str, Any]:
        """Derive a browser-side Indexing Spec from all registered tag schemas."""
        self._validate_bid(bid)
        self._require_bid(bid)

        tags = self.list_tags(bid)
        tables: dict[str, Any] = {}
        xml_hints: dict[str, Any] = {}
        prompt_hints: dict[str, str] = {}

        for tag_schema in tags:
            tag = tag_schema["tag"]
            fields = tag_schema.get("fields", [])
            indexes = tag_schema.get("indexes", [])

            tables[tag] = {
                "keyPath": tag_schema.get("keyPath", "id"),
                "autoIncrement": tag_schema.get("autoIncrement", True),
                "indexes": indexes,
                "fields": fields,
            }

            child_tags = [f["name"] for f in fields]
            xml_hints[tag] = {
                "rootTag": f"{bid}:{tag}",
                "childTags": child_tags,
            }

            field_desc = ", ".join(child_tags) if child_tags else "relevant fields"
            prompt_hints[tag] = (
                f"When describing {tag} data, wrap each item in "
                f"<{bid}:{tag}>...</{bid}:{tag}> with child elements: {field_desc}"
            )

        # Version is derived from the count of tags + a timestamp hash
        version = len(tags) + int(time.time()) % 10000

        return {
            "bid": bid,
            "version": version,
            "tables": tables,
            "xmlHints": xml_hints,
            "promptHints": prompt_hints,
        }

    # ---- Export / Import ----

    def export_business(self, bid: str) -> dict[str, Any]:
        """Export a complete business model (meta + all tags) as a single JSON object."""
        self._validate_bid(bid)
        self._require_bid(bid)
        meta = _read_json(self._meta_path(bid))
        tags = self.list_tags(bid)
        return {"meta": meta, "tags": tags}

    def import_business(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import a business model from an exported JSON object.

        If the bid already exists, merges tags (overwriting existing, adding new).
        """
        meta = data.get("meta", {})
        tags = data.get("tags", [])
        bid = meta.get("bid", "")
        self._validate_bid(bid)

        meta_path = self._meta_path(bid)
        if not meta_path.exists():
            _write_json(meta_path, meta)
            self._tags_dir(bid).mkdir(parents=True, exist_ok=True)

        imported_tags = 0
        for tag_data in tags:
            tag = tag_data.get("tag", "")
            if not tag:
                continue
            _write_json(self._tag_path(bid, tag), tag_data)
            imported_tags += 1

        logger.info("Imported business '%s' with %d tags", bid, imported_tags)
        return {"bid": bid, "imported_tags": imported_tags}
