"""Development Topology self-description verification.

EA 시스템의 패키지·모듈·의존성을 커널 프로파일로 모델링한
80-development.toml을 로드하고 구조적 타당성을 검증한다.
"""

from pathlib import Path

from ea_kernel.profile_loader import load_profile
from ea_kernel.profile_quality_gate import check_profile_quality
from ea_kernel.spec import KERNEL_SPEC

_TOML_PATH = (
    Path(__file__).parent.parent
    / "src" / "ea_kernel" / "profiles" / "ea_sys" / "80-development.toml"
)
_PROFILE = load_profile(_TOML_PATH)


class TestDevelopmentTopologyProfile:
    """프로파일 기본 구조 검증."""

    def test_profile_loads_without_error(self):
        assert _PROFILE.name == "EASystem-Development"
        assert _PROFILE.version == "1.0.0"

    def test_element_count(self):
        assert len(_PROFILE.elements) >= 45

    def test_relation_count(self):
        assert len(_PROFILE.relations) == 10

    def test_all_packages_present(self):
        """8 LayerPackage elements covering all system layers."""
        packages = {e.name for e in _PROFILE.elements if e.category == "LayerPackage"}
        expected = {
            "ProfileFramework", "InfraLayer", "DecisionLayer", "NeedsLayer",
            "KernelLayer", "FlowLayer", "GovernanceLayer", "VizLayer",
        }
        assert packages == expected

    def test_layers_present(self):
        layers = _PROFILE.domain_layers()
        for layer in (
            "Foundation", "Infrastructure", "Decision", "Needs",
            "Kernel", "Flow", "Management", "Visualization",
        ):
            assert layer in layers, f"Missing layer: {layer}"

    def test_dependency_direction_rules(self):
        """역방향 의존 deny 규칙이 존재하고 유효한지 검증."""
        deny_rules = [
            r for r in _PROFILE.validity_rules
            if not r.valid and r.relationship_name == "depends_on" and r.priority > 1
        ]
        assert len(deny_rules) >= 11, f"Expected >=11 deny rules, got {len(deny_rules)}"

        # Verify specific critical denies
        deny_pairs = {(r.source_pattern, r.target_pattern) for r in deny_rules}
        assert ("ProfileFramework", "KernelLayer") in deny_pairs
        assert ("KernelLayer", "GovernanceLayer") in deny_pairs
        assert ("FlowLayer", "GovernanceLayer") in deny_pairs

    def test_quality_gate_passes(self):
        """커널 품질 게이트 통과: dead rule, conflicting rule 없음."""
        qr = check_profile_quality(_PROFILE, KERNEL_SPEC)
        assert qr.passed, (
            f"Quality gate failed:\n"
            f"  dead_rules={qr.dead_rules}\n"
            f"  conflicting_rules={qr.conflicting_rules}\n"
            f"  missing_fallbacks={qr.missing_fallbacks}\n"
            f"  invalid_patterns={qr.invalid_patterns}\n"
            f"  invalid_kernel_refs={qr.invalid_kernel_refs}"
        )

    def test_topology_graph_connected(self):
        """고립 노드 없음 — 모든 요소가 최소 1개 규칙에 참여."""
        from ea_kernel.profile_graph import ProfileTopologyGraph

        graph = ProfileTopologyGraph(_PROFILE)
        isolated = []
        for node in graph.nodes:
            if not graph.outgoing(node) and not graph.incoming(node):
                isolated.append(node)
        assert not isolated, f"Isolated nodes: {isolated}"
