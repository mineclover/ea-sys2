"""Fluent builder for kernel profiles.

Reduces profile boilerplate from ~500 lines to ~80 lines by providing:
- Automatic kernel_type inference from category_mapping
- Bulk element generation (elements_from_matrix for matrix-style profiles)
- Rule convenience methods (allow_same_category, rule_group)
- Build-time validation (pattern refs, kernel refs, structure checks)
- Automatic fallback deny rule generation
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from ea_profile.types import (
    I18nString,
    KernelProfile,
    LayerDefinition,
    LayerStack,
    PatternType,
    ProfileArtifactType,
    ProfileBuildError,
    ProfileElement,
    ProfileMetadata,
    ProfileProcessUnit,
    ProfileRelation,
    ProfileRule,
    ProfileStateTransition,
    RuleCondition,
    SchemaPort,
    classify_pattern,
)

if TYPE_CHECKING:
    from ea_kernel.types import RuleMetadata


class ProfileBuilder:
    """Fluent builder for constructing KernelProfile instances.

    Usage:
        profile = (
            ProfileBuilder("MyFramework", version="1.0", kernel_version="2.5.0")
            .id_prefix("mf")
            .metadata(standard="MyFramework 1.0", organization="ACME")
            .category_mapping({"ActiveStructure": "structure", "Behavior": "step"})
            .element("Widget", layer="Core", category="ActiveStructure")
            .relation("uses", kernel_relation="association")
            .allow("@ActiveStructure", "@Behavior", "uses")
            .build()
        )
    """

    def __init__(
        self,
        name: str,
        *,
        version: str,
        kernel_version: str,
    ) -> None:
        self._name = name
        self._version = version
        self._kernel_version = kernel_version
        self._prefix = ""
        self._standard = ""
        self._organization = ""
        self._extra: dict[str, str] | None = None
        self._cat_map: dict[str, str] = {}
        self._elements: list[ProfileElement] = []
        self._relations: list[ProfileRelation] = []
        self._state_transitions: list[ProfileStateTransition] = []
        self._artifact_types: list[ProfileArtifactType] = []
        self._process_units: list[ProfileProcessUnit] = []
        self._layer_stack: LayerStack | None = None
        self._rules: list[ProfileRule] = []
        self._rule_metadata: dict[str, RuleMetadata] = {}
        self._rule_counter = 0

    # ── Meta ──────────────────────────────────────────────────────

    def id_prefix(self, prefix: str) -> ProfileBuilder:
        """Set the rule ID prefix (e.g., 'zf' → 'zf-allow-01')."""
        self._prefix = prefix
        return self

    def metadata(
        self,
        *,
        standard: str,
        organization: str,
        extra: dict[str, str] | None = None,
    ) -> ProfileBuilder:
        """Set profile metadata."""
        self._standard = standard
        self._organization = organization
        self._extra = extra
        return self

    # ── Category mapping ──────────────────────────────────────────

    def category_mapping(self, mapping: dict[str, str]) -> ProfileBuilder:
        """Set category → kernel_type mapping for auto-inference.

        Example: {"ActiveStructure": "structure", "Behavior": "step"}
        When adding elements, kernel_type can be omitted if category is mapped.
        """
        self._cat_map = dict(mapping)
        return self

    # ── Elements ──────────────────────────────────────────────────

    def element(
        self,
        name: str,
        *,
        layer: str,
        category: str,
        kernel_type: str | None = None,
        description: I18nString = "",
        display_name: I18nString = "",
    ) -> ProfileBuilder:
        """Add a single element."""
        if kernel_type is None:
            kernel_type = self._cat_map.get(category)
            if kernel_type is None:
                raise ProfileBuildError(
                    [f"No kernel_type for element '{name}': "
                     f"category '{category}' not in category_mapping"]
                )
        self._elements.append(ProfileElement(
            name=name,
            kernel_type=kernel_type,
            layer=layer,
            category=category,
            description=description,
            display_name=display_name,
        ))
        return self

    def elements_bulk(self, elements: list[dict[str, object]]) -> ProfileBuilder:
        """Add multiple elements from dicts.

        Each dict: {"name": ..., "layer": ..., "category": ...,
                     "kernel_type": ... (opt), "description": ... (opt)}
        """
        for elem in elements:
            self.element(
                cast(str, elem["name"]),
                layer=cast(str, elem["layer"]),
                category=cast(str, elem["category"]),
                kernel_type=cast(str | None, elem.get("kernel_type")),
                description=cast(I18nString, elem.get("description", "")),
            )
        return self

    def elements_from_matrix(
        self,
        layers: list[str],
        categories: dict[str, str],
        naming: Callable[[str, str], str],
        descriptions: Callable[[str, str], str] | None = None,
    ) -> ProfileBuilder:
        """Generate elements from a layer × category matrix.

        Args:
            layers: Row names (e.g., ["Scope", "Enterprise", ...])
            categories: Column → kernel_type map (e.g., {"What": "item", ...})
            naming: Callable(layer, category) → element name
            descriptions: Optional callable(layer, category) → description

        This also updates category_mapping from the categories dict.
        """
        self._cat_map.update(categories)
        for layer in layers:
            for cat, ktype in categories.items():
                name = naming(layer, cat)
                desc = descriptions(layer, cat) if descriptions else ""
                self._elements.append(ProfileElement(
                    name=name,
                    kernel_type=ktype,
                    layer=layer,
                    category=cat,
                    description=desc,
                ))
        return self

    # ── Relations ─────────────────────────────────────────────────

    def relation(
        self,
        name: str,
        *,
        kernel_relation: str,
        description: I18nString = "",
        display_name: I18nString = "",
        direction: str = "",
    ) -> ProfileBuilder:
        """Add a single relation."""
        self._relations.append(ProfileRelation(
            name=name,
            kernel_relation=kernel_relation,
            description=description,
            display_name=display_name,
            direction=direction,
        ))
        return self

    def relations(
        self,
        *decls: tuple[str, str] | tuple[str, str, str] | tuple[str, str, str, str],
    ) -> ProfileBuilder:
        """Add multiple relations from tuples.

        Each tuple: (name, kernel_relation)
                  or (name, kernel_relation, description)
                  or (name, kernel_relation, description, direction)
        """
        for decl in decls:
            name = decl[0]
            kernel_rel = decl[1]
            desc = decl[2] if len(decl) > 2 else ""
            direction = decl[3] if len(decl) > 3 else ""
            self._relations.append(ProfileRelation(
                name=name,
                kernel_relation=kernel_rel,
                description=desc,
                direction=direction,
            ))
        return self

    # ── State transitions ────────────────────────────────────────

    def add_state_transition(
        self,
        from_state: str,
        to_state: str,
        *,
        guard_condition: str = "",
        description: I18nString = "",
    ) -> ProfileBuilder:
        """Add a declarative state transition to the profile."""
        self._state_transitions.append(ProfileStateTransition(
            from_state=from_state,
            to_state=to_state,
            guard_condition=guard_condition,
            description=description,
        ))
        return self

    def add_artifact_type(
        self,
        name: str,
        tier: str,
        *,
        description: I18nString = "",
        kernel_element_pattern: str = "",
    ) -> ProfileBuilder:
        """Add a declarative artifact type definition to the profile."""
        self._artifact_types.append(ProfileArtifactType(
            name=name,
            tier=tier,
            description=description,
            kernel_element_pattern=kernel_element_pattern,
        ))
        return self

    def add_process_unit(
        self,
        name: str,
        phase: str,
        *,
        description: I18nString = "",
        input_artifacts: tuple[str, ...] = (),
        output_artifacts: tuple[str, ...] = (),
    ) -> ProfileBuilder:
        """Add a declarative process unit definition to the profile."""
        self._process_units.append(ProfileProcessUnit(
            name=name,
            phase=phase,
            description=description,
            input_artifacts=input_artifacts,
            output_artifacts=output_artifacts,
        ))
        return self

    def set_layer_stack(
        self,
        *,
        definition_flow: str = "",
        runtime_flow: str = "",
        feedback_flow: str = "",
    ) -> ProfileBuilder:
        """Set layer stack-level flow metadata."""
        layers = self._layer_stack.layers if self._layer_stack is not None else ()
        self._layer_stack = LayerStack(
            layers=layers,
            definition_flow=definition_flow,
            runtime_flow=runtime_flow,
            feedback_flow=feedback_flow,
        )
        return self

    def add_layer_definition(
        self,
        name: str,
        order: int,
        *,
        depends_on: tuple[str, ...] = (),
        responsibility: I18nString = "",
        model_perspective: str = "",
    ) -> ProfileBuilder:
        """Add a layer definition entry to the layer stack metadata."""
        if self._layer_stack is None:
            self._layer_stack = LayerStack()
        layer = LayerDefinition(
            name=name,
            order=order,
            depends_on=depends_on,
            responsibility=responsibility,
            model_perspective=model_perspective,
        )
        self._layer_stack = LayerStack(
            layers=self._layer_stack.layers + (layer,),
            definition_flow=self._layer_stack.definition_flow,
            runtime_flow=self._layer_stack.runtime_flow,
            feedback_flow=self._layer_stack.feedback_flow,
        )
        return self

    # ── Composite validation ─────────────────────────────────────

    def hosted_flow(
        self,
        host_category: str,
        step_category: str,
        data_category: str,
        *,
        produce_relation: str = "produces",
        consume_relation: str = "consumes",
        kernel: SchemaPort | None = None,
    ) -> ProfileBuilder:
        """Validate Hosted Flow Pattern at build time.

        Checks that the host→step ownership and step↔data flow paths
        are structurally valid at the kernel level.

        Args:
            host_category: Category of the host element (e.g., "ActiveComponent")
            step_category: Category of the step element (e.g., "BehavioralStep")
            data_category: Category of the data element (e.g., "PassiveAsset")
            produce_relation: Profile relation for step→data (default "produces")
            consume_relation: Profile relation for data→step (default "consumes")
            kernel: Kernel schema for validation (optional)
        """
        errors: list[str] = []

        # 1. Resolve kernel types from category mapping
        host_ktype = self._cat_map.get(host_category)
        step_ktype = self._cat_map.get(step_category)
        data_ktype = self._cat_map.get(data_category)

        if host_ktype is None:
            errors.append(
                f"hosted_flow: host category '{host_category}' not in category_mapping"
            )
        if step_ktype is None:
            errors.append(
                f"hosted_flow: step category '{step_category}' not in category_mapping"
            )
        if data_ktype is None:
            errors.append(
                f"hosted_flow: data category '{data_category}' not in category_mapping"
            )

        # 2. Check that produce/consume relations are defined
        rel_names = {r.name for r in self._relations}
        if produce_relation not in rel_names:
            errors.append(
                f"hosted_flow: produce relation '{produce_relation}' not defined"
            )
        if consume_relation not in rel_names:
            errors.append(
                f"hosted_flow: consume relation '{consume_relation}' not defined"
            )

        # 3. Kernel-level structural validation (if schema supports it)
        if (kernel is not None
                and hasattr(kernel, "validate_relationship")
                and host_ktype and step_ktype and data_ktype):
            # ownership: host → step
            own_result = kernel.validate_relationship(host_ktype, step_ktype, "ownership")
            if not own_result.valid:
                errors.append(
                    f"hosted_flow: kernel denies ownership "
                    f"{host_ktype}→{step_ktype}: {own_result.notes}"
                )

            # flow: step → data (produces)
            flow_out = kernel.validate_relationship(step_ktype, data_ktype, "flow")
            if not flow_out.valid:
                errors.append(
                    f"hosted_flow: kernel denies flow "
                    f"{step_ktype}→{data_ktype}: {flow_out.notes}"
                )

            # flow: data → step (consumes)
            flow_in = kernel.validate_relationship(data_ktype, step_ktype, "flow")
            if not flow_in.valid:
                errors.append(
                    f"hosted_flow: kernel denies flow "
                    f"{data_ktype}→{step_ktype}: {flow_in.notes}"
                )

        if errors:
            raise ProfileBuildError(errors)

        return self

    # ── Rules ─────────────────────────────────────────────────────

    def _next_rule_id(self, tag: str) -> str:
        self._rule_counter += 1
        prefix = f"{self._prefix}-" if self._prefix else ""
        return f"{prefix}{tag}-{self._rule_counter:02d}"

    def allow(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        priority: int = 40,
        notes: str = "",
        conditions: tuple[RuleCondition, ...] = (),
        rule_id: str | None = None,
        metadata: RuleMetadata | None = None,
        scope: str = "",
    ) -> ProfileBuilder:
        """Add an allow rule."""
        rid = rule_id or self._next_rule_id("allow")
        self._rules.append(ProfileRule(
            id=rid,
            source_pattern=source,
            target_pattern=target,
            relationship_name=relation,
            valid=True,
            priority=priority,
            conditions=conditions,
            notes=notes,
            scope=scope,
        ))
        if metadata is not None:
            self._rule_metadata[rid] = metadata
        return self

    def deny(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        priority: int = 80,
        notes: str = "",
        rule_id: str | None = None,
        metadata: RuleMetadata | None = None,
        scope: str = "",
    ) -> ProfileBuilder:
        """Add a deny rule."""
        rid = rule_id or self._next_rule_id("deny")
        self._rules.append(ProfileRule(
            id=rid,
            source_pattern=source,
            target_pattern=target,
            relationship_name=relation,
            valid=False,
            priority=priority,
            notes=notes,
            scope=scope,
        ))
        if metadata is not None:
            self._rule_metadata[rid] = metadata
        return self

    # ── Rule convenience methods ──────────────────────────────────

    def allow_same_category(
        self,
        relation: str,
        *,
        priority: int = 40,
        notes: str = "",
        rule_id: str | None = None,
    ) -> ProfileBuilder:
        """Allow * → * with SAME_CATEGORY condition."""
        return self.allow(
            "*", "*", relation,
            priority=priority,
            notes=notes,
            conditions=(RuleCondition("same_category"),),
            rule_id=rule_id,
        )

    def allow_same_layer(
        self,
        relation: str,
        *,
        priority: int = 40,
        notes: str = "",
        rule_id: str | None = None,
    ) -> ProfileBuilder:
        """Allow * → * with SAME_LAYER condition."""
        return self.allow(
            "*", "*", relation,
            priority=priority,
            notes=notes,
            conditions=(RuleCondition("same_layer"),),
            rule_id=rule_id,
        )

    def rule_group(
        self,
        relation: str,
        rules: list[tuple[str, str]],
        *,
        priority: int = 40,
        notes: str = "",
    ) -> ProfileBuilder:
        """Add multiple allow rules for the same relation.

        Args:
            relation: The relation name
            rules: List of (source_pattern, target_pattern) tuples
            priority: Shared priority for all rules
            notes: Shared notes prefix
        """
        for source, target in rules:
            self.allow(source, target, relation, priority=priority, notes=notes)
        return self

    # ── Build ─────────────────────────────────────────────────────

    def build(
        self,
        kernel: SchemaPort | None = None,
        *,
        auto_fallback: bool = True,
        validate: bool = True,
    ) -> KernelProfile:
        """Build the KernelProfile with validation and auto-fallback.

        Args:
            kernel: Optional schema for kernel-level reference validation
            auto_fallback: Auto-generate deny-by-default fallback rules (default True)
            validate: Run build-time validation (default True)

        Raises:
            ProfileBuildError: If validation finds errors
        """
        if validate:
            self._validate(kernel)

        rules = list(self._rules)

        if auto_fallback:
            rules = self._add_fallbacks(rules)

        md = None
        if self._standard or self._organization:
            md = ProfileMetadata(
                standard=self._standard,
                organization=self._organization,
                extra=self._extra,
            )

        return KernelProfile(
            name=self._name,
            version=self._version,
            kernel_version=self._kernel_version,
            elements=tuple(self._elements),
            relations=tuple(self._relations),
            validity_rules=tuple(rules),
            metadata=md,
            state_transitions=tuple(self._state_transitions),
            artifact_types=tuple(self._artifact_types),
            process_units=tuple(self._process_units),
            layer_stack=self._layer_stack,
        )

    # ── Internal validation ───────────────────────────────────────

    def _validate(self, kernel: SchemaPort | None) -> None:
        """Run all build-time validations. Raises ProfileBuildError on failure."""
        errors: list[str] = []

        # 1. Structure: duplicate names
        elem_names = [e.name for e in self._elements]
        dup_elems = [n for n in elem_names if elem_names.count(n) > 1]
        if dup_elems:
            errors.append(f"Duplicate element names: {sorted(set(dup_elems))}")

        rel_names = [r.name for r in self._relations]
        dup_rels = [n for n in rel_names if rel_names.count(n) > 1]
        if dup_rels:
            errors.append(f"Duplicate relation names: {sorted(set(dup_rels))}")

        rule_ids = [r.id for r in self._rules]
        dup_rules = [i for i in rule_ids if rule_ids.count(i) > 1]
        if dup_rules:
            errors.append(f"Duplicate rule IDs: {sorted(set(dup_rules))}")

        # 2. Kernel reference validation
        if kernel is not None:
            kernel_entities = {e.name for e in kernel.entities}
            kernel_relations = {r.name for r in kernel.relations}

            for elem in self._elements:
                if elem.kernel_type not in kernel_entities:
                    errors.append(
                        f"Element '{elem.name}' maps to unknown kernel type: "
                        f"'{elem.kernel_type}'"
                    )

            for rel in self._relations:
                if rel.kernel_relation not in kernel_relations:
                    errors.append(
                        f"Relation '{rel.name}' maps to unknown kernel relation: "
                        f"'{rel.kernel_relation}'"
                    )

        # 3. Pattern reference validation
        categories = {e.category for e in self._elements}
        layers = {e.layer for e in self._elements}
        elem_name_set = set(elem_names)

        for rule in self._rules:
            for pattern in (rule.source_pattern, rule.target_pattern):
                ptype = classify_pattern(pattern)
                if ptype == PatternType.CATEGORY:
                    cat = pattern[1:]
                    if cat not in categories:
                        errors.append(
                            f"Rule '{rule.id}': pattern '{pattern}' references "
                            f"unknown category '{cat}'"
                        )
                elif ptype == PatternType.LAYER:
                    layer = pattern[1:]
                    if layer not in layers:
                        errors.append(
                            f"Rule '{rule.id}': pattern '{pattern}' references "
                            f"unknown layer '{layer}'"
                        )
                elif ptype == PatternType.EXACT:
                    if pattern not in elem_name_set:
                        errors.append(
                            f"Rule '{rule.id}': pattern '{pattern}' references "
                            f"unknown element"
                        )

        # 4. Category consistency: category_mapping vs actual kernel_types
        if self._cat_map:
            for elem in self._elements:
                expected = self._cat_map.get(elem.category)
                if expected is not None and elem.kernel_type != expected:
                    errors.append(
                        f"Element '{elem.name}': category '{elem.category}' "
                        f"maps to '{expected}' but kernel_type is '{elem.kernel_type}'"
                    )

        # 5. Rule relationship references
        rel_name_set = set(rel_names)
        for rule in self._rules:
            if rule.relationship_name not in rel_name_set:
                errors.append(
                    f"Rule '{rule.id}': references unknown relation "
                    f"'{rule.relationship_name}'"
                )

        # 6. Layer stack metadata consistency
        if self._layer_stack is not None:
            layer_names = [layer.name for layer in self._layer_stack.layers]
            dup_layer_names = [name for name in layer_names if layer_names.count(name) > 1]
            if dup_layer_names:
                errors.append(
                    f"Duplicate layer names in layer_stack: {sorted(set(dup_layer_names))}"
                )

            layer_orders = [layer.order for layer in self._layer_stack.layers]
            dup_layer_orders = [order for order in layer_orders if layer_orders.count(order) > 1]
            if dup_layer_orders:
                errors.append(
                    f"Duplicate layer order values in layer_stack: {sorted(set(dup_layer_orders))}"
                )

            known_layers = set(layer_names)
            for layer_def in self._layer_stack.layers:
                unknown = [dep for dep in layer_def.depends_on if dep not in known_layers]
                if unknown:
                    errors.append(
                        f"Layer '{layer_def.name}' depends on unknown layers: "
                        f"{sorted(set(unknown))}"
                    )

        if errors:
            raise ProfileBuildError(errors)

    def _add_fallbacks(
        self, rules: list[ProfileRule],
    ) -> list[ProfileRule]:
        """Add deny-by-default fallback rules for relations missing them."""
        existing_fallback_rels = set()
        for rule in rules:
            if not rule.valid and rule.priority == 1 and rule.source_pattern == "*" and rule.target_pattern == "*":
                existing_fallback_rels.add(rule.relationship_name)

        prefix = f"{self._prefix}-" if self._prefix else ""
        for rel in self._relations:
            if rel.name not in existing_fallback_rels:
                rules.append(ProfileRule(
                    id=f"{prefix}fallback-{rel.name.replace('_', '-')}",
                    source_pattern="*",
                    target_pattern="*",
                    relationship_name=rel.name,
                    valid=False,
                    priority=1,
                    notes=f"Deny-by-default for {rel.name}",
                ))

        return rules
