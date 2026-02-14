from pathlib import Path
import pytest
from ea_kernel.profile_loader import load_profile
from ea_kernel.types import KernelSchema, KernelEntity, KernelRelation, Layer
from ea_kernel.localizer import ProfileLocalizer

def test_system_self_model_base_loading():
    """Verify that the base system_self_model.toml loads with English strings."""
    profile_path = Path(__file__).parent.parent / "src" / "ea_kernel" / "profiles" / "system_self_model.toml"
    
    # 1. Setup dummy kernel
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
    
    # 2. Load Base Profile (should be English strings now)
    profile = load_profile(profile_path, kernel=dummy_kernel)
    elem = profile.get_element("ea:kernel:schema")
    
    # Base description is now a simple string "Defines structural truth..."
    assert isinstance(elem.description, str)
    assert "structural truth" in elem.description

def test_system_self_model_patch_loading():
    """Verify that the Korean patch can be applied to the base profile."""
    profile_dir = Path(__file__).parent.parent / "src" / "ea_kernel" / "profiles"
    profile_path = profile_dir / "system_self_model.toml"
    
    dummy_kernel = KernelSchema(
        attributes=(),
        entities=(KernelEntity(name="structure", layer=Layer.L1), KernelEntity(name="action", layer=Layer.L3)),
        relations=(KernelRelation(name="association", layer=Layer.L2), KernelRelation(name="ownership", layer=Layer.L2))
    )
    
    profile = load_profile(profile_path, kernel=dummy_kernel)
    
    # Apply Localizer
    localizer = ProfileLocalizer(patch_dir=profile_dir)
    localized = localizer.localize(profile, lang="ko")
    
    elem = localized.get_element("ea:kernel:schema")
    assert isinstance(elem.description, dict)
    assert elem.description["ko"] == "구조적 진실과 제약 조건을 정의합니다. (패치 적용됨)"
    assert elem.display_name["ko"] == "커널 스키마"

def test_manual_i18n_string_assignment():
    from ea_kernel.profile_types import ProfileElement
    
    # Test that simple strings still work (Backward compatibility)
    elem = ProfileElement(
        name="LegacyElement",
        kernel_type="entity",
        layer="test",
        category="test",
        description="Just a string"
    )
    assert elem.description == "Just a string"
    
    # Test that dict works
    elem_i18n = ProfileElement(
        name="ModernElement",
        kernel_type="entity",
        layer="test",
        category="test",
        description={"en": "Hello", "ko": "안녕"}
    )
    assert isinstance(elem_i18n.description, dict)
    assert elem_i18n.description["ko"] == "안녕"
