"""Core representation types for the kernel metamodel."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ea_kernel.profile_types import ProfileRule, RuleCondition

# Multi-language string: either a simple string or a mapping of language codes to strings
I18nString = str | dict[str, str]


class Layer(StrEnum):
    """The 4-layer progressive abstraction."""
    L1 = "L1"  # Structure
    L2 = "L2"  # Relationship
    L3 = "L3"  # Behavioral
    L4 = "L4"  # Concrete


LAYER_ORDER: dict[Layer, int] = {
    Layer.L1: 1, Layer.L2: 2, Layer.L3: 3, Layer.L4: 4,
}


class SchemaType(StrEnum):
    DEFINE = "define"
    INSERT = "insert"


class KernelConditionType(StrEnum):
    SAME_LAYER = "same_layer"
    LAYER_ORDER = "layer_order"
    ANCESTOR_OF = "ancestor_of"
    SAME_ENTITY_BRANCH = "same_branch"
    SAME_CATEGORY = "same_category"  # profile-level condition


@dataclass(frozen=True)
class KernelRuleCondition(RuleCondition):
    """Kernel-specific rule condition.

    Inherits from RuleCondition (kernel-agnostic). condition_type accepts
    KernelConditionType values (StrEnum, hence valid str).
    """


@dataclass(frozen=True)
class KernelValidityRule(ProfileRule):
    """Kernel-specific validity rule.

    Inherits from ProfileRule (kernel-agnostic). conditions accepts
    KernelRuleCondition instances (which are RuleCondition subclasses).
    """


@dataclass(frozen=True)
class LayerConstraint:
    """Declares that entities in source_layer cannot use specified L2 relations
    with entities in target_layer, except for allowed pairs."""
    id: str
    source_layer: Layer
    target_layer: Layer
    forbidden_relations: tuple[str, ...]
    allowed_pairs: tuple[tuple[str, str], ...] = ()  # (source_pattern, target_pattern) exceptions
    priority: int = 90
    notes: str = ""


@dataclass(frozen=True)
class KernelValidationResult:
    valid: bool
    rule_id: str | None = None
    notes: str | None = None
    source_entity: str | None = None
    target_entity: str | None = None
    relationship_name: str | None = None


@dataclass(frozen=True)
class SchemaFile:
    """Metadata for a TypeDB schema file."""
    filename: str
    order: int
    schema_type: SchemaType
    description: str


@dataclass(frozen=True)
class KernelAttribute:
    """An attribute definition in the kernel schema."""
    name: str
    value_type: str  # string | long | boolean | double | datetime


@dataclass(frozen=True)
class KernelRole:
    """A role in a relation."""
    name: str
    player: str  # entity type that plays this role


@dataclass(frozen=True)
class KernelEntity:
    """An entity type in the kernel schema."""
    name: str
    layer: Layer
    parent: str | None = None
    is_abstract: bool = False
    owns: tuple[str, ...] = ()
    owns_key: str | None = None
    plays: tuple[str, ...] = ()  # "relation_name:role_name" format
    description: I18nString = ""
    display_name: I18nString = ""


@dataclass(frozen=True)
class KernelRelation:
    """A relation type in the kernel schema."""
    name: str
    layer: Layer
    parent: str | None = None
    roles: tuple[KernelRole, ...] = ()
    owns: tuple[str, ...] = ()
    owns_key: str | None = None
    description: I18nString = ""
    display_name: I18nString = ""


@dataclass(frozen=True)
class KernelSchema:
    """Complete kernel schema definition."""
    attributes: tuple[KernelAttribute, ...]
    entities: tuple[KernelEntity, ...]
    relations: tuple[KernelRelation, ...]
    validity_rules: tuple[KernelValidityRule, ...] = ()
    layer_constraints: tuple[LayerConstraint, ...] = ()
    _rules_by_rel: dict[str, tuple[KernelValidityRule, ...]] = field(
        default_factory=dict, init=False, repr=False, compare=False,
    )
    _entity_by_name: dict[str, KernelEntity] = field(
        default_factory=dict, init=False, repr=False, compare=False,
    )
    _relation_by_name: dict[str, KernelRelation] = field(
        default_factory=dict, init=False, repr=False, compare=False,
    )
    _ancestors: dict[str, tuple[str, ...]] = field(
        default_factory=dict, init=False, repr=False, compare=False,
    )
    _pattern_matches: dict[str, frozenset[str]] = field(
        default_factory=dict, init=False, repr=False, compare=False,
    )

    def __post_init__(self) -> None:
        # Rule index by relationship name
        rule_idx: dict[str, list[KernelValidityRule]] = {}
        for rule in self.validity_rules:
            rule_idx.setdefault(rule.relationship_name, []).append(rule)
        object.__setattr__(self, '_rules_by_rel', {
            k: tuple(v) for k, v in rule_idx.items()
        })

        # Entity index by name — O(1) lookup
        entity_idx: dict[str, KernelEntity] = {}
        for e in self.entities:
            entity_idx[e.name] = e
        object.__setattr__(self, '_entity_by_name', entity_idx)

        # Relation index by name — O(1) lookup
        relation_idx: dict[str, KernelRelation] = {}
        for r in self.relations:
            relation_idx[r.name] = r
        object.__setattr__(self, '_relation_by_name', relation_idx)

        # Pre-compute ancestor chains
        ancestors: dict[str, tuple[str, ...]] = {}
        for e in self.entities:
            chain: list[str] = []
            current = e
            while current and current.parent:
                chain.append(current.parent)
                current = entity_idx.get(current.parent)  # type: ignore[assignment]
            ancestors[e.name] = tuple(chain)
        object.__setattr__(self, '_ancestors', ancestors)

        # Pre-compute pattern matches — collect all patterns from rules
        patterns: set[str] = set()
        for rule in self.validity_rules:
            patterns.add(rule.source_pattern)
            patterns.add(rule.target_pattern)
        for lc in self.layer_constraints:
            for ap_src, ap_tgt in lc.allowed_pairs:
                patterns.add(ap_src)
                patterns.add(ap_tgt)

        pattern_matches: dict[str, frozenset[str]] = {}
        for pattern in patterns:
            if pattern == "*":
                pattern_matches[pattern] = frozenset(entity_idx.keys())
            elif pattern.endswith("*"):
                base = pattern[:-1]
                matching = set()
                for name in entity_idx:
                    if name == base or base in ancestors.get(name, ()):
                        matching.add(name)
                pattern_matches[pattern] = frozenset(matching)
            else:
                # Exact match — only if entity exists
                if pattern in entity_idx:
                    pattern_matches[pattern] = frozenset({pattern})
                else:
                    pattern_matches[pattern] = frozenset()
        object.__setattr__(self, '_pattern_matches', pattern_matches)

    def get_entity(self, name: str) -> KernelEntity | None:
        return self._entity_by_name.get(name)

    def get_relation(self, name: str) -> KernelRelation | None:
        return self._relation_by_name.get(name)

    def entities_in_layer(self, layer: Layer) -> tuple[KernelEntity, ...]:
        return tuple(e for e in self.entities if e.layer == layer)

    def relations_in_layer(self, layer: Layer) -> tuple[KernelRelation, ...]:
        return tuple(r for r in self.relations if r.layer == layer)

    def entity_children(self, parent: str) -> tuple[KernelEntity, ...]:
        return tuple(e for e in self.entities if e.parent == parent)

    def relation_children(self, parent: str) -> tuple[KernelRelation, ...]:
        return tuple(r for r in self.relations if r.parent == parent)

    def entity_depth(self, name: str) -> int:
        """Compute inheritance depth from root."""
        return len(self._ancestors.get(name, ()))

    def all_entity_ancestors(self, name: str) -> tuple[str, ...]:
        """Get all ancestors in order from immediate parent to root.

        Breaking change (v2.5.0): returns tuple instead of list.
        """
        return self._ancestors.get(name, ())

    def effective_plays(self, entity_name: str) -> tuple[str, ...]:
        """Entity's own plays + all ancestors' plays, sorted."""
        entity = self.get_entity(entity_name)
        if entity is None:
            return ()
        all_plays: set[str] = set(entity.plays)
        for ancestor_name in self.all_entity_ancestors(entity_name):
            ancestor = self.get_entity(ancestor_name)
            if ancestor is not None:
                all_plays.update(ancestor.plays)
        return tuple(sorted(all_plays))

    def effective_roles(self, relation_name: str) -> tuple[KernelRole, ...]:
        """Relation's own roles + parent relation's roles (child overrides)."""
        relation = self.get_relation(relation_name)
        if relation is None:
            return ()
        # Collect roles from parent chain (parent first, then child overrides)
        role_chain: list[tuple[KernelRole, ...]] = []
        current: KernelRelation | None = relation
        while current is not None:
            role_chain.append(current.roles)
            current = self.get_relation(current.parent) if current.parent else None
        # Build result: start from root, child overrides by role name
        role_map: dict[str, KernelRole] = {}
        for roles in reversed(role_chain):
            for role in roles:
                role_map[role.name] = role
        return tuple(sorted(role_map.values(), key=lambda r: r.name))

    # ── Validation Engine ──────────────────────────────────────────────

    def entity_matches(self, entity_name: str, pattern: str) -> bool:
        """Check if an entity name matches a pattern.

        Patterns:
          "*"           — matches any entity
          "metatype*"   — matches metatype and all its descendants
          "feature"     — exact match only
        """
        cached = self._pattern_matches.get(pattern)
        if cached is not None:
            return entity_name in cached
        # Fallback for patterns not pre-computed (e.g. from external callers)
        if pattern == "*":
            return entity_name in self._entity_by_name
        if pattern.endswith("*"):
            base = pattern[:-1]
            if entity_name == base:
                return True
            return base in self._ancestors.get(entity_name, ())
        return entity_name == pattern

    def find_matching_rules(
        self, source: str, target: str, relationship_name: str,
    ) -> tuple[KernelValidityRule, ...]:
        """Find all rules matching the given relationship triple, sorted by priority desc.

        Tiebreaking: at the same priority, deny (valid=False) wins over allow.
        """
        candidates = self._rules_by_rel.get(relationship_name, ())
        matched: list[KernelValidityRule] = []
        for rule in candidates:
            # Use pre-computed pattern matches for O(1) membership check
            src_set = self._pattern_matches.get(rule.source_pattern)
            if src_set is not None:
                if source not in src_set:
                    continue
            elif not self.entity_matches(source, rule.source_pattern):
                continue
            tgt_set = self._pattern_matches.get(rule.target_pattern)
            if tgt_set is not None:
                if target not in tgt_set:
                    continue
            elif not self.entity_matches(target, rule.target_pattern):
                continue
            matched.append(rule)
        # Primary: higher priority first. Secondary: deny before allow.
        # Sort key uses `not r.valid` so deny(True) > allow(False) when reversed.
        return tuple(sorted(matched, key=lambda r: (r.priority, not r.valid), reverse=True))

    def validate_relationship(
        self, source: str, target: str, relationship_name: str,
    ) -> KernelValidationResult:
        """Validate a relationship triple against validity rules.

        Layer constraints are checked first (before rule lookup).
        Then returns the result from the highest-priority matching rule.
        If no rules match, the relationship is denied by default.
        """
        base = {
            "source_entity": source,
            "target_entity": target,
            "relationship_name": relationship_name,
        }

        src_e = self.get_entity(source)
        if src_e is None:
            return KernelValidationResult(
                valid=False, notes=f"Unknown entity: {source}", **base,
            )
        tgt_e = self.get_entity(target)
        if tgt_e is None:
            return KernelValidationResult(
                valid=False, notes=f"Unknown entity: {target}", **base,
            )

        # Check layer constraints before rule lookup
        for lc in self.layer_constraints:
            if relationship_name not in lc.forbidden_relations:
                continue
            if src_e.layer != lc.source_layer or tgt_e.layer != lc.target_layer:
                continue
            # Check allowed_pairs exceptions
            exempt = False
            for ap_src, ap_tgt in lc.allowed_pairs:
                if (self.entity_matches(source, ap_src)
                        and self.entity_matches(target, ap_tgt)):
                    exempt = True
                    break
            if not exempt:
                return KernelValidationResult(
                    valid=False,
                    rule_id=f"constraint:{lc.source_layer.value}→{lc.target_layer.value}:{relationship_name}",
                    notes=lc.notes or f"Layer constraint: {lc.source_layer.value} entities cannot use {relationship_name} with {lc.target_layer.value} entities",
                    **base,
                )

        rules = self.find_matching_rules(source, target, relationship_name)
        if not rules:
            return KernelValidationResult(
                valid=False, notes="No matching rule (deny-by-default)", **base,
            )

        top = rules[0]

        # Check conditions on the top-priority rule
        for cond in top.conditions:
            ok, msg = self._check_condition(cond, source, target)
            if not ok:
                return KernelValidationResult(
                    valid=False, rule_id=top.id,
                    notes=f"Condition failed: {msg}", **base,
                )

        return KernelValidationResult(
            valid=top.valid, rule_id=top.id, notes=top.notes, **base,
        )

    def _check_condition(
        self, condition: RuleCondition, source: str, target: str,
    ) -> tuple[bool, str]:
        """Evaluate a single condition. Returns (passed, message)."""
        ct = condition.condition_type
        src_e = self.get_entity(source)
        tgt_e = self.get_entity(target)
        if src_e is None or tgt_e is None:
            return False, "Entity not found"

        if ct == KernelConditionType.SAME_LAYER:
            ok = src_e.layer == tgt_e.layer
            return ok, f"{source}.layer={src_e.layer.value} vs {target}.layer={tgt_e.layer.value}"

        if ct == KernelConditionType.LAYER_ORDER:
            src_ord = LAYER_ORDER[src_e.layer]
            tgt_ord = LAYER_ORDER[tgt_e.layer]
            ok = src_ord <= tgt_ord
            return ok, f"{source}(L{src_ord}) must be <= {target}(L{tgt_ord})"

        if ct == KernelConditionType.ANCESTOR_OF:
            ancestors = self.all_entity_ancestors(target)
            ok = source in ancestors
            return ok, f"{source} {'is' if ok else 'is not'} ancestor of {target}"

        if ct == KernelConditionType.SAME_CATEGORY:
            return True, "SAME_CATEGORY is profile-level only (skipped at kernel)"

        if ct == KernelConditionType.SAME_ENTITY_BRANCH:
            src_anc = set(self.all_entity_ancestors(source)) | {source}
            tgt_anc = set(self.all_entity_ancestors(target)) | {target}
            # Share a non-root ancestor, or one is ancestor of the other
            shared = src_anc & tgt_anc
            # Remove root entities (those with no parent)
            shared_non_root = {
                n for n in shared
                if (e := self.get_entity(n)) is not None and e.parent is not None
            }
            ok = len(shared_non_root) > 0
            return ok, f"shared non-root ancestors: {shared_non_root or 'none'}"

        return False, f"Unknown condition type: {ct}"

    def rule_coverage(self) -> dict[str, object]:
        """Analyze rule coverage over entities and relations."""
        entity_names = {e.name for e in self.entities}
        relation_names = {r.name for r in self.relations}

        covered_entities: set[str] = set()       # literal only
        effective_covered: set[str] = set()      # including wildcards
        covered_relations: set[str] = set()
        for rule in self.validity_rules:
            covered_relations.add(rule.relationship_name)
            for pattern in (rule.source_pattern, rule.target_pattern):
                if pattern == "*":
                    continue  # global wildcard excluded from both
                if pattern.endswith("*"):
                    # effective: resolve hierarchy pattern to actual entities
                    for e_name in entity_names:
                        if self.entity_matches(e_name, pattern):
                            effective_covered.add(e_name)
                else:
                    covered_entities.add(pattern)
                    effective_covered.add(pattern)

        return {
            "total_rules": len(self.validity_rules),
            "entity_coverage": len(covered_entities & entity_names) / len(entity_names) if entity_names else 0,
            "effective_entity_coverage": len(effective_covered & entity_names) / len(entity_names) if entity_names else 0,
            "relation_coverage": len(covered_relations & relation_names) / len(relation_names) if relation_names else 0,
            "covered_entities": sorted(covered_entities & entity_names),
            "effective_covered_entities": sorted(effective_covered & entity_names),
            "uncovered_entities": sorted(entity_names - covered_entities),
            "effective_uncovered_entities": sorted(entity_names - effective_covered),
            "covered_relations": sorted(covered_relations & relation_names),
            "uncovered_relations": sorted(relation_names - covered_relations),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Rule Corpus types — Phase 0.5
# ═══════════════════════════════════════════════════════════════════════════════

class RuleGroup(StrEnum):
    """규칙 검증 단위 그룹. relationship_name 기반."""
    MEMBERSHIP = "membership"
    OWNERSHIP = "ownership"
    SPECIALIZATION = "specialization"
    FEATURE_TYPING = "feature_typing"
    ASSOCIATION = "association"
    CONNECTOR = "connector"
    REDEFINITION = "redefinition"
    SUBSETTING = "subsetting"
    FLOW = "flow"
    SUCCESSION = "succession"
    INTERACTION = "interaction"
    TRIGGERING = "triggering"
    GUARDING = "guarding"
    TRANSITION = "transition"

    @classmethod
    def from_relation(cls, relation_name: str) -> RuleGroup:
        """Derive RuleGroup from relationship_name. Falls back to MEMBERSHIP."""
        try:
            return cls(relation_name)
        except ValueError:
            return cls.MEMBERSHIP


class RuleCategory(StrEnum):
    """Classification of what aspect a rule governs."""
    STRUCTURAL = "structural"
    BEHAVIORAL = "behavioral"
    DOMAIN = "domain"
    EMPIRICAL = "empirical"


class RuleConfidence(StrEnum):
    """How universally applicable a rule is."""
    UNIVERSAL = "universal"
    COMMON = "common"
    CONTEXTUAL = "contextual"
    EMPIRICAL = "empirical"


@dataclass(frozen=True)
class RuleMetadata:
    """Rich metadata attached to a validity rule."""
    domain: str
    tags: tuple[str, ...]
    category: RuleCategory
    confidence: RuleConfidence
    source: str
    established_version: str
    rationale: str
    group: RuleGroup = RuleGroup.MEMBERSHIP


@dataclass(frozen=True)
class RuleCorpusEntry:
    """A validity rule paired with its metadata."""
    rule: KernelValidityRule
    metadata: RuleMetadata


@dataclass(frozen=True)
class RuleEvidence:
    """Evidence record for a single rule during judgment."""
    entry: RuleCorpusEntry
    matched: bool
    is_winner: bool
    condition_results: tuple[tuple[str, bool], ...]


@dataclass(frozen=True)
class JudgmentReport:
    """Evidence-based judgment result (parallel path to validate_relationship)."""
    verdict: bool
    evidence: tuple[RuleEvidence, ...]
    confidence: RuleConfidence
    domains: tuple[str, ...]
    conflicts: tuple[str, ...]


# ═══════════════════════════════════════════════════════════════════════════════
# Topology Graph types — Phase 2
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GraphEdge:
    """An edge in the topology graph with judgment."""
    source: str
    target: str
    relation: str
    judgment: JudgmentReport | None = None


@dataclass(frozen=True)
class GraphPath:
    """An ordered sequence of edges forming a path."""
    edges: tuple[GraphEdge, ...]
    total_confidence: RuleConfidence = RuleConfidence.COMMON

    @property
    def nodes(self) -> tuple[str, ...]:
        if not self.edges:
            return ()
        result = [self.edges[0].source]
        for edge in self.edges:
            result.append(edge.target)
        return tuple(result)

    @property
    def length(self) -> int:
        return len(self.edges)


# ═══════════════════════════════════════════════════════════════════════════════
# Instance + Decision types — Phase 3
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class InstanceElement:
    """M0 instance of a kernel type."""
    id: str
    entity_type: str
    name: str = ""
    properties: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class InstanceRelation:
    """M0 instance of a kernel relation."""
    id: str
    relation_type: str
    source_id: str
    target_id: str


@dataclass(frozen=True)
class ConformanceResult:
    """Result of M0→M2 conformance check."""
    valid: bool
    element_id: str
    check_type: str
    details: str = ""
    rule_id: str | None = None


@dataclass(frozen=True)
class DecisionRecord:
    """Immutable record of a modeling decision."""
    id: str
    timestamp: str
    actor: str
    decision_type: str
    subject_triple: tuple[str, str, str]
    judgment: JudgmentReport | None = None
    override_reason: str = ""
    context: tuple[tuple[str, str], ...] = ()


# ═══════════════════════════════════════════════════════════════════════════════
# AI Decision Interface types — Phase 4
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DecisionContext:
    """Structured context for an AI decision query."""
    subject_triple: tuple[str, str, str]
    judgment: JudgmentReport
    related_decisions: tuple[DecisionRecord, ...]
    reachable_paths: tuple[GraphPath, ...] = ()


@dataclass(frozen=True)
class Recommendation:
    """A ranked recommendation for a modeling decision."""
    triple: tuple[str, str, str]
    score: float
    judgment: JudgmentReport
    rationale: str


# ═══════════════════════════════════════════════════════════════════════════════
# Rule Verification types — group-based rule verification
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RuleVerificationEntry:
    """Verification result for a single rule against a specific triple."""
    rule_id: str
    group: RuleGroup
    passed: bool
    source: str
    target: str
    relation: str
    expected_valid: bool
    actual_valid: bool
    details: str = ""


@dataclass(frozen=True)
class GroupVerificationResult:
    """Aggregated verification result for one RuleGroup."""
    group: RuleGroup
    total_rules: int
    passed_rules: int
    failed_rules: int
    pass_rate: float
    entries: tuple[RuleVerificationEntry, ...]


@dataclass(frozen=True)
class VerificationReport:
    """Full verification report across multiple groups."""
    total_groups: int
    passed_groups: int
    total_rules: int
    total_passed: int
    overall_pass_rate: float
    group_results: tuple[GroupVerificationResult, ...]
    timestamp: str
