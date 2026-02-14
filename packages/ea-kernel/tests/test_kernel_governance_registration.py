"""Tests for K2 model registration integrity."""

from __future__ import annotations

from pathlib import Path

import pytest
from ea_kernel.definition import KERNEL_SCHEMA
from ea_kernel.model_registration import (
    KernelModelRegistrationService,
    ModelRegistrationError,
)
from ea_kernel.profile_types import KernelProfile, ProfileElement, ProfileMetadata, ProfileRelation
from ea_kernel.types import KernelValidityRule


def _valid_profile(name: str = "KernelGovModel", version: str = "1.0") -> KernelProfile:
    return KernelProfile(
        name=name,
        version=version,
        kernel_version="2.5.0",
        elements=(
            ProfileElement("Widget", "structure", "Core", "Thing"),
            ProfileElement("Action", "step", "Core", "Behavior"),
        ),
        relations=(ProfileRelation("uses", "association"),),
        validity_rules=(
            KernelValidityRule(
                id="kgm-allow-01",
                source_pattern="@Thing",
                target_pattern="@Behavior",
                relationship_name="uses",
                valid=True,
                priority=40,
            ),
            KernelValidityRule(
                id="kgm-fallback-uses",
                source_pattern="*",
                target_pattern="*",
                relationship_name="uses",
                valid=False,
                priority=1,
            ),
        ),
        metadata=ProfileMetadata(standard="Kernel Gov", organization="EA"),
    )


def _invalid_profile(name: str = "BrokenModel", version: str = "1.0") -> KernelProfile:
    return KernelProfile(
        name=name,
        version=version,
        kernel_version="2.5.0",
        elements=(ProfileElement("Widget", "nonexistent_type", "Core", "Thing"),),
        relations=(ProfileRelation("uses", "association"),),
        validity_rules=(
            KernelValidityRule(
                id="broken-fallback",
                source_pattern="*",
                target_pattern="*",
                relationship_name="uses",
                valid=False,
                priority=1,
            ),
        ),
    )


@pytest.fixture
def service(tmp_path: Path) -> KernelModelRegistrationService:
    db_path = tmp_path / "profiles.db"
    return KernelModelRegistrationService(db_path, KERNEL_SCHEMA)


def test_register_valid_profile_persists_registry_and_validation(service: KernelModelRegistrationService) -> None:
    result = service.register(
        _valid_profile(),
        owner="kernel-team",
        created_by="tester",
        context={"source": "unit"},
    )

    assert result.model_name == "KernelGovModel"
    model = service.get_model("KernelGovModel")
    assert model is not None
    assert model.status == "registered"
    assert model.active_version_id is None

    versions = service.list_versions("KernelGovModel")
    assert len(versions) == 1
    assert versions[0].version == "1.0"

    runs = service.list_validation_runs(model_name="KernelGovModel")
    assert len(runs) == 1
    assert runs[0].passed is True
    assert runs[0].context["source"] == "unit"


def test_register_invalid_profile_rolls_back_without_partial_rows(
    service: KernelModelRegistrationService,
) -> None:
    with pytest.raises(ModelRegistrationError, match="Validation failed"):
        service.register(_invalid_profile(), owner="kernel-team", created_by="tester")

    assert service.get_model("BrokenModel") is None
    assert service.list_versions("BrokenModel") == ()
    assert service.list_validation_runs(model_name="BrokenModel") == ()


def test_duplicate_version_rejected_atomically(service: KernelModelRegistrationService) -> None:
    service.register(_valid_profile(version="1.0"), owner="kernel-team", created_by="tester")

    with pytest.raises(ModelRegistrationError, match="already exists"):
        service.register(_valid_profile(version="1.0"), owner="kernel-team", created_by="tester")

    versions = service.list_versions("KernelGovModel")
    assert len(versions) == 1
    runs = service.list_validation_runs(model_name="KernelGovModel")
    assert len(runs) == 1


def test_activate_sets_active_version(service: KernelModelRegistrationService) -> None:
    service.register(_valid_profile(version="1.0"), owner="kernel-team", created_by="tester")
    service.register(_valid_profile(version="2.0"), owner="kernel-team", created_by="tester")

    v2 = [v for v in service.list_versions("KernelGovModel") if v.version == "2.0"][0]
    model = service.activate("KernelGovModel", "2.0", actor="admin")

    assert model.status == "active"
    assert model.active_version_id == v2.version_id
    assert model.owner == "admin"


def test_independent_revalidation_creates_new_validation_run(
    service: KernelModelRegistrationService,
) -> None:
    service.register(_valid_profile(version="1.0"), owner="kernel-team", created_by="tester")

    rerun = service.validate_registered(
        "KernelGovModel",
        "1.0",
        context={"mode": "independent_recheck"},
    )
    assert rerun.passed is True
    assert rerun.context["mode"] == "independent_recheck"

    runs = service.list_validation_runs(model_name="KernelGovModel")
    assert len(runs) == 2
    assert runs[0].run_id == rerun.run_id

