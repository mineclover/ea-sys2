from pathlib import Path
import pytest
from ea_governance.facade import GovernanceContainer
from ea_kernel.types import KernelSchema, KernelEntity, KernelRelation, Layer

def test_facade_localized_diagram(tmp_path):
    # Setup dummy schema that the self-model profile expects
    # The profile maps categories to 'structure' and 'action' types
    schema = KernelSchema(
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
    
    container = GovernanceContainer(tmp_path, schema)
    
    # 1. Get English Diagram (Default)
    mermaid_en = container.get_self_model_diagram(lang="en")
    assert "Defines structural truth and constraints." in mermaid_en
    assert "구조적" not in mermaid_en
    
    # 2. Get Korean Diagram (Localized)
    mermaid_ko = container.get_self_model_diagram(lang="ko")
    assert "구조적 진실과 제약 조건을 정의합니다." in mermaid_ko
    assert "(패치 적용됨)" in mermaid_ko
