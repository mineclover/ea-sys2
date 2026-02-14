"""Governance-managed kernel store built on layer-scoped store contracts."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ea_kernel.governance_types import CorpusVersionInfo, RuleAsset
from ea_kernel.judgment_service import EnhancedJudgment

from ea_governance.layer_store import GovernanceLayerStore

_RULE_PREFIX = "rule:"
_CORPUS_VERSION_PREFIX = "corpus_version:"
_JUDGMENT_PREFIX = "judgment:"


def _rule_model_id(rule_id: str) -> str:
    return f"{_RULE_PREFIX}{rule_id}"


def _corpus_version_model_id(version_id: str) -> str:
    return f"{_CORPUS_VERSION_PREFIX}{version_id}"


def _judgment_model_id(decision_id: str) -> str:
    return f"{_JUDGMENT_PREFIX}{decision_id}"


class GovernanceKernelStore:
    """Kernel snapshot store implemented via layer-scoped governance store."""

    def __init__(self, db_path: str | Path):
        self._layer_store = GovernanceLayerStore(db_path=db_path, layer="kernel")
        self.db_path = self._layer_store.db_path

    def save_rule_asset(self, asset: RuleAsset) -> str:
        self._layer_store.save_payload(
            model_id=_rule_model_id(asset.id),
            payload=self._rule_asset_payload(asset),
        )
        return asset.id

    def get_rule_asset(self, rule_id: str) -> dict[str, Any] | None:
        payload = self._layer_store.get_payload(_rule_model_id(rule_id))
        if payload is None:
            return None
        return payload

    def list_rule_assets(self) -> list[dict[str, Any]]:
        return self._list_prefixed(_RULE_PREFIX)

    def save_corpus_version(self, version: CorpusVersionInfo) -> str:
        self._layer_store.save_payload(
            model_id=_corpus_version_model_id(version.version_id),
            payload=self._corpus_version_payload(version),
        )
        return version.version_id

    def get_corpus_version(self, version_id: str) -> dict[str, Any] | None:
        payload = self._layer_store.get_payload(_corpus_version_model_id(version_id))
        if payload is None:
            return None
        return payload

    def list_corpus_versions(self) -> list[dict[str, Any]]:
        return self._list_prefixed(_CORPUS_VERSION_PREFIX)

    def save_judgment(
        self,
        *,
        source: str,
        target: str,
        relation: str,
        actor: str,
        judgment: EnhancedJudgment,
    ) -> str:
        stored = judgment.stored_record
        decision_id = (
            stored.storage_id if stored is not None else f"volatile-{uuid4().hex}"
        )

        self._layer_store.save_payload(
            model_id=_judgment_model_id(decision_id),
            payload=self._judgment_payload(
                decision_id=decision_id,
                source=source,
                target=target,
                relation=relation,
                actor=actor,
                judgment=judgment,
            ),
        )
        return decision_id

    def get_judgment(self, decision_id: str) -> dict[str, Any] | None:
        payload = self._layer_store.get_payload(_judgment_model_id(decision_id))
        if payload is None:
            return None
        return payload

    def list_judgments(self) -> list[dict[str, Any]]:
        return self._list_prefixed(_JUDGMENT_PREFIX)

    def _list_prefixed(self, prefix: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for snapshot in self._layer_store.list_snapshots():
            if not snapshot.model_id.startswith(prefix):
                continue
            result.append(
                {
                    "model_id": snapshot.model_id,
                    "updated_at": snapshot.updated_at,
                    "payload": snapshot.payload,
                }
            )
        return result

    @staticmethod
    def _rule_asset_payload(asset: RuleAsset) -> dict[str, Any]:
        return {
            "kind": "kernel_rule_asset",
            "rule_id": asset.id,
            "rule": {
                "id": asset.rule.id,
                "source_pattern": asset.rule.source_pattern,
                "target_pattern": asset.rule.target_pattern,
                "relationship_name": asset.rule.relationship_name,
                "valid": asset.rule.valid,
                "priority": asset.rule.priority,
                "conditions": [
                    {
                        "condition_type": condition.condition_type.value,
                        "parameters": dict(condition.parameters),
                    }
                    for condition in asset.rule.conditions
                ],
                "description": asset.rule.description,
                "notes": asset.rule.notes,
            },
            "metadata": {
                "domain": asset.metadata.domain,
                "tags": list(asset.metadata.tags),
                "category": asset.metadata.category.value,
                "confidence": asset.metadata.confidence.value,
                "source": asset.metadata.source,
                "established_version": asset.metadata.established_version,
                "rationale": asset.metadata.rationale,
                "group": asset.metadata.group.value,
            },
            "provenance": {
                "author": asset.provenance.author,
                "source_type": asset.provenance.source_type,
                "source_reference": asset.provenance.source_reference,
                "decision_ref": asset.provenance.decision_ref,
                "created_at": asset.provenance.created_at,
                "updated_at": asset.provenance.updated_at,
                "version": asset.provenance.version,
            },
            "lifecycle": {
                "state": asset.lifecycle.current_state.value,
                "history": [
                    {
                        "timestamp": item[0],
                        "from_state": item[1],
                        "to_state": item[2],
                        "actor": item[3],
                        "reason": item[4],
                    }
                    for item in asset.lifecycle.state_history
                ],
            },
        }

    @staticmethod
    def _corpus_version_payload(version: CorpusVersionInfo) -> dict[str, Any]:
        payload = asdict(version)
        payload["kind"] = "kernel_corpus_version"
        payload["rule_ids"] = list(version.rule_ids)
        return payload

    @staticmethod
    def _judgment_payload(
        *,
        decision_id: str,
        source: str,
        target: str,
        relation: str,
        actor: str,
        judgment: EnhancedJudgment,
    ) -> dict[str, Any]:
        evidence = [
            {
                "rule_id": item.entry.rule.id,
                "domain": item.entry.metadata.domain,
                "matched": item.matched,
                "is_winner": item.is_winner,
                "condition_results": [
                    {"condition": cond_name, "result": cond_result}
                    for cond_name, cond_result in item.condition_results
                ],
            }
            for item in judgment.judgment.evidence
        ]
        return {
            "kind": "kernel_judgment",
            "decision_id": decision_id,
            "source": source,
            "target": target,
            "relation": relation,
            "actor": actor,
            "created_at": datetime.now(UTC).isoformat(),
            "judgment": {
                "verdict": judgment.judgment.verdict,
                "confidence": judgment.judgment.confidence.value,
                "domains": list(judgment.judgment.domains),
                "conflicts": list(judgment.judgment.conflicts),
                "evidence": evidence,
            },
            "reference_stats": asdict(judgment.reference_stats),
            "stored_record_id": judgment.stored_record.storage_id if judgment.stored_record else None,
            "corpus_version_id": (
                judgment.stored_record.corpus_version_id if judgment.stored_record else ""
            ),
        }
