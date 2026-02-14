"""Build and verify ea-kernel contract snapshots for external consumers.

This script produces deterministic JSON artifacts for cross-repo integration
(for example, ea-web consuming ea-sys2 kernel contracts).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ea_kernel.definition import KERNEL_SCHEMA, KERNEL_VERSION
from ea_kernel.rule_corpus import RuleCorpus
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.spec_loader import load_kernel_rules_with_metadata
from ea_kernel.types import (
    KernelAttribute,
    KernelEntity,
    KernelRelation,
    KernelValidityRule,
    LayerConstraint,
    RuleMetadata,
)

CONTRACT_VERSION = "1.0.0"
SCRIPT_NAME = "kernel_contract_snapshot.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PACKAGE_ROOT / "docs" / "reference" / "contracts"

SNAPSHOT_FILENAMES: dict[str, str] = {
    "schema": "kernel_schema.snapshot.json",
    "rules": "kernel_rules.snapshot.json",
    "vectors": "kernel_judgment_vectors.snapshot.json",
}

DEFAULT_VECTOR_CASES: tuple[tuple[str, tuple[str, str, str]], ...] = (
    ("allow-structure-association", ("structure", "structure", "association")),
    ("allow-event-trigger-step", ("event", "step", "triggering")),
    ("allow-state-transition", ("state", "state", "transition")),
    ("deny-item-specialize-structure", ("item", "structure", "specialization")),
    ("deny-package-connector-item", ("package", "item", "connector")),
    ("deny-event-trigger-structure", ("event", "structure", "triggering")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build/verify ea-kernel contract snapshots.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser("build", help="Build contract snapshots")
    build_p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    build_p.add_argument(
        "--force-reset",
        action="store_true",
        help="Delete existing snapshot files before build.",
    )

    verify_p = sub.add_parser("verify", help="Verify contract snapshots")
    verify_p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    return parser.parse_args()


def _attribute_payload(attr: KernelAttribute) -> dict[str, str]:
    return {
        "name": attr.name,
        "value_type": attr.value_type,
    }


def _entity_payload(entity: KernelEntity) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": entity.name,
        "layer": entity.layer.value,
        "is_abstract": entity.is_abstract,
        "owns": list(entity.owns),
        "plays": list(entity.plays),
        "description": entity.description,
    }
    if entity.parent is not None:
        payload["parent"] = entity.parent
    if entity.owns_key is not None:
        payload["owns_key"] = entity.owns_key
    return payload


def _relation_payload(relation: KernelRelation) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": relation.name,
        "layer": relation.layer.value,
        "roles": [
            {"name": role.name, "player": role.player}
            for role in relation.roles
        ],
        "owns": list(relation.owns),
        "description": relation.description,
    }
    if relation.parent is not None:
        payload["parent"] = relation.parent
    if relation.owns_key is not None:
        payload["owns_key"] = relation.owns_key
    return payload


def _rule_metadata_payload(metadata: RuleMetadata) -> dict[str, Any]:
    return {
        "domain": metadata.domain,
        "tags": list(metadata.tags),
        "category": metadata.category.value,
        "confidence": metadata.confidence.value,
        "source": metadata.source,
        "established_version": metadata.established_version,
        "rationale": metadata.rationale,
        "group": metadata.group.value,
    }


def _rule_payload(
    rule: KernelValidityRule,
    metadata_map: dict[str, RuleMetadata],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": rule.id,
        "source_pattern": rule.source_pattern,
        "target_pattern": rule.target_pattern,
        "relation": rule.relationship_name,
        "valid": rule.valid,
        "priority": rule.priority,
        "conditions": [
            {
                "type": condition.condition_type.value,
                "parameters": dict(condition.parameters),
            }
            for condition in rule.conditions
        ],
        "notes": rule.notes,
    }
    metadata = metadata_map.get(rule.id)
    if metadata is not None:
        payload["metadata"] = _rule_metadata_payload(metadata)
    return payload


def _layer_constraint_id(index: int, constraint: LayerConstraint) -> str:
    if constraint.id:
        return constraint.id
    forbidden = "-".join(constraint.forbidden_relations) if constraint.forbidden_relations else "none"
    return (
        f"lc-{index:02d}-"
        f"{constraint.source_layer.value.lower()}-"
        f"{constraint.target_layer.value.lower()}-"
        f"{forbidden}"
    )


def _layer_constraint_payload(index: int, constraint: LayerConstraint) -> dict[str, Any]:
    return {
        "id": _layer_constraint_id(index, constraint),
        "source_layer": constraint.source_layer.value,
        "target_layer": constraint.target_layer.value,
        "forbidden_relations": list(constraint.forbidden_relations),
        "allowed_pairs": [
            [source, target]
            for source, target in constraint.allowed_pairs
        ],
        "priority": constraint.priority,
        "notes": constraint.notes,
    }


def _build_schema_snapshot() -> dict[str, Any]:
    return {
        "snapshot_kind": "ea_kernel_schema_contract",
        "contract_version": CONTRACT_VERSION,
        "kernel_version": KERNEL_VERSION,
        "generated_by": SCRIPT_NAME,
        "stats": {
            "attributes": len(KERNEL_SCHEMA.attributes),
            "entities": len(KERNEL_SCHEMA.entities),
            "relations": len(KERNEL_SCHEMA.relations),
        },
        "attributes": [
            _attribute_payload(attribute)
            for attribute in KERNEL_SCHEMA.attributes
        ],
        "entities": [
            _entity_payload(entity)
            for entity in KERNEL_SCHEMA.entities
        ],
        "relations": [
            _relation_payload(relation)
            for relation in KERNEL_SCHEMA.relations
        ],
    }


def _build_rules_snapshot() -> dict[str, Any]:
    rules, constraints, metadata_map = load_kernel_rules_with_metadata()
    explicit_rules: list[dict[str, Any]] = []
    fallback_rules: list[dict[str, Any]] = []

    for rule in sorted(rules, key=lambda item: item.id):
        payload = _rule_payload(rule, metadata_map)
        if rule.id.startswith("fallback-"):
            fallback_rules.append(payload)
        else:
            explicit_rules.append(payload)

    return {
        "snapshot_kind": "ea_kernel_rules_contract",
        "contract_version": CONTRACT_VERSION,
        "kernel_version": KERNEL_VERSION,
        "generated_by": SCRIPT_NAME,
        "stats": {
            "total_rules": len(rules),
            "explicit_rules": len(explicit_rules),
            "fallback_rules": len(fallback_rules),
            "layer_constraints": len(constraints),
            "metadata_entries": len(metadata_map),
        },
        "explicit_rules": explicit_rules,
        "fallback_rules": fallback_rules,
        "layer_constraints": [
            _layer_constraint_payload(index, constraint)
            for index, constraint in enumerate(constraints)
        ],
    }


def _build_vectors_snapshot() -> dict[str, Any]:
    _rules, _constraints, metadata_map = load_kernel_rules_with_metadata()
    corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC, metadata_map=metadata_map)

    vectors: list[dict[str, Any]] = []
    allow_count = 0
    deny_count = 0

    for vector_id, triple in DEFAULT_VECTOR_CASES:
        report = corpus.judge(*triple)
        winner_rule_id = next(
            (evidence.entry.rule.id for evidence in report.evidence if evidence.is_winner),
            None,
        )
        if report.verdict:
            allow_count += 1
        else:
            deny_count += 1

        vectors.append(
            {
                "id": vector_id,
                "triple": list(triple),
                "expected_verdict": report.verdict,
                "expected_confidence": report.confidence.value,
                "expected_winner_rule_id": winner_rule_id,
            }
        )

    return {
        "snapshot_kind": "ea_kernel_judgment_vectors_contract",
        "contract_version": CONTRACT_VERSION,
        "kernel_version": KERNEL_VERSION,
        "generated_by": SCRIPT_NAME,
        "stats": {
            "vectors": len(vectors),
            "allow_vectors": allow_count,
            "deny_vectors": deny_count,
        },
        "vectors": vectors,
    }


def _build_payloads() -> dict[str, dict[str, Any]]:
    return {
        "schema": _build_schema_snapshot(),
        "rules": _build_rules_snapshot(),
        "vectors": _build_vectors_snapshot(),
    }


def _snapshot_paths(output_dir: Path) -> dict[str, Path]:
    return {
        key: output_dir / filename
        for key, filename in SNAPSHOT_FILENAMES.items()
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid snapshot payload: {path}")
    return raw


def _diff(expected: Any, actual: Any, path: str = "root") -> list[str]:
    if type(expected) is not type(actual):
        return [f"{path}: type mismatch expected={type(expected).__name__} actual={type(actual).__name__}"]

    if isinstance(expected, dict):
        dict_issues: list[str] = []
        expected_keys = set(expected)
        actual_keys = set(actual)
        for key in sorted(expected_keys - actual_keys):
            dict_issues.append(f"{path}.{key}: missing in actual")
        for key in sorted(actual_keys - expected_keys):
            dict_issues.append(f"{path}.{key}: unexpected key in actual")
        for key in sorted(expected_keys & actual_keys):
            dict_issues.extend(_diff(expected[key], actual[key], f"{path}.{key}"))
        return dict_issues

    if isinstance(expected, list):
        list_issues: list[str] = []
        if len(expected) != len(actual):
            list_issues.append(f"{path}: length mismatch expected={len(expected)} actual={len(actual)}")
            return list_issues
        for idx, (lhs, rhs) in enumerate(zip(expected, actual, strict=True)):
            list_issues.extend(_diff(lhs, rhs, f"{path}[{idx}]"))
        return list_issues

    if expected != actual:
        return [f"{path}: expected={expected!r} actual={actual!r}"]
    return []


def _reset_snapshot_files(output_dir: Path) -> None:
    for path in _snapshot_paths(output_dir).values():
        if path.exists():
            path.unlink()


def build_contract_snapshots(
    output_dir: Path,
    *,
    force_reset: bool = False,
) -> dict[str, dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if force_reset:
        _reset_snapshot_files(output_dir)

    payloads = _build_payloads()
    for key, path in _snapshot_paths(output_dir).items():
        _write_json(path, payloads[key])
    return payloads


def verify_contract_snapshots(output_dir: Path) -> list[str]:
    expected_payloads = _build_payloads()
    issues: list[str] = []
    for key, path in _snapshot_paths(output_dir).items():
        if not path.exists():
            issues.append(f"{key}: snapshot file not found: {path}")
            continue
        actual = _load_json(path)
        issues.extend(_diff(expected_payloads[key], actual, path=key))
    return issues


def main() -> int:
    args = parse_args()
    if args.command == "build":
        payloads = build_contract_snapshots(
            args.output_dir,
            force_reset=args.force_reset,
        )
        print(f"[ok] built contract snapshots: {args.output_dir}")
        print(
            "schema_entities="
            f"{payloads['schema']['stats']['entities']} "
            "rules_total="
            f"{payloads['rules']['stats']['total_rules']} "
            "vectors="
            f"{payloads['vectors']['stats']['vectors']}"
        )
        return 0

    if args.command == "verify":
        issues = verify_contract_snapshots(args.output_dir)
        if not issues:
            print(f"[ok] contract snapshots match: {args.output_dir}")
            return 0

        print(f"[fail] contract snapshots mismatch: {args.output_dir}")
        for issue in issues[:30]:
            print(f"- {issue}")
        if len(issues) > 30:
            print(f"- ... {len(issues) - 30} more")
        return 1

    raise RuntimeError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
