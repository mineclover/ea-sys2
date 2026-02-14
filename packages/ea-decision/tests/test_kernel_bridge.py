from ea_decision.kernel_bridge import create_rule_provenance, decision_result_from_rule_asset


def test_create_rule_provenance_returns_reference_fields() -> None:
    provenance = create_rule_provenance("decision-1", "report-1")
    assert provenance["decision_ref"] == "decision-1"
    assert provenance["report_ref"] == "report-1"


def test_decision_result_from_unknown_asset_falls_back_to_raw() -> None:
    class _DummyAsset:
        def __str__(self) -> str:
            return "dummy-asset"

    result = decision_result_from_rule_asset(_DummyAsset())
    assert result == {"raw": "dummy-asset"}
