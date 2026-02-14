from ea_decision.evidence import Evidence, EvidenceCollection, EvidenceType


def test_evidence_type_values_are_string_compatible() -> None:
    assert str(EvidenceType.DOCUMENT) == "document"
    assert EvidenceType.BENCHMARK.value == "benchmark"


def test_collection_add_returns_new_collection_and_keeps_original() -> None:
    original = EvidenceCollection()
    evidence = Evidence(
        id="ev-1",
        type=EvidenceType.DOCUMENT,
        uri="file:///tmp/doc.md",
        title="Doc",
    )

    updated = original.add(evidence)

    assert updated.id == original.id
    assert len(original.items) == 0
    assert len(updated.items) == 1
    assert updated.items[0].id == "ev-1"
