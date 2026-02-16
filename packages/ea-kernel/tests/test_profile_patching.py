from dataclasses import replace
from pathlib import Path

from ea_kernel.localizer import ProfileLocalizer, audit_profile_i18n_patch
from ea_kernel.profile_builder import ProfileBuilder
from ea_kernel.profile_loader import load_profile
from ea_kernel.types import (
    KernelEntity,
    KernelRelation,
    KernelSchema,
    KernelValidityRule,
    Layer,
)


def test_profile_patching_ko():
    # 1. Paths
    profile_dir = Path(__file__).parent.parent / "src" / "ea_kernel" / "profiles"
    profile_path = profile_dir / "system_self_model.toml"

    # 2. Setup dummy kernel schema with required types
    dummy_kernel = KernelSchema(
        attributes=(),
        entities=(
            KernelEntity(name="structure", layer=Layer.L1),
            KernelEntity(name="action", layer=Layer.L3),
        ),
        relations=(
            KernelRelation(name="association", layer=Layer.L2),
            KernelRelation(name="ownership", layer=Layer.L2),
        )
    )

    # 3. Load Base Profile (English)
    profile = load_profile(profile_path, kernel=dummy_kernel)
    assert profile.get_element("ea:kernel:schema").description == "Defines structural truth and constraints."

    # 4. Apply Korean Patch via Localizer
    localizer = ProfileLocalizer(patch_dir=profile_dir)
    localized_profile = localizer.localize(profile, lang="ko")

    # 5. Verify Patch Application
    elem = localized_profile.get_element("ea:kernel:schema")
    assert isinstance(elem.description, dict)
    assert elem.description["en"] == "Defines structural truth and constraints."
    assert elem.description["ko"] == "구조적 진실과 제약 조건을 정의합니다. (패치 적용됨)"

    # 6. Verify Relation Patch
    rel = localized_profile.get_relation("targets")
    assert rel.description["ko"] == "의사결정 패턴은 컨텍스트 또는 변경을 위해 특정 커널 스키마 영역을 대상으로 합니다."

def test_localizer_no_patch_behavior():
    # Test that it returns the original profile if patch is missing or lang is en
    profile_dir = Path(__file__).parent.parent / "src" / "ea_kernel" / "profiles"
    profile_path = profile_dir / "system_self_model.toml"
    dummy_kernel = KernelSchema(attributes=(), entities=(KernelEntity(name="structure", layer=Layer.L1), KernelEntity(name="action", layer=Layer.L3)), relations=(KernelRelation(name="association", layer=Layer.L2), KernelRelation(name="ownership", layer=Layer.L2)))
    profile = load_profile(profile_path, kernel=dummy_kernel)

    localizer = ProfileLocalizer(patch_dir=profile_dir)

    # lang='en' should return original
    en_profile = localizer.localize(profile, lang="en")
    assert en_profile == profile

    # lang='ja' (missing) should return original
    ja_profile = localizer.localize(profile, lang="ja")
    assert ja_profile == profile


def test_profile_i18n_audit_detects_missing_orphan_stale(tmp_path: Path):
    builder = ProfileBuilder("AuditProfile", version="1.0.0", kernel_version="2.5.0")
    builder.element(
        "ElementOne",
        layer="Business",
        category="Behavior",
        kernel_type="step",
        description="Element EN Description",
        display_name="Element One",
    )
    builder.relation(
        "relates",
        kernel_relation="association",
        description="Relation EN Description",
        display_name="Relates",
    )
    profile = builder.build(validate=False, auto_fallback=False)
    profile = replace(
        profile,
        validity_rules=(
            KernelValidityRule(
                id="rule_1",
                source_pattern="ElementOne",
                target_pattern="ElementOne",
                relationship_name="relates",
                description="Rule EN Description",
            ),
        ),
    )

    patch_path = tmp_path / "auditprofile.ko.patch.toml"
    patch_path.write_text(
        (
            "[elements.ElementOne]\n"
            "display_name = \"요소 하나\"\n"
            "_en_display_name = \"Element One\"\n"
            "description = \"요소 설명\"\n"
            "_en_description = \"Old Element EN Description\"\n\n"
            "[elements.UnknownElement]\n"
            "display_name = \"고아 요소\"\n\n"
            "[relations.relates]\n"
            "display_name = \"연결\"\n"
            "_en_display_name = \"Relates\"\n\n"
            "[validity_rules.rule_1]\n"
            "description = \"규칙 설명\"\n"
            "_en_description = \"Rule EN Description\"\n\n"
            "[validity_rules.ghost_rule]\n"
            "description = \"고아 규칙\"\n"
        ),
        encoding="utf-8",
    )

    report = audit_profile_i18n_patch(profile, "ko", patch_path=patch_path)

    assert report.total_schema_items == 5
    assert report.total_translated == 4
    assert report.coverage == 0.8

    assert len(report.missing) == 1
    missing = report.missing[0]
    assert missing.kind == "relation"
    assert missing.name == "relates"
    assert missing.field == "description"

    assert len(report.orphan) == 2
    orphan_keys = {(e.kind, e.name, e.field) for e in report.orphan}
    assert ("element", "UnknownElement", "display_name") in orphan_keys
    assert ("validity_rule", "ghost_rule", "description") in orphan_keys

    assert len(report.stale) == 1
    stale = report.stale[0]
    assert stale.kind == "element"
    assert stale.name == "ElementOne"
    assert stale.field == "description"
    assert stale.en_recorded == "Old Element EN Description"
