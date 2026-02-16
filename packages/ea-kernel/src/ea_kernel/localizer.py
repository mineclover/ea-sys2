from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from ea_kernel.profile_types import KernelProfile
from ea_kernel.types import I18nString


def _to_i18n(value: I18nString, *, fallback_en: str = "") -> dict[str, str]:
    """Normalize i18n text into a mutable language map."""
    if isinstance(value, str):
        return {"en": value or fallback_en}
    return dict(value)


def _en_text(value: I18nString) -> str:
    """Extract English source text from I18nString."""
    if isinstance(value, str):
        return value
    return value.get("en", "")


def _profile_i18n_items(profile: KernelProfile) -> dict[tuple[str, str], dict[str, str]]:
    """Extract M1 translation slots from a profile.

    Returns:
        (kind, name) -> {field: en_source}
    """
    items: dict[tuple[str, str], dict[str, str]] = {}

    for e in profile.elements:
        items[("element", e.name)] = {
            "display_name": _en_text(e.display_name),
            "description": _en_text(e.description),
        }

    for r in profile.relations:
        items[("relation", r.name)] = {
            "display_name": _en_text(r.display_name),
            "description": _en_text(r.description),
        }

    for rule in profile.validity_rules:
        items[("validity_rule", rule.id)] = {
            "description": _en_text(rule.description),
        }

    return items


class ProfileLocalizer:
    """Handles loading and merging of language patches for KernelProfiles."""

    def __init__(self, patch_dir: Path | None = None) -> None:
        self.patch_dir = patch_dir

    def load_patch(self, patch_path: Path) -> dict[str, Any]:
        """Load a `.patch.toml` file."""
        if not patch_path.exists():
            return {}

        try:
            loaded = tomllib.loads(patch_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return {}

        if isinstance(loaded, dict):
            return loaded
        return {}

    def apply_patch(
        self,
        profile: KernelProfile,
        patch_data: dict[str, Any],
        lang: str,
    ) -> KernelProfile:
        """Merge patch data into a profile for a specific language."""
        new_elements = []
        elem_patches_raw = patch_data.get("elements", {})
        elem_patches = (
            elem_patches_raw if isinstance(elem_patches_raw, Mapping) else {}
        )
        for elem in profile.elements:
            patch_raw = elem_patches.get(elem.name)
            if not isinstance(patch_raw, Mapping):
                new_elements.append(elem)
                continue

            new_desc = _to_i18n(elem.description)
            patch_desc = patch_raw.get("description")
            if isinstance(patch_desc, str):
                new_desc[lang] = patch_desc

            new_display_name = _to_i18n(elem.display_name, fallback_en=elem.name)
            patch_display_name = patch_raw.get("display_name")
            if isinstance(patch_display_name, str):
                new_display_name[lang] = patch_display_name

            new_elements.append(
                replace(
                    elem,
                    description=new_desc,
                    display_name=new_display_name,
                )
            )

        new_relations = []
        rel_patches_raw = patch_data.get("relations", {})
        rel_patches = (
            rel_patches_raw if isinstance(rel_patches_raw, Mapping) else {}
        )
        for rel in profile.relations:
            patch_raw = rel_patches.get(rel.name)
            if not isinstance(patch_raw, Mapping):
                new_relations.append(rel)
                continue

            new_desc = _to_i18n(rel.description)
            patch_desc = patch_raw.get("description")
            if isinstance(patch_desc, str):
                new_desc[lang] = patch_desc

            new_display_name = _to_i18n(rel.display_name, fallback_en=rel.name)
            patch_display_name = patch_raw.get("display_name")
            if isinstance(patch_display_name, str):
                new_display_name[lang] = patch_display_name

            new_relations.append(
                replace(
                    rel,
                    description=new_desc,
                    display_name=new_display_name,
                )
            )

        new_rules = []
        rule_patches_raw = patch_data.get("validity_rules", {})
        rule_patches = (
            rule_patches_raw if isinstance(rule_patches_raw, Mapping) else {}
        )
        for rule in profile.validity_rules:
            patch_raw = rule_patches.get(rule.id)
            if not isinstance(patch_raw, Mapping):
                new_rules.append(rule)
                continue

            new_desc = _to_i18n(rule.description)
            patch_desc = patch_raw.get("description")
            if isinstance(patch_desc, str):
                new_desc[lang] = patch_desc
            new_rules.append(replace(rule, description=new_desc))

        return replace(
            profile,
            elements=tuple(new_elements),
            relations=tuple(new_relations),
            validity_rules=tuple(new_rules),
        )

    def localize(
        self,
        profile: KernelProfile,
        lang: str,
        search_path: Path | None = None,
    ) -> KernelProfile:
        """Find and apply the appropriate patch for a language."""
        if lang == "en":
            return profile

        base_path = search_path or self.patch_dir
        if not base_path:
            return profile

        patch_file = base_path / f"{profile.name.lower()}.{lang}.patch.toml"
        if patch_file.exists():
            patch_data = self.load_patch(patch_file)
            return self.apply_patch(profile, patch_data, lang)

        return profile


def audit_profile_i18n_patch(
    profile: KernelProfile,
    lang: str,
    patch_path: Path | None = None,
) -> "I18nAuditReport":
    """M1 profile patch audit (TOML-based, DB-independent)."""
    from ea_kernel.i18n_store import I18nAuditEntry, I18nAuditReport

    patch_data: dict[str, dict[str, dict[str, str]]] = {
        "elements": {},
        "relations": {},
        "validity_rules": {},
    }
    if patch_path is not None and patch_path.exists():
        try:
            doc = tomllib.loads(patch_path.read_text(encoding="utf-8"))
            raw_elements = doc.get("elements", {})
            raw_relations = doc.get("relations", {})
            raw_rules = doc.get("validity_rules", {})
            patch_data["elements"] = (
                raw_elements if isinstance(raw_elements, dict) else {}
            )
            patch_data["relations"] = (
                raw_relations if isinstance(raw_relations, dict) else {}
            )
            patch_data["validity_rules"] = (
                raw_rules if isinstance(raw_rules, dict) else {}
            )
        except (OSError, tomllib.TOMLDecodeError):
            pass

    profile_items = _profile_i18n_items(profile)
    section_map = {
        "element": "elements",
        "relation": "relations",
        "validity_rule": "validity_rules",
    }

    expected_fields = {
        "element": ("display_name", "description"),
        "relation": ("display_name", "description"),
        "validity_rule": ("description",),
    }

    missing: list[I18nAuditEntry] = []
    stale: list[I18nAuditEntry] = []
    orphan: list[I18nAuditEntry] = []
    schema_keys: set[tuple[str, str, str]] = set()

    for (kind, name), en_fields in profile_items.items():
        section = section_map[kind]
        patch = patch_data[section].get(name, {})
        if not isinstance(patch, Mapping):
            patch = {}

        for field_name, en_value in en_fields.items():
            schema_keys.add((kind, name, field_name))
            if field_name not in patch:
                missing.append(I18nAuditEntry(
                    kind=kind,
                    name=name,
                    issue="missing",
                    field=field_name,
                    en_current=en_value,
                    en_recorded="",
                ))
                continue

            en_key = f"_en_{field_name}"
            en_recorded = patch.get(en_key, "")
            if isinstance(en_recorded, str) and en_recorded and en_recorded != en_value:
                stale.append(I18nAuditEntry(
                    kind=kind,
                    name=name,
                    issue="stale",
                    field=field_name,
                    en_current=en_value,
                    en_recorded=en_recorded,
                ))

    for section, kind in (
        ("elements", "element"),
        ("relations", "relation"),
        ("validity_rules", "validity_rule"),
    ):
        for item_name, fields in patch_data[section].items():
            if not isinstance(fields, Mapping):
                continue
            for field_name in expected_fields[kind]:
                if field_name in fields and (kind, item_name, field_name) not in schema_keys:
                    en_key = f"_en_{field_name}"
                    en_recorded = fields.get(en_key, "")
                    orphan.append(I18nAuditEntry(
                        kind=kind,
                        name=item_name,
                        issue="orphan",
                        field=field_name,
                        en_current="",
                        en_recorded=en_recorded if isinstance(en_recorded, str) else "",
                    ))

    total_slots = sum(len(fields) for fields in profile_items.values())
    translated = total_slots - len(missing)

    return I18nAuditReport(
        lang=lang,
        missing=tuple(missing),
        orphan=tuple(orphan),
        stale=tuple(stale),
        total_schema_items=total_slots,
        total_translated=translated,
    )
