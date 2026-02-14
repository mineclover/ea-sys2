"""Model I/O Manager for Exporting/Importing Governance Data."""

from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict

from ea_kernel.governance import GovernanceSystem
from ea_kernel.governance_types import RuleAsset, RuleLifecycleState, RuleProvenance, RuleLifecycle
from ea_kernel.types import KernelValidityRule, RuleMetadata, RuleCorpusEntry, RuleCategory, RuleConfidence, RuleGroup

class ImportStrategy(Enum):
    SKIP_EXISTING = "skip"
    OVERWRITE = "overwrite"
    FAIL = "fail"

class ModelIOManager:
    """Manages Export/Import of Governance Models."""
    
    def __init__(self, system: GovernanceSystem):
        self.system = system
        
    def export_model(self, 
                     target_state: RuleLifecycleState | None = None, 
                     domain: str | None = None) -> Dict[str, Any]:
        """
        Exports rules matching criteria to a dictionary structure.
        """
        # 1. Fetch all assets (simplified access via store iterators if available, 
        # but here we rely on what we can get. RuleAssetStore has active_rules, 
        # but for full export we might want everything. For now, active only or specific query.)
        
        # Accessing private store directly for full scan is not ideal but necessary without rich query API
        # Assuming we just export active rules for now as primarily
        all_rules = self.system.rule_store.active_rules()
        
        exported_rules = []
        for asset in all_rules:
            # Filter
            if target_state and asset.lifecycle.current_state != target_state:
                continue
            if domain and asset.entry.metadata.domain != domain:
                continue
                
            # Serialize
            # RuleAsset is frozen dataclass, asdict should work
            # Note: Need to handle complex types if any (Enums -> str)
            rule_data = asdict(asset)
            
            # Simple recursive enum conversion helper
            rule_data = self._serialize(rule_data)
            exported_rules.append(rule_data)
            
        return {
            "meta": {
                "exported_by": "ea-kernel-io",
                "rules_count": len(exported_rules),
            },
            "rules": exported_rules
        }

    def import_model(self, 
                     data: Dict[str, Any], 
                     strategy: ImportStrategy = ImportStrategy.SKIP_EXISTING) -> Dict[str, int]:
        """
        Imports rules from the data structure.
        """
        rules_data: list[dict] = data.get("rules", [])
        imported = 0
        skipped = 0
        failed = 0
        
        for r_data in rules_data:
            try:
                # Reconstruct RuleAsset
                # This is tricky because of nested dataclasses and Enums
                # We need a robust deserializer.
                # For PoC, we manually reconstruct critical parts or use a helper
                asset = self._deserialize_asset(r_data)
                
                # Check existence
                existing = self.system.rule_store.get(asset.id)
                
                if existing:
                    if strategy == ImportStrategy.SKIP_EXISTING:
                        skipped += 1
                        continue
                    elif strategy == ImportStrategy.FAIL:
                        raise ValueError(f"Rule {asset.id} already exists.")
                    elif strategy == ImportStrategy.OVERWRITE:
                        # Logic to overwrite/update
                        # Ideally RuleAssetStore should support 'save' or 'update'
                        # For now, we simulate by just relying on create/transition if supported
                        # or direct store access (hacky).
                        # Let's assume create handles upsert or we fail.
                        pass

                # Create (Restore)
                # Use restore() to bypass DRAFT check since we are importing existing assets
                self.system.rule_store.restore(asset) 
                
                # If imported asset was approved, we might need to reflect that
                # Store.create might reset lifecycle to DRAFT by default depending on implementation
                # If we want to preserve state, we might need a lower-level 'import' method in store
                # For this PoC, we just save it.
                
                imported += 1
                
            except Exception as e:
                # print(f"Failed to import rule: {e}")
                failed += 1
                
        # Rebuild corpus after import
        self.system._rebuild_corpus()
        
        return {"imported": imported, "skipped": skipped, "failed": failed}

    def _serialize(self, obj: Any) -> Any:
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, (list, tuple)):
            return [self._serialize(i) for i in obj]
        if isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        return obj

    def _deserialize_asset(self, data: dict) -> RuleAsset:
        """Reconstruct RuleAsset from dict. 
        Note: This requires careful mapping of nested dicts to Dataclasses.
        """
        # Entry
        entry_data = data["entry"]
        rule_data = entry_data["rule"]
        meta_data = entry_data["metadata"]
        
        rule = KernelValidityRule(
            id=rule_data["id"],
            source_pattern=rule_data["source_pattern"],
            target_pattern=rule_data["target_pattern"],
            relationship_name=rule_data["relationship_name"],
            valid=rule_data["valid"],
            priority=rule_data["priority"]
        )
        
        meta = RuleMetadata(
            domain=meta_data["domain"],
            tags=tuple(meta_data["tags"]),
            category=RuleCategory(meta_data["category"]),
            confidence=RuleConfidence(meta_data["confidence"]),
            source=meta_data["source"],
            established_version=meta_data["established_version"],
            rationale=meta_data["rationale"],
            group=RuleGroup(meta_data["group"]),
        )
        entry = RuleCorpusEntry(rule, meta)
        
        # Provenance
        prov_data = data["provenance"]
        prov = RuleProvenance(
            author=prov_data["author"],
            source_type=prov_data["source_type"],
            source_reference=prov_data["source_reference"],
            created_at=prov_data["created_at"],
            # ... other fields
        )
        
        # Lifecycle
        life_data = data["lifecycle"]
        lifecycle = RuleLifecycle(
            current_state=RuleLifecycleState(life_data["current_state"])
        )
        
        return RuleAsset(entry, prov, lifecycle)
