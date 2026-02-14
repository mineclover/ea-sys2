"""Load, validate, and consume ea-kernel contract snapshots."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from ea_kernel_contract.types import (
    DEFAULT_MANAGED_GOVERNANCE_LAYERS,
    ConditionEvaluation,
    ContractBundle,
    ContractIndex,
    ContractModel,
    ContractPaths,
    FeedbackTarget,
    FeedbackTargetType,
    GovernanceLayerCatalog,
    JsonObject,
    RelationshipEvaluation,
)

ENV_CONTRACT_DIR = "EA_KERNEL_CONTRACT_DIR"
ENV_GOVERNANCE_REFERENCE_PATH = "EA_KERNEL_GOVERNANCE_REFERENCE_PATH"

SCHEMA_FILE = "kernel_schema.snapshot.json"
RULES_FILE = "kernel_rules.snapshot.json"
VECTORS_FILE = "kernel_judgment_vectors.snapshot.json"

GOVERNANCE_REFERENCE_FILE = "kernel_governance_reference_v1.snapshot.json"

_LAYER_ORDER: dict[str, int] = {
    "L1": 1,
    "L2": 2,
    "L3": 3,
    "L4": 4,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def default_contract_dir() -> Path:
    """Resolve default snapshot directory.

    Resolution order:
    1) EA_KERNEL_CONTRACT_DIR (environment override)
    2) monorepo default: packages/ea-kernel/docs/reference/contracts
    """
    from_env = os.getenv(ENV_CONTRACT_DIR)
    if from_env:
        return Path(from_env).expanduser().resolve()

    return (_repo_root() / "packages" / "ea-kernel" / "docs" / "reference" / "contracts").resolve()


def default_governance_reference_path() -> Path:
    """Resolve default governance reference snapshot path."""
    from_env = os.getenv(ENV_GOVERNANCE_REFERENCE_PATH)
    if from_env:
        return Path(from_env).expanduser().resolve()

    return (
        _repo_root()
        / "packages"
        / "ea-kernel"
        / "docs"
        / "reference"
        / GOVERNANCE_REFERENCE_FILE
    ).resolve()


def resolve_governance_reference_path(reference_path: Path | None = None) -> Path:
    """Resolve governance reference snapshot path."""
    return (reference_path or default_governance_reference_path()).resolve()


def resolve_contract_paths(contract_dir: Path | None = None) -> ContractPaths:
    """Resolve snapshot file paths for a contract directory."""
    base = (contract_dir or default_contract_dir()).resolve()
    return ContractPaths(
        contract_dir=base,
        schema_path=base / SCHEMA_FILE,
        rules_path=base / RULES_FILE,
        vectors_path=base / VECTORS_FILE,
    )


def _load_json(path: Path) -> JsonObject:
    if not path.exists():
        raise FileNotFoundError(f"contract snapshot not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid contract snapshot payload: {path}")
    return raw


def _as_object(value: Any, *, context: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _require_str(payload: JsonObject, key: str, *, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or len(value.strip()) == 0:
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value


def _require_dict(payload: JsonObject, key: str, *, context: str) -> JsonObject:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{context}.{key} must be an object")
    return value


def _require_list(payload: JsonObject, key: str, *, context: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{context}.{key} must be a list")
    return value


def _require_number(payload: JsonObject, key: str, *, context: str) -> int:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{context}.{key} must be a number")
    return int(value)


def _collect_names(rows: list[Any], *, context: str, issues: list[str]) -> list[str]:
    names: list[str] = []
    for index, row in enumerate(rows):
        row_obj = _as_object(row, context=f"{context}[{index}]")
        try:
            names.append(_require_str(row_obj, "name", context=f"{context}[{index}]"))
        except ValueError as err:
            issues.append(str(err))
    return names


def _find_duplicates(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(sorted(duplicates))


def _pattern_base(pattern: str) -> str:
    return pattern[:-1] if pattern.endswith("*") else pattern


def _is_known_pattern(pattern: str, entities: set[str]) -> bool:
    if pattern == "*":
        return True
    return _pattern_base(pattern) in entities


def load_schema_snapshot(contract_dir: Path | None = None) -> JsonObject:
    paths = resolve_contract_paths(contract_dir)
    return _load_json(paths.schema_path)


def load_rules_snapshot(contract_dir: Path | None = None) -> JsonObject:
    paths = resolve_contract_paths(contract_dir)
    return _load_json(paths.rules_path)


def load_vectors_snapshot(contract_dir: Path | None = None) -> JsonObject:
    paths = resolve_contract_paths(contract_dir)
    return _load_json(paths.vectors_path)


def validate_bundle_shape(bundle: ContractBundle) -> tuple[str, ...]:
    """Validate minimum shape + cross-snapshot integrity."""
    issues: list[str] = []

    schema_version = ""
    rules_version = ""
    vectors_version = ""

    entities_raw: list[Any] = []
    relations_raw: list[Any] = []
    attributes_raw: list[Any] = []
    explicit_rules_raw: list[Any] = []
    fallback_rules_raw: list[Any] = []
    constraints_raw: list[Any] = []
    vectors_raw: list[Any] = []

    # Root shape checks
    try:
        schema_kind = _require_str(bundle.schema, "snapshot_kind", context="schema")
        schema_version = _require_str(bundle.schema, "kernel_version", context="schema")
        _require_dict(bundle.schema, "stats", context="schema")
        attributes_raw = _require_list(bundle.schema, "attributes", context="schema")
        entities_raw = _require_list(bundle.schema, "entities", context="schema")
        relations_raw = _require_list(bundle.schema, "relations", context="schema")
        if schema_kind != "ea_kernel_schema_contract":
            issues.append(f"schema.snapshot_kind unexpected: {schema_kind}")
    except ValueError as err:
        issues.append(str(err))

    try:
        rules_kind = _require_str(bundle.rules, "snapshot_kind", context="rules")
        rules_version = _require_str(bundle.rules, "kernel_version", context="rules")
        _require_dict(bundle.rules, "stats", context="rules")
        explicit_rules_raw = _require_list(bundle.rules, "explicit_rules", context="rules")
        fallback_rules_raw = _require_list(bundle.rules, "fallback_rules", context="rules")
        constraints_raw = _require_list(bundle.rules, "layer_constraints", context="rules")
        if rules_kind != "ea_kernel_rules_contract":
            issues.append(f"rules.snapshot_kind unexpected: {rules_kind}")
    except ValueError as err:
        issues.append(str(err))

    try:
        vectors_kind = _require_str(bundle.vectors, "snapshot_kind", context="vectors")
        vectors_version = _require_str(bundle.vectors, "kernel_version", context="vectors")
        _require_dict(bundle.vectors, "stats", context="vectors")
        vectors_raw = _require_list(bundle.vectors, "vectors", context="vectors")
        if vectors_kind != "ea_kernel_judgment_vectors_contract":
            issues.append(f"vectors.snapshot_kind unexpected: {vectors_kind}")
    except ValueError as err:
        issues.append(str(err))

    # Schema-level integrity
    attribute_names = _collect_names(attributes_raw, context="schema.attributes", issues=issues)
    entity_names = _collect_names(entities_raw, context="schema.entities", issues=issues)
    relation_names = _collect_names(relations_raw, context="schema.relations", issues=issues)

    for duplicate in _find_duplicates(attribute_names):
        issues.append(f"schema.attributes.name duplicated: {duplicate}")
    for duplicate in _find_duplicates(entity_names):
        issues.append(f"schema.entities.name duplicated: {duplicate}")
    for duplicate in _find_duplicates(relation_names):
        issues.append(f"schema.relations.name duplicated: {duplicate}")

    attribute_set = set(attribute_names)
    entity_set = set(entity_names)
    relation_set = set(relation_names)

    for index, row in enumerate(entities_raw):
        row_obj = _as_object(row, context=f"schema.entities[{index}]")
        name = row_obj.get("name")
        if not isinstance(name, str):
            continue

        parent = row_obj.get("parent")
        if parent is not None and not isinstance(parent, str):
            issues.append(f"schema.entities[{index}].parent must be a string")
        if isinstance(parent, str) and parent not in entity_set:
            issues.append(f"schema.entities.parent unknown: {name} -> {parent}")

        owns_key = row_obj.get("owns_key")
        if owns_key is not None and not isinstance(owns_key, str):
            issues.append(f"schema.entities[{index}].owns_key must be a string")
        if isinstance(owns_key, str) and owns_key not in attribute_set:
            issues.append(f"schema.entities.owns_key unknown attribute: {name} -> {owns_key}")

        owns = row_obj.get("owns", [])
        if not isinstance(owns, list):
            issues.append(f"schema.entities[{index}].owns must be a list")
        else:
            for own_index, own in enumerate(owns):
                if not isinstance(own, str):
                    issues.append(f"schema.entities[{index}].owns[{own_index}] must be a string")
                elif own not in attribute_set:
                    issues.append(f"schema.entities.owns unknown attribute: {name} -> {own}")

        plays = row_obj.get("plays", [])
        if not isinstance(plays, list):
            issues.append(f"schema.entities[{index}].plays must be a list")

    for index, row in enumerate(relations_raw):
        row_obj = _as_object(row, context=f"schema.relations[{index}]")
        name = row_obj.get("name")
        if not isinstance(name, str):
            continue

        parent = row_obj.get("parent")
        if parent is not None and not isinstance(parent, str):
            issues.append(f"schema.relations[{index}].parent must be a string")
        if isinstance(parent, str) and parent not in relation_set:
            issues.append(f"schema.relations.parent unknown: {name} -> {parent}")

        owns_key = row_obj.get("owns_key")
        if owns_key is not None and not isinstance(owns_key, str):
            issues.append(f"schema.relations[{index}].owns_key must be a string")
        if isinstance(owns_key, str) and owns_key not in attribute_set:
            issues.append(f"schema.relations.owns_key unknown attribute: {name} -> {owns_key}")

        owns = row_obj.get("owns", [])
        if not isinstance(owns, list):
            issues.append(f"schema.relations[{index}].owns must be a list")
        else:
            for own_index, own in enumerate(owns):
                if not isinstance(own, str):
                    issues.append(f"schema.relations[{index}].owns[{own_index}] must be a string")
                elif own not in attribute_set:
                    issues.append(f"schema.relations.owns unknown attribute: {name} -> {own}")

        roles = row_obj.get("roles", [])
        if not isinstance(roles, list):
            issues.append(f"schema.relations[{index}].roles must be a list")
        else:
            for role_index, role in enumerate(roles):
                if not isinstance(role, dict):
                    issues.append(f"schema.relations[{index}].roles[{role_index}] must be an object")
                    continue
                player = role.get("player")
                if not isinstance(player, str):
                    issues.append(
                        f"schema.relations[{index}].roles[{role_index}].player must be a string"
                    )
                elif player not in entity_set:
                    issues.append(
                        f"schema.relations.roles.player unknown entity: {name} -> {player}"
                    )

    # Rules-level integrity
    all_rules: list[JsonObject] = []
    rule_ids: list[str] = []
    fallback_relations: list[str] = []

    def _collect_rule(row: Any, *, context: str, is_fallback: bool) -> None:
        row_obj = _as_object(row, context=context)
        rule_id = row_obj.get("id")
        relation = row_obj.get("relation")
        source_pattern = row_obj.get("source_pattern")
        target_pattern = row_obj.get("target_pattern")
        if isinstance(rule_id, str):
            rule_ids.append(rule_id)
        else:
            issues.append(f"{context}.id must be a string")
        if isinstance(relation, str):
            if relation not in relation_set:
                issues.append(f"{context}.relation unknown relation: {relation}")
            if is_fallback:
                fallback_relations.append(relation)
        else:
            issues.append(f"{context}.relation must be a string")
        if isinstance(source_pattern, str):
            if not _is_known_pattern(source_pattern, entity_set):
                issues.append(f"{context}.source_pattern unknown: {source_pattern}")
        else:
            issues.append(f"{context}.source_pattern must be a string")
        if isinstance(target_pattern, str):
            if not _is_known_pattern(target_pattern, entity_set):
                issues.append(f"{context}.target_pattern unknown: {target_pattern}")
        else:
            issues.append(f"{context}.target_pattern must be a string")

        conditions = row_obj.get("conditions", [])
        if not isinstance(conditions, list):
            issues.append(f"{context}.conditions must be a list")
        all_rules.append(row_obj)

    for index, row in enumerate(explicit_rules_raw):
        _collect_rule(row, context=f"rules.explicit_rules[{index}]", is_fallback=False)
    for index, row in enumerate(fallback_rules_raw):
        _collect_rule(row, context=f"rules.fallback_rules[{index}]", is_fallback=True)

    for duplicate in _find_duplicates(rule_ids):
        issues.append(f"rules.rule.id duplicated: {duplicate}")
    for duplicate in _find_duplicates(fallback_relations):
        issues.append(f"rules.fallback_rules.relation duplicated: {duplicate}")

    constraint_ids: list[str] = []
    for index, row in enumerate(constraints_raw):
        row_obj = _as_object(row, context=f"rules.layer_constraints[{index}]")
        cid = row_obj.get("id")
        if isinstance(cid, str):
            constraint_ids.append(cid)
        else:
            issues.append(f"rules.layer_constraints[{index}].id must be a string")
            cid = f"<unknown:{index}>"

        forbidden_relations = row_obj.get("forbidden_relations", [])
        if not isinstance(forbidden_relations, list):
            issues.append(f"rules.layer_constraints[{index}].forbidden_relations must be a list")
        else:
            for rel_index, rel in enumerate(forbidden_relations):
                if not isinstance(rel, str):
                    issues.append(
                        f"rules.layer_constraints[{index}].forbidden_relations[{rel_index}] must be a string"
                    )
                elif rel not in relation_set:
                    issues.append(
                        f"rules.layer_constraints.forbidden_relations unknown relation: {cid} -> {rel}"
                    )

        allowed_pairs = row_obj.get("allowed_pairs", [])
        if not isinstance(allowed_pairs, list):
            issues.append(f"rules.layer_constraints[{index}].allowed_pairs must be a list")
        else:
            for pair_index, pair in enumerate(allowed_pairs):
                if not isinstance(pair, list) or len(pair) != 2:
                    issues.append(
                        f"rules.layer_constraints[{index}].allowed_pairs[{pair_index}] must contain 2 items"
                    )
                    continue
                source_pattern, target_pattern = pair
                if not isinstance(source_pattern, str) or not isinstance(target_pattern, str):
                    issues.append(
                        f"rules.layer_constraints[{index}].allowed_pairs[{pair_index}] must contain strings"
                    )
                    continue
                if not _is_known_pattern(source_pattern, entity_set):
                    issues.append(
                        f"rules.layer_constraints.allowed_pairs source unknown: {cid} -> {source_pattern}"
                    )
                if not _is_known_pattern(target_pattern, entity_set):
                    issues.append(
                        f"rules.layer_constraints.allowed_pairs target unknown: {cid} -> {target_pattern}"
                    )

    for duplicate in _find_duplicates(constraint_ids):
        issues.append(f"rules.layer_constraints.id duplicated: {duplicate}")

    vector_ids: list[str] = []
    rule_id_set = set(rule_ids)
    for index, row in enumerate(vectors_raw):
        row_obj = _as_object(row, context=f"vectors.vectors[{index}]")
        vector_id = row_obj.get("id")
        if isinstance(vector_id, str):
            vector_ids.append(vector_id)
        else:
            issues.append(f"vectors.vectors[{index}].id must be a string")

        triple = row_obj.get("triple")
        if not isinstance(triple, list) or len(triple) != 3:
            issues.append(f"vectors.vectors[{index}].triple must contain 3 items")
        else:
            source, target, relation = triple
            if not isinstance(source, str) or source not in entity_set:
                issues.append(f"vectors.triple source unknown: {vector_id} -> {source}")
            if not isinstance(target, str) or target not in entity_set:
                issues.append(f"vectors.triple target unknown: {vector_id} -> {target}")
            if not isinstance(relation, str) or relation not in relation_set:
                issues.append(f"vectors.triple relation unknown: {vector_id} -> {relation}")

        winner = row_obj.get("expected_winner_rule_id")
        if winner is not None:
            if not isinstance(winner, str):
                issues.append(
                    f"vectors.vectors[{index}].expected_winner_rule_id must be string or null"
                )
            elif winner not in rule_id_set:
                issues.append(f"vectors.expected_winner_rule_id unknown: {vector_id} -> {winner}")

    for duplicate in _find_duplicates(vector_ids):
        issues.append(f"vectors.vectors.id duplicated: {duplicate}")

    # Stats consistency
    try:
        schema_stats = _require_dict(bundle.schema, "stats", context="schema")
        if _require_number(schema_stats, "attributes", context="schema.stats") != len(attributes_raw):
            issues.append(
                "schema.stats.attributes mismatch: "
                f"expected={schema_stats.get('attributes')} actual={len(attributes_raw)}"
            )
        if _require_number(schema_stats, "entities", context="schema.stats") != len(entities_raw):
            issues.append(
                "schema.stats.entities mismatch: "
                f"expected={schema_stats.get('entities')} actual={len(entities_raw)}"
            )
        if _require_number(schema_stats, "relations", context="schema.stats") != len(relations_raw):
            issues.append(
                "schema.stats.relations mismatch: "
                f"expected={schema_stats.get('relations')} actual={len(relations_raw)}"
            )
    except ValueError as err:
        issues.append(str(err))

    try:
        rules_stats = _require_dict(bundle.rules, "stats", context="rules")
        if _require_number(rules_stats, "explicit_rules", context="rules.stats") != len(explicit_rules_raw):
            issues.append(
                "rules.stats.explicit_rules mismatch: "
                f"expected={rules_stats.get('explicit_rules')} actual={len(explicit_rules_raw)}"
            )
        if _require_number(rules_stats, "fallback_rules", context="rules.stats") != len(fallback_rules_raw):
            issues.append(
                "rules.stats.fallback_rules mismatch: "
                f"expected={rules_stats.get('fallback_rules')} actual={len(fallback_rules_raw)}"
            )
        if _require_number(rules_stats, "layer_constraints", context="rules.stats") != len(constraints_raw):
            issues.append(
                "rules.stats.layer_constraints mismatch: "
                f"expected={rules_stats.get('layer_constraints')} actual={len(constraints_raw)}"
            )
        if _require_number(rules_stats, "total_rules", context="rules.stats") != len(all_rules):
            issues.append(
                "rules.stats.total_rules mismatch: "
                f"expected={rules_stats.get('total_rules')} actual={len(all_rules)}"
            )
        metadata_entries = 0
        for rule in explicit_rules_raw:
            if isinstance(rule, dict) and isinstance(rule.get("metadata"), dict):
                metadata_entries += 1
        if _require_number(rules_stats, "metadata_entries", context="rules.stats") != metadata_entries:
            issues.append(
                "rules.stats.metadata_entries mismatch: "
                f"expected={rules_stats.get('metadata_entries')} actual={metadata_entries}"
            )
    except ValueError as err:
        issues.append(str(err))

    try:
        vectors_stats = _require_dict(bundle.vectors, "stats", context="vectors")
        vectors_count = len(vectors_raw)
        if _require_number(vectors_stats, "vectors", context="vectors.stats") != vectors_count:
            issues.append(
                "vectors.stats.vectors mismatch: "
                f"expected={vectors_stats.get('vectors')} actual={vectors_count}"
            )
        allow_vectors = 0
        for row in vectors_raw:
            if isinstance(row, dict) and row.get("expected_verdict") is True:
                allow_vectors += 1
        deny_vectors = vectors_count - allow_vectors
        if _require_number(vectors_stats, "allow_vectors", context="vectors.stats") != allow_vectors:
            issues.append(
                "vectors.stats.allow_vectors mismatch: "
                f"expected={vectors_stats.get('allow_vectors')} actual={allow_vectors}"
            )
        if _require_number(vectors_stats, "deny_vectors", context="vectors.stats") != deny_vectors:
            issues.append(
                "vectors.stats.deny_vectors mismatch: "
                f"expected={vectors_stats.get('deny_vectors')} actual={deny_vectors}"
            )
    except ValueError as err:
        issues.append(str(err))

    versions = {value for value in (schema_version, rules_version, vectors_version) if value}
    if len(versions) > 1:
        issues.append(f"kernel_version mismatch across snapshots: {sorted(versions)}")

    return tuple(issues)


def load_contract_bundle(
    contract_dir: Path | None = None,
    *,
    validate_shape: bool = True,
) -> ContractBundle:
    """Load all contract snapshots and optionally validate shape+integrity."""
    paths = resolve_contract_paths(contract_dir)
    bundle = ContractBundle(
        paths=paths,
        schema=_load_json(paths.schema_path),
        rules=_load_json(paths.rules_path),
        vectors=_load_json(paths.vectors_path),
    )
    if validate_shape:
        issues = validate_bundle_shape(bundle)
        if issues:
            joined = "; ".join(issues)
            raise ValueError(f"invalid contract bundle: {joined}")
    return bundle


def contract_fingerprint(bundle: ContractBundle) -> str:
    """Compute deterministic SHA-256 fingerprint from snapshot file bytes."""
    digest = hashlib.sha256()
    for file_path in (
        bundle.paths.schema_path,
        bundle.paths.rules_path,
        bundle.paths.vectors_path,
    ):
        digest.update(file_path.name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(file_path.read_bytes())
        digest.update(b"\x00")
    return digest.hexdigest()


def _require_row_dict(row: Any, *, context: str) -> JsonObject:
    if not isinstance(row, dict):
        raise ValueError(f"{context} must be an object")
    return row


def _as_row_list(payload: JsonObject, key: str, *, context: str) -> list[JsonObject]:
    rows = _require_list(payload, key, context=context)
    result: list[JsonObject] = []
    for index, row in enumerate(rows):
        result.append(_require_row_dict(row, context=f"{context}.{key}[{index}]"))
    return result


def build_contract_index(bundle: ContractBundle) -> ContractIndex:
    """Build lookup maps for fast consumer-side resolution."""
    entities = _as_row_list(bundle.schema, "entities", context="schema")
    relations = _as_row_list(bundle.schema, "relations", context="schema")
    attributes = _as_row_list(bundle.schema, "attributes", context="schema")
    explicit_rules = _as_row_list(bundle.rules, "explicit_rules", context="rules")
    fallback_rules = _as_row_list(bundle.rules, "fallback_rules", context="rules")
    constraints = _as_row_list(bundle.rules, "layer_constraints", context="rules")
    vectors = _as_row_list(bundle.vectors, "vectors", context="vectors")

    return ContractIndex(
        entity_by_name={str(row["name"]): row for row in entities if "name" in row},
        relation_by_name={str(row["name"]): row for row in relations if "name" in row},
        attribute_by_name={str(row["name"]): row for row in attributes if "name" in row},
        rule_by_id={
            str(row["id"]): row
            for row in [*explicit_rules, *fallback_rules]
            if "id" in row
        },
        fallback_rule_by_relation={
            str(row["relation"]): row for row in fallback_rules if "relation" in row
        },
        layer_constraint_by_id={
            str(row["id"]): row for row in constraints if "id" in row
        },
        vector_by_id={str(row["id"]): row for row in vectors if "id" in row},
    )


def build_contract_model(
    contract_dir: Path | None = None,
    *,
    validate_shape: bool = True,
) -> ContractModel:
    """Load+validate bundle then build index and fingerprint."""
    bundle = load_contract_bundle(contract_dir, validate_shape=validate_shape)
    return ContractModel(
        bundle=bundle,
        index=build_contract_index(bundle),
        fingerprint=contract_fingerprint(bundle),
    )


def make_feedback_target(target_type: FeedbackTargetType, target_id: str) -> FeedbackTarget:
    """Build canonical feedback target id pair."""
    tid = target_id.strip()
    if len(tid) == 0:
        raise ValueError("feedback target_id cannot be empty")
    return FeedbackTarget(
        target_type=target_type,
        target_id=tid,
        canonical_id=f"{target_type}:{tid}",
    )


def parse_feedback_target(raw: str) -> FeedbackTarget:
    """Parse `type:id` feedback target string into typed structure."""
    value = raw.strip()
    parts = value.split(":", maxsplit=1)
    if len(parts) != 2 or len(parts[0]) == 0 or len(parts[1]) == 0:
        raise ValueError(f"invalid feedback target format: {raw}")

    target_type_raw, target_id = parts
    if target_type_raw not in {
        "entity_type",
        "relation_type",
        "rule",
        "layer_constraint",
    }:
        raise ValueError(f"unsupported feedback target type: {target_type_raw}")

    return make_feedback_target(target_type_raw, target_id)


def resolve_feedback_target(raw: str, model: ContractModel) -> FeedbackTarget:
    """Validate feedback target exists in the loaded contract model."""
    target = parse_feedback_target(raw)

    if target.target_type == "entity_type":
        if target.target_id not in model.index.entity_by_name:
            raise ValueError(f"unknown entity_type target: {target.target_id}")
    elif target.target_type == "relation_type":
        if target.target_id not in model.index.relation_by_name:
            raise ValueError(f"unknown relation_type target: {target.target_id}")
    elif target.target_type == "rule":
        if target.target_id not in model.index.rule_by_id:
            raise ValueError(f"unknown rule target: {target.target_id}")
    elif target.target_type == "layer_constraint":
        if target.target_id not in model.index.layer_constraint_by_id:
            raise ValueError(f"unknown layer_constraint target: {target.target_id}")

    return target


def list_feedback_targets(
    model: ContractModel,
    target_type: FeedbackTargetType | None = None,
) -> tuple[FeedbackTarget, ...]:
    """List all canonical feedback targets or a filtered target type."""
    targets: list[FeedbackTarget] = []

    if target_type is None or target_type == "entity_type":
        for name in model.index.entity_by_name:
            targets.append(make_feedback_target("entity_type", name))

    if target_type is None or target_type == "relation_type":
        for name in model.index.relation_by_name:
            targets.append(make_feedback_target("relation_type", name))

    if target_type is None or target_type == "rule":
        for rule_id in model.index.rule_by_id:
            targets.append(make_feedback_target("rule", rule_id))

    if target_type is None or target_type == "layer_constraint":
        for constraint_id in model.index.layer_constraint_by_id:
            targets.append(make_feedback_target("layer_constraint", constraint_id))

    targets.sort(key=lambda item: item.canonical_id)
    return tuple(targets)


def list_entity_ancestors(model: ContractModel, entity_name: str) -> tuple[str, ...]:
    """Return entity ancestor names from parent to root."""
    if entity_name not in model.index.entity_by_name:
        raise ValueError(f"unknown entity type: {entity_name}")

    ancestors: list[str] = []
    seen: set[str] = set()
    cursor = model.index.entity_by_name[entity_name]

    while True:
        parent = cursor.get("parent")
        if parent is None:
            break
        if not isinstance(parent, str):
            raise ValueError(f"invalid parent value on entity '{entity_name}'")
        if parent in seen:
            raise ValueError(f"entity parent cycle detected: {parent}")
        if parent not in model.index.entity_by_name:
            raise ValueError(f"unknown parent entity: {parent}")
        seen.add(parent)
        ancestors.append(parent)
        cursor = model.index.entity_by_name[parent]

    return tuple(ancestors)


def entity_matches_pattern(model: ContractModel, entity_name: str, pattern: str) -> bool:
    """Kernel pattern matcher: *, type*, exact-name."""
    if pattern == "*":
        return entity_name in model.index.entity_by_name
    if pattern.endswith("*"):
        base = pattern[:-1]
        if entity_name == base:
            return True
        return base in set(list_entity_ancestors(model, entity_name))
    return entity_name == pattern


def get_entity_required_keys(model: ContractModel, entity_name: str) -> tuple[str, ...]:
    """Resolve owns_key + owns across full ancestor chain."""
    if entity_name not in model.index.entity_by_name:
        raise ValueError(f"unknown entity type: {entity_name}")

    lineage: list[JsonObject] = []
    cursor = model.index.entity_by_name[entity_name]
    lineage.append(cursor)
    while True:
        parent = cursor.get("parent")
        if parent is None:
            break
        if not isinstance(parent, str) or parent not in model.index.entity_by_name:
            raise ValueError(f"invalid parent chain for entity type: {entity_name}")
        cursor = model.index.entity_by_name[parent]
        lineage.append(cursor)

    required: list[str] = []
    for row in reversed(lineage):
        owns_key = row.get("owns_key")
        if isinstance(owns_key, str) and owns_key not in required:
            required.append(owns_key)

        owns = row.get("owns", [])
        if isinstance(owns, list):
            for key in owns:
                if isinstance(key, str) and key not in required:
                    required.append(key)

    return tuple(required)


def find_matching_rules(
    model: ContractModel,
    source_entity: str,
    target_entity: str,
    relation: str,
) -> tuple[JsonObject, ...]:
    """Find all matching rules sorted by priority(desc), deny-first tie-break."""
    rules = [
        *model.bundle.rules.get("explicit_rules", []),
        *model.bundle.rules.get("fallback_rules", []),
    ]

    matched: list[JsonObject] = []
    for row in rules:
        if not isinstance(row, dict):
            continue
        if row.get("relation") != relation:
            continue

        source_pattern = row.get("source_pattern")
        target_pattern = row.get("target_pattern")
        if not isinstance(source_pattern, str) or not isinstance(target_pattern, str):
            continue

        if not entity_matches_pattern(model, source_entity, source_pattern):
            continue
        if not entity_matches_pattern(model, target_entity, target_pattern):
            continue

        matched.append(row)

    matched.sort(
        key=lambda rule: (
            int(rule.get("priority", 0)),
            not bool(rule.get("valid", True)),
        ),
        reverse=True,
    )
    return tuple(matched)


def _evaluate_condition(
    model: ContractModel,
    condition: JsonObject,
    source_entity: str,
    target_entity: str,
) -> ConditionEvaluation:
    condition_type = str(condition.get("type", ""))

    source = model.index.entity_by_name.get(source_entity)
    target = model.index.entity_by_name.get(target_entity)
    if source is None or target is None:
        return ConditionEvaluation(
            condition_type=condition_type,
            passed=False,
            note="entity not found",
        )

    source_layer = source.get("layer")
    target_layer = target.get("layer")

    if condition_type == "same_layer":
        passed = source_layer == target_layer
        return ConditionEvaluation(
            condition_type=condition_type,
            passed=passed,
            note=f"{source_entity}.layer={source_layer} vs {target_entity}.layer={target_layer}",
        )

    if condition_type == "layer_order":
        source_order = _LAYER_ORDER.get(str(source_layer))
        target_order = _LAYER_ORDER.get(str(target_layer))
        if source_order is None or target_order is None:
            return ConditionEvaluation(
                condition_type=condition_type,
                passed=False,
                note="unknown layer value",
            )
        passed = source_order <= target_order
        return ConditionEvaluation(
            condition_type=condition_type,
            passed=passed,
            note=f"{source_entity}(L{source_order}) <= {target_entity}(L{target_order})",
        )

    if condition_type == "ancestor_of":
        passed = source_entity in set(list_entity_ancestors(model, target_entity))
        return ConditionEvaluation(
            condition_type=condition_type,
            passed=passed,
            note=f"{source_entity} {'is' if passed else 'is not'} ancestor of {target_entity}",
        )

    if condition_type == "same_category":
        return ConditionEvaluation(
            condition_type=condition_type,
            passed=True,
            note="same_category is profile-level only (skipped at kernel)",
        )

    if condition_type == "same_branch":
        source_chain = {source_entity, *list_entity_ancestors(model, source_entity)}
        target_chain = {target_entity, *list_entity_ancestors(model, target_entity)}
        shared = source_chain & target_chain
        shared_non_root = {
            name
            for name in shared
            if isinstance(model.index.entity_by_name.get(name, {}).get("parent"), str)
        }
        passed = len(shared_non_root) > 0
        names = ", ".join(sorted(shared_non_root)) if shared_non_root else "none"
        return ConditionEvaluation(
            condition_type=condition_type,
            passed=passed,
            note=f"shared non-root ancestors: {names}",
        )

    return ConditionEvaluation(
        condition_type=condition_type,
        passed=False,
        note=f"unknown condition type: {condition_type}",
    )


def evaluate_relationship(
    model: ContractModel,
    source_entity: str,
    target_entity: str,
    relation: str,
) -> RelationshipEvaluation:
    """Evaluate relation triple with layer constraints and winner rule details."""
    source = model.index.entity_by_name.get(source_entity)
    if source is None:
        return RelationshipEvaluation(
            allowed=False,
            reason="unknown_entity",
            winner_rule_id=None,
            matched_rule_ids=(),
            blocking_constraint_id=None,
            condition_checks=(),
            notes=f"unknown entity: {source_entity}",
        )

    target = model.index.entity_by_name.get(target_entity)
    if target is None:
        return RelationshipEvaluation(
            allowed=False,
            reason="unknown_entity",
            winner_rule_id=None,
            matched_rule_ids=(),
            blocking_constraint_id=None,
            condition_checks=(),
            notes=f"unknown entity: {target_entity}",
        )

    if relation not in model.index.relation_by_name:
        return RelationshipEvaluation(
            allowed=False,
            reason="unknown_relation",
            winner_rule_id=None,
            matched_rule_ids=(),
            blocking_constraint_id=None,
            condition_checks=(),
            notes=f"unknown relation: {relation}",
        )

    source_layer = source.get("layer")
    target_layer = target.get("layer")

    constraints = model.bundle.rules.get("layer_constraints", [])
    if isinstance(constraints, list):
        for row in constraints:
            if not isinstance(row, dict):
                continue

            forbidden = row.get("forbidden_relations", [])
            if not isinstance(forbidden, list) or relation not in forbidden:
                continue

            if row.get("source_layer") != source_layer or row.get("target_layer") != target_layer:
                continue

            exempt = False
            allowed_pairs = row.get("allowed_pairs", [])
            if isinstance(allowed_pairs, list):
                for pair in allowed_pairs:
                    if not isinstance(pair, list) or len(pair) != 2:
                        continue
                    source_pattern, target_pattern = pair
                    if not isinstance(source_pattern, str) or not isinstance(target_pattern, str):
                        continue
                    if entity_matches_pattern(model, source_entity, source_pattern) and entity_matches_pattern(
                        model,
                        target_entity,
                        target_pattern,
                    ):
                        exempt = True
                        break

            if not exempt:
                cid = row.get("id")
                constraint_id = cid if isinstance(cid, str) else None
                notes = row.get("notes")
                if not isinstance(notes, str) or len(notes.strip()) == 0:
                    notes = (
                        "layer constraint: "
                        f"{source_layer} entities cannot use {relation} "
                        f"with {target_layer} entities"
                    )
                return RelationshipEvaluation(
                    allowed=False,
                    reason="constraint_denied",
                    winner_rule_id=None,
                    matched_rule_ids=(),
                    blocking_constraint_id=constraint_id,
                    condition_checks=(),
                    notes=notes,
                )

    matched = find_matching_rules(model, source_entity, target_entity, relation)
    if len(matched) == 0:
        return RelationshipEvaluation(
            allowed=False,
            reason="no_matching_rule",
            winner_rule_id=None,
            matched_rule_ids=(),
            blocking_constraint_id=None,
            condition_checks=(),
            notes="no matching rule (deny-by-default)",
        )

    winner = matched[0]
    winner_rule_id = winner.get("id") if isinstance(winner.get("id"), str) else None

    checks: list[ConditionEvaluation] = []
    conditions = winner.get("conditions", [])
    if isinstance(conditions, list):
        for row in conditions:
            if isinstance(row, dict):
                checks.append(_evaluate_condition(model, row, source_entity, target_entity))

    failed = next((row for row in checks if not row.passed), None)
    if failed is not None:
        return RelationshipEvaluation(
            allowed=False,
            reason="condition_failed",
            winner_rule_id=winner_rule_id,
            matched_rule_ids=tuple(
                str(row.get("id"))
                for row in matched
                if isinstance(row, dict) and isinstance(row.get("id"), str)
            ),
            blocking_constraint_id=None,
            condition_checks=tuple(checks),
            notes=f"condition failed: {failed.note}",
        )

    verdict = winner.get("valid")
    allowed = bool(verdict) if isinstance(verdict, bool) else False
    winner_notes = winner.get("notes")
    notes = winner_notes if isinstance(winner_notes, str) else ""

    return RelationshipEvaluation(
        allowed=allowed,
        reason="rule_verdict",
        winner_rule_id=winner_rule_id,
        matched_rule_ids=tuple(
            str(row.get("id"))
            for row in matched
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        ),
        blocking_constraint_id=None,
        condition_checks=tuple(checks),
        notes=notes,
    )


def load_governance_reference_snapshot(reference_path: Path | None = None) -> JsonObject:
    """Load governance reference snapshot used to manage layer models."""
    path = resolve_governance_reference_path(reference_path)
    payload = _load_json(path)

    kind = payload.get("snapshot_kind")
    if kind != "kernel_governance_db_reference":
        raise ValueError(f"unexpected governance snapshot_kind: {kind!r}")
    return payload


def build_governance_layer_catalog(
    reference_path: Path | None = None,
    *,
    expected_managed_layers: tuple[str, ...] = DEFAULT_MANAGED_GOVERNANCE_LAYERS,
) -> GovernanceLayerCatalog:
    """Build layer-model catalog with expected 5 managed governance layers."""
    path = resolve_governance_reference_path(reference_path)
    snapshot = load_governance_reference_snapshot(path)

    seed_profiles = snapshot.get("seed_profiles")
    if not isinstance(seed_profiles, list):
        raise ValueError("governance snapshot seed_profiles must be a list")

    profile_by_layer: dict[str, str] = {}
    layer_order: list[str] = []

    for index, row in enumerate(seed_profiles):
        if not isinstance(row, dict):
            raise ValueError(f"seed_profiles[{index}] must be an object")

        layer = row.get("layer")
        model_name = row.get("model_name")
        if not isinstance(layer, str) or len(layer.strip()) == 0:
            raise ValueError(f"seed_profiles[{index}].layer must be a non-empty string")
        if not isinstance(model_name, str) or len(model_name.strip()) == 0:
            raise ValueError(f"seed_profiles[{index}].model_name must be a non-empty string")

        if layer not in profile_by_layer:
            profile_by_layer[layer] = model_name
            layer_order.append(layer)

    layers = tuple(layer_order)
    layer_set = set(layers)
    expected = tuple(expected_managed_layers)

    managed_layers = tuple(layer for layer in expected if layer in layer_set)
    missing_managed = tuple(layer for layer in expected if layer not in layer_set)
    unexpected_layers = tuple(
        sorted(layer for layer in layer_set if layer not in set(expected) and layer != "governance")
    )

    profile_models = tuple((layer, profile_by_layer[layer]) for layer in layers)

    return GovernanceLayerCatalog(
        reference_path=path,
        layers=layers,
        profile_models=profile_models,
        expected_managed_layers=expected,
        managed_layers=managed_layers,
        missing_managed_layers=missing_managed,
        unexpected_layers=unexpected_layers,
        governance_layer_present="governance" in layer_set,
    )


def validate_governance_layer_catalog(catalog: GovernanceLayerCatalog) -> tuple[str, ...]:
    """Validate governance layer coverage for managed 5-layer operation."""
    issues: list[str] = []

    if len(catalog.expected_managed_layers) != 5:
        issues.append(
            "expected_managed_layers should contain 5 layers "
            f"(actual={len(catalog.expected_managed_layers)})"
        )

    if len(catalog.missing_managed_layers) > 0:
        issues.append(
            "missing managed governance layers: "
            + ", ".join(catalog.missing_managed_layers)
        )

    if not catalog.governance_layer_present:
        issues.append("governance layer profile is missing from seed_profiles")

    return tuple(issues)
