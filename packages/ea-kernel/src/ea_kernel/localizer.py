from __future__ import annotations
try:
    import tomllib
except ImportError:
    import tomli as tomllib
from pathlib import Path
from dataclasses import replace
from typing import Dict, Any, List

from ea_kernel.profile_types import KernelProfile, ProfileElement, ProfileRelation

class ProfileLocalizer:
    """Handles loading and merging of language patches for KernelProfiles."""

    def __init__(self, patch_dir: Path | None = None):
        self.patch_dir = patch_dir

    def load_patch(self, patch_path: Path) -> Dict[str, Any]:
        """Load a .patch.toml file."""
        if not patch_path.exists():
            return {}
        try:
            return tomllib.loads(patch_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def apply_patch(self, profile: KernelProfile, patch_data: Dict[str, Any], lang: str) -> KernelProfile:
        """Merge patch data into a profile for a specific language."""
        
        # 1. Update Elements
        new_elements = []
        elem_patches = patch_data.get("elements", {})
        for elem in profile.elements:
            if elem.name in elem_patches:
                patch = elem_patches[elem.name]
                
                # Patch Description
                desc = elem.description
                if isinstance(desc, str): desc = {"en": desc}
                new_desc = desc.copy()
                if "description" in patch:
                    new_desc[lang] = patch["description"]
                
                # Patch Display Name
                dname = elem.display_name
                if isinstance(dname, str): dname = {"en": dname or elem.name}
                new_dname = dname.copy()
                if "display_name" in patch:
                    new_dname[lang] = patch["display_name"]
                
                new_elements.append(replace(elem, description=new_desc, display_name=new_dname))
            else:
                new_elements.append(elem)

        # 2. Update Relations
        new_relations = []
        rel_patches = patch_data.get("relations", {})
        for rel in profile.relations:
            if rel.name in rel_patches:
                patch = rel_patches[rel.name]
                
                # Patch Description
                desc = rel.description
                if isinstance(desc, str): desc = {"en": desc}
                new_desc = desc.copy()
                if "description" in patch:
                    new_desc[lang] = patch["description"]
                
                # Patch Display Name
                dname = rel.display_name
                if isinstance(dname, str): dname = {"en": dname or rel.name}
                new_dname = dname.copy()
                if "display_name" in patch:
                    new_dname[lang] = patch["display_name"]
                
                new_relations.append(replace(rel, description=new_desc, display_name=new_dname))
            else:
                new_relations.append(rel)

        # 3. Update Validity Rules
        new_rules = []
        rule_patches = patch_data.get("validity_rules", {})
        for rule in profile.validity_rules:
            if rule.id in rule_patches:
                patch = rule_patches[rule.id]
                desc = rule.description
                if isinstance(desc, str): desc = {"en": desc}
                new_desc = desc.copy()
                if "description" in patch:
                    new_desc[lang] = patch["description"]
                new_rules.append(replace(rule, description=new_desc))
            else:
                new_rules.append(rule)

        return replace(
            profile, 
            elements=tuple(new_elements), 
            relations=tuple(new_relations),
            validity_rules=tuple(new_rules)
        )

    def localize(self, profile: KernelProfile, lang: str, search_path: Path | None = None) -> KernelProfile:
        """Find and apply the appropriate patch for a language."""
        if lang == "en": # Default
            return profile
            
        # Try to find {profile_name}.{lang}.patch.toml
        base_path = search_path or self.patch_dir
        if not base_path:
            return profile
            
        patch_file = base_path / f"{profile.name.lower()}.{lang}.patch.toml"
        if patch_file.exists():
            patch_data = self.load_patch(patch_file)
            return self.apply_patch(profile, patch_data, lang)
            
        return profile
