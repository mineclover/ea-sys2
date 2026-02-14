from pathlib import Path

from ea_kernel.localizer import ProfileLocalizer
from ea_kernel.profile_loader import load_profile
from ea_kernel.types import KernelEntity, KernelRelation, KernelSchema, Layer


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
