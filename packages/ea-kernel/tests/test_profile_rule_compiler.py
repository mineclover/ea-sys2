from __future__ import annotations

from ea_kernel.profile_builder import ProfileBuilder
from ea_kernel.profile_rule_compiler import (
    build_profile_runtime_schema,
    build_profile_structure_schema,
    compile_profile_rules_for_runtime,
)
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.types import Layer


def test_compile_category_patterns_to_kernel_wildcards() -> None:
    profile = (
        ProfileBuilder("WildcardProfile", version="1.0.0", kernel_version="2.5.0")
        .category_mapping(
            {
                "Composite": "package",
                "ActiveStructure": "structure",
            }
        )
        .element("KernelLayer", layer="Kernel", category="Composite")
        .element("KernelSpecBuilder", layer="Kernel", category="ActiveStructure")
        .relation("contains", kernel_relation="ownership")
        .allow("@Composite", "@ActiveStructure", "contains", rule_id="wc-allow-01")
        .build(auto_fallback=False)
    )

    result = compile_profile_rules_for_runtime(profile)

    assert result.stats.source_rule_count == 1
    assert result.stats.compiled_rule_count == 1
    assert result.stats.transformed_rule_count == 1
    assert result.stats.skipped_rule_count == 0

    compiled = result.rules[0]
    assert compiled.id == "wc-allow-01__c0001"
    assert compiled.source_pattern == "package*"
    assert compiled.target_pattern == "structure*"


def test_compile_category_patterns_to_explicit_elements_when_mixed_kernel_types() -> None:
    profile = (
        ProfileBuilder("MixedCategoryProfile", version="1.0.0", kernel_version="2.5.0")
        .element("DomainPackage", layer="L1", category="Domain", kernel_type="package")
        .element("DomainStructure", layer="L1", category="Domain", kernel_type="structure")
        .element("Target", layer="L1", category="Target", kernel_type="structure")
        .relation("depends_on", kernel_relation="association")
        .allow("@Domain", "Target", "depends_on", rule_id="mix-allow-01")
        .allow("DomainPackage", "Target", "depends_on", rule_id="mix-allow-exact")
        .build(auto_fallback=False)
    )

    result = compile_profile_rules_for_runtime(profile)

    assert result.stats.source_rule_count == 2
    assert result.stats.compiled_rule_count == 3
    assert result.stats.transformed_rule_count == 1
    assert result.stats.skipped_rule_count == 0

    transformed_sources = {
        rule.source_pattern
        for rule in result.rules
        if rule.id.startswith("mix-allow-01__c")
    }
    assert transformed_sources == {"DomainPackage", "DomainStructure"}
    assert all(
        rule.target_pattern == "Target"
        for rule in result.rules
        if rule.id.startswith("mix-allow-01__c")
    )

    exact = next(rule for rule in result.rules if rule.id == "mix-allow-exact")
    assert exact.source_pattern == "DomainPackage"
    assert exact.target_pattern == "Target"


def test_build_profile_runtime_schema_standalone_compiles_patterns_with_kernel_layer_mapping() -> None:
    profile = (
        ProfileBuilder("RuntimeProjectionProfile", version="1.0.0", kernel_version="2.5.0")
        .category_mapping(
            {
                "Composite": "package",
                "ActiveStructure": "structure",
            }
        )
        .element("DomainKernel", layer="Kernel", category="Composite")
        .element("DomainAgent", layer="Authoring", category="ActiveStructure")
        .relation("contains", kernel_relation="ownership")
        .allow("@Composite", "@ActiveStructure", "contains", rule_id="runtime-allow-01")
        .build(auto_fallback=False)
    )

    runtime = build_profile_runtime_schema(
        KERNEL_SPEC,
        profile,
        include_base_schema=False,
        include_base_rules=False,
    )
    schema = runtime.schema

    assert runtime.overlay.added_entity_count == 2
    assert runtime.overlay.added_relation_count == 1
    assert len(schema.entities) == 2
    assert len(schema.relations) == 1
    assert len(schema.validity_rules) == 1
    assert runtime.compilation.stats.transformed_rule_count == 1

    entities = {entity.name: entity for entity in schema.entities}
    assert entities["DomainKernel"].parent == "package"
    assert entities["DomainKernel"].layer == Layer.L1
    assert entities["DomainAgent"].parent == "structure"
    assert entities["DomainAgent"].layer == Layer.L1

    relation = schema.relations[0]
    assert relation.name == "contains"
    assert relation.parent == "ownership"
    assert relation.layer == Layer.L2

    compiled = schema.validity_rules[0]
    assert compiled.source_pattern == "package*"
    assert compiled.target_pattern == "structure*"


def test_build_profile_structure_schema_keeps_base_rules_when_requested() -> None:
    profile = (
        ProfileBuilder("StructureProjectionProfile", version="1.0.0", kernel_version="2.5.0")
        .category_mapping({"Domain": "structure"})
        .element("DomainNode", layer="Domain", category="Domain")
        .relation("connects", kernel_relation="association")
        .build(auto_fallback=False)
    )

    schema, overlay = build_profile_structure_schema(
        KERNEL_SPEC,
        profile,
        include_base_schema=True,
        include_base_rules=True,
    )

    assert overlay.added_entity_count == 1
    assert overlay.added_relation_count == 1
    assert len(schema.validity_rules) == len(KERNEL_SPEC.validity_rules)
    assert any(entity.name == "DomainNode" for entity in schema.entities)
    assert any(relation.name == "connects" for relation in schema.relations)
