from dataclasses import replace

from ea_kernel.diagram_exporter import DiagramExporter
from ea_kernel.graph_view import TopologyGraph
from ea_kernel.localizer import ProfileLocalizer
from ea_kernel.types import KernelEntity, KernelRelation, KernelSchema, KernelValidityRule, Layer


def test_diagram_exporter_localized_labels():
    # 1. Setup entities with localized display names and descriptions
    e1 = KernelEntity(
        name="ea:test:1",
        layer=Layer.L1,
        display_name={"en": "Test One", "ko": "테스트 하나"},
        description={"en": "Desc En", "ko": "설명 한"}
    )
    e2 = KernelEntity(
        name="ea:test:2",
        layer=Layer.L1,
        display_name="Test Two", # Simple string
        description="Simple Desc"
    )

    # 2. Setup schema with a rule that results in an edge
    rule1 = KernelValidityRule(id="rule1", source_pattern="ea:test:1", target_pattern="ea:test:2", relationship_name="links")

    schema = KernelSchema(
        attributes=(),
        entities=(e1, e2),
        relations=(KernelRelation(name="links", layer=Layer.L2),),
        validity_rules=(rule1,)
    )

    # 3. Build Graph
    graph = TopologyGraph(schema)
    exporter = DiagramExporter(graph)

    # 4. Generate Mermaid
    mermaid = exporter.generate_mermaid()

    # 5. Assertions
    assert "테스트 하나" in mermaid
    assert "설명 한" in mermaid
    assert "Test Two" in mermaid
    assert "Simple Desc" in mermaid
    # Use loosely matched string to avoid spacing issues
    assert "ea:test:1" in mermaid
    assert "-->|links|" in mermaid
    assert "ea:test:2" in mermaid

def test_localizer_extended_patching():
    # 1. Setup base profile with correct arguments
    from ea_kernel.profile_builder import ProfileBuilder

    builder = ProfileBuilder("TestProfile", version="1.0", kernel_version="2.5.0")
    builder.element("ea:test:1", layer="L1", category="Cat", kernel_type="structure", display_name="Base Name")
    profile = builder.build()

    # 2. Mock patch data
    patch_data = {
        "elements": {
            "ea:test:1": {
                "display_name": "Localized Name",
                "description": "Localized Desc"
            }
        },
        "validity_rules": {
            "rule_1": {
                "description": "Rule Desc Ko"
            }
        }
    }

    # Add a rule to the profile manually
    rule = KernelValidityRule(id="rule_1", source_pattern="*", target_pattern="*", relationship_name="*", description="Base Rule")
    profile = replace(profile, validity_rules=(rule,))

    # 3. Apply Patch
    localizer = ProfileLocalizer()
    local_profile = localizer.apply_patch(profile, patch_data, lang="ko")

    # 4. Verify
    elem = local_profile.get_element("ea:test:1")
    assert elem.display_name["ko"] == "Localized Name"
    assert elem.description["ko"] == "Localized Desc"

    rule_ko = local_profile.validity_rules[0]
    assert rule_ko.description["ko"] == "Rule Desc Ko"

def test_localizer_missing_file_safety(tmp_path):
    # Verify that it doesn't crash if search_path is provided but file missing
    localizer = ProfileLocalizer(patch_dir=tmp_path)
    from ea_kernel.profile_builder import ProfileBuilder
    profile = ProfileBuilder("Missing", version="1.0", kernel_version="2.5.0").build()

    # Should just return original
    result = localizer.localize(profile, lang="ko")
    assert result == profile
