"""Tests for surface artifact definitions and extraction."""

from __future__ import annotations

from ea_projection.artifacts import (
    ArtifactExtractionRule,
    ArtifactSummary,
    ArtifactType,
    DEFAULT_EXTRACTION_RULES,
    SurfaceArtifact,
    extract_artifacts,
    summarize_artifacts,
)


# ── SurfaceArtifact ──────────────────────────────────────────────────

class TestSurfaceArtifact:

    def test_qualified_id_default(self):
        a = SurfaceArtifact(
            artifact_id="ui:page:LoginPage",
            artifact_type=ArtifactType.PAGE,
            name="LoginPage",
            source_element="LoginPage",
            tier="ui",
        )
        assert a.qualified_id == "ui:page:LoginPage"

    def test_qualified_id_custom(self):
        a = SurfaceArtifact(
            artifact_id="ui:page:LoginPage",
            artifact_type=ArtifactType.PAGE,
            name="LoginPage",
            source_element="LoginPage",
            tier="ui",
            qualified_name="my_app:ui:page:LoginPage",
        )
        assert a.qualified_id == "my_app:ui:page:LoginPage"


# ── ArtifactType ─────────────────────────────────────────────────────

class TestArtifactType:

    def test_all_types_are_strings(self):
        for at in ArtifactType:
            assert isinstance(at.value, str)

    def test_expected_types_exist(self):
        names = {at.value for at in ArtifactType}
        assert "api_endpoint" in names
        assert "page" in names
        assert "tool" in names
        assert "identifier" in names
        assert "contract" in names


# ── extract_artifacts ─────────────────────────────────────────────────

class TestExtractArtifacts:

    def test_ui_page_extraction(self):
        nodes = [
            {"name": "LoginPage", "category": "Page"},
            {"name": "Dashboard", "category": "Page"},
        ]
        tiers = {"LoginPage": "ui", "Dashboard": "ui"}

        artifacts = extract_artifacts(nodes, tiers)

        assert len(artifacts) == 2
        assert all(a.artifact_type == ArtifactType.PAGE for a in artifacts)
        assert artifacts[0].name == "LoginPage"
        assert artifacts[0].tier == "ui"

    def test_function_api_endpoint_extraction(self):
        nodes = [
            {"name": "UserService", "category": "ActiveStructure"},
        ]
        tiers = {"UserService": "function"}

        artifacts = extract_artifacts(nodes, tiers)

        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == ArtifactType.API_ENDPOINT
        assert artifacts[0].name == "UserService"

    def test_data_schema_extraction(self):
        nodes = [
            {"name": "UserModel", "category": "PassiveStructure"},
        ]
        tiers = {"UserModel": "data"}

        artifacts = extract_artifacts(nodes, tiers)

        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == ArtifactType.DATA_SCHEMA

    def test_decision_contract_extraction(self):
        nodes = [
            {"name": "ArchGoal", "category": "Goal"},
        ]
        tiers = {"ArchGoal": "decision"}

        artifacts = extract_artifacts(nodes, tiers)

        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == ArtifactType.CONTRACT

    def test_decision_event_extraction(self):
        nodes = [
            {"name": "SystemEvent", "category": "Event"},
        ]
        tiers = {"SystemEvent": "decision"}

        artifacts = extract_artifacts(nodes, tiers)

        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == ArtifactType.EVENT

    def test_evidence_identifier_extraction(self):
        nodes = [
            {"name": "AuditEvidence", "category": "PassiveStructure"},
        ]
        tiers = {"AuditEvidence": "evidence"}

        artifacts = extract_artifacts(nodes, tiers)

        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == ArtifactType.IDENTIFIER

    def test_no_tier_skips_node(self):
        nodes = [
            {"name": "Unclassified", "category": "Page"},
        ]
        tiers = {}

        artifacts = extract_artifacts(nodes, tiers)
        assert len(artifacts) == 0

    def test_no_matching_rule_skips_node(self):
        nodes = [
            {"name": "Unknown", "category": "UnknownCategory"},
        ]
        tiers = {"Unknown": "ui"}

        artifacts = extract_artifacts(nodes, tiers)
        assert len(artifacts) == 0

    def test_deduplication(self):
        nodes = [
            {"name": "Same", "category": "Page"},
            {"name": "Same", "category": "Page"},
        ]
        tiers = {"Same": "ui"}

        artifacts = extract_artifacts(nodes, tiers)
        assert len(artifacts) == 1

    def test_profile_name_qualifies(self):
        nodes = [
            {"name": "LoginPage", "category": "Page"},
        ]
        tiers = {"LoginPage": "ui"}

        artifacts = extract_artifacts(nodes, tiers, profile_name="archimate")

        assert len(artifacts) == 1
        assert artifacts[0].qualified_name == "archimate:ui:page:LoginPage"

    def test_custom_rules(self):
        custom_rules = (
            ArtifactExtractionRule(
                tier="custom",
                categories=("MyCategory",),
                artifact_type=ArtifactType.CONFIGURATION,
            ),
        )
        nodes = [
            {"name": "AppConfig", "category": "MyCategory"},
        ]
        tiers = {"AppConfig": "custom"}

        artifacts = extract_artifacts(nodes, tiers, rules=custom_rules)

        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == ArtifactType.CONFIGURATION

    def test_name_patterns_filter(self):
        custom_rules = (
            ArtifactExtractionRule(
                tier="data",
                categories=("PassiveStructure",),
                artifact_type=ArtifactType.IDENTIFIER,
                name_patterns=("Evidence", "Audit"),
            ),
        )
        nodes = [
            {"name": "AuditLog", "category": "PassiveStructure"},
            {"name": "UserData", "category": "PassiveStructure"},
        ]
        tiers = {"AuditLog": "data", "UserData": "data"}

        artifacts = extract_artifacts(nodes, tiers, rules=custom_rules)

        assert len(artifacts) == 1
        assert artifacts[0].name == "AuditLog"

    def test_name_exclude_patterns(self):
        custom_rules = (
            ArtifactExtractionRule(
                tier="data",
                categories=("PassiveStructure",),
                artifact_type=ArtifactType.DATA_SCHEMA,
                name_exclude_patterns=("Internal",),
            ),
        )
        nodes = [
            {"name": "PublicModel", "category": "PassiveStructure"},
            {"name": "InternalCache", "category": "PassiveStructure"},
        ]
        tiers = {"PublicModel": "data", "InternalCache": "data"}

        artifacts = extract_artifacts(nodes, tiers, rules=custom_rules)

        assert len(artifacts) == 1
        assert artifacts[0].name == "PublicModel"

    def test_empty_nodes(self):
        artifacts = extract_artifacts([], {})
        assert len(artifacts) == 0

    def test_description_preserved(self):
        nodes = [
            {"name": "LoginPage", "category": "Page", "description": "Login screen"},
        ]
        tiers = {"LoginPage": "ui"}

        artifacts = extract_artifacts(nodes, tiers)

        assert artifacts[0].description == "Login screen"


# ── summarize_artifacts ───────────────────────────────────────────────

class TestSummarizeArtifacts:

    def test_empty(self):
        summary = summarize_artifacts(())
        assert summary.total_artifacts == 0
        assert summary.by_type == ()
        assert summary.by_tier == ()

    def test_mixed(self):
        artifacts = (
            SurfaceArtifact("a1", ArtifactType.PAGE, "P1", "P1", "ui"),
            SurfaceArtifact("a2", ArtifactType.PAGE, "P2", "P2", "ui"),
            SurfaceArtifact("a3", ArtifactType.API_ENDPOINT, "S1", "S1", "function"),
        )
        summary = summarize_artifacts(artifacts)

        assert summary.total_artifacts == 3
        type_dict = dict(summary.by_type)
        assert type_dict["page"] == 2
        assert type_dict["api_endpoint"] == 1
        tier_dict = dict(summary.by_tier)
        assert tier_dict["ui"] == 2
        assert tier_dict["function"] == 1


# ── DEFAULT_EXTRACTION_RULES ─────────────────────────────────────────

class TestDefaultExtractionRules:

    def test_rules_exist(self):
        assert len(DEFAULT_EXTRACTION_RULES) > 0

    def test_all_tiers_covered(self):
        tiers_covered = {r.tier for r in DEFAULT_EXTRACTION_RULES}
        assert "ui" in tiers_covered
        assert "function" in tiers_covered
        assert "data" in tiers_covered
        assert "decision" in tiers_covered
        assert "evidence" in tiers_covered

    def test_rules_are_frozen(self):
        for rule in DEFAULT_EXTRACTION_RULES:
            assert isinstance(rule, ArtifactExtractionRule)
