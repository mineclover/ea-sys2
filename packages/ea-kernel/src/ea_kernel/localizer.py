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
