"""Tests for Phase 3 InstanceValidator — M0 instance validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from ea_kernel.instance_validator import InstanceValidator
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.types import (
    ConformanceResult,
    InstanceElement,
    InstanceRelation,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Element validation
# ═════════════════════════════════════════════════════════════════════════════

class TestValidateElement:
    @pytest.fixture
    def validator(self):
        return InstanceValidator(KERNEL_SPEC)

    def test_valid_structure(self, validator):
        elem = InstanceElement(id="e1", entity_type="structure", name="MyClass")
        result = validator.validate_element(elem)
        assert result.valid is True
        assert result.check_type == "type_validity"

    def test_valid_item(self, validator):
        elem = InstanceElement(id="e2", entity_type="item", name="MyItem")
        result = validator.validate_element(elem)
        assert result.valid is True

    def test_valid_step(self, validator):
        elem = InstanceElement(id="e3", entity_type="step", name="Process")
        result = validator.validate_element(elem)
        assert result.valid is True

    def test_unknown_type(self, validator):
        elem = InstanceElement(id="e4", entity_type="nonexistent")
        result = validator.validate_element(elem)
        assert result.valid is False
        assert "Unknown" in result.details

    def test_abstract_type_rejected(self, validator):
        elem = InstanceElement(id="e5", entity_type="element")
        result = validator.validate_element(elem)
        assert result.valid is False
        assert "abstract" in result.details

    def test_abstract_classifier_rejected(self, validator):
        elem = InstanceElement(id="e6", entity_type="classifier")
        result = validator.validate_element(elem)
        assert result.valid is False

    def test_abstract_metatype_rejected(self, validator):
        elem = InstanceElement(id="e7", entity_type="metatype")
        result = validator.validate_element(elem)
        assert result.valid is False

    def test_result_has_element_id(self, validator):
        elem = InstanceElement(id="e1", entity_type="structure")
        result = validator.validate_element(elem)
        assert result.element_id == "e1"

    def test_valid_feature(self, validator):
        elem = InstanceElement(id="e8", entity_type="feature", name="attr1")
        result = validator.validate_element(elem)
        assert result.valid is True

    def test_valid_port(self, validator):
        elem = InstanceElement(id="e9", entity_type="port", name="p1")
        result = validator.validate_element(elem)
        assert result.valid is True

    def test_valid_state(self, validator):
        elem = InstanceElement(id="e10", entity_type="state", name="Active")
        result = validator.validate_element(elem)
        assert result.valid is True


# ═════════════════════════════════════════════════════════════════════════════
# 2. Relation validation
# ═════════════════════════════════════════════════════════════════════════════

class TestValidateRelation:
    @pytest.fixture
    def validator(self):
        return InstanceValidator(KERNEL_SPEC)

    @pytest.fixture
    def elements(self):
        return {
            "e1": InstanceElement(id="e1", entity_type="structure", name="A"),
            "e2": InstanceElement(id="e2", entity_type="item", name="B"),
            "e3": InstanceElement(id="e3", entity_type="step", name="Process"),
            "e4": InstanceElement(id="e4", entity_type="feature", name="attr"),
            "e5": InstanceElement(id="e5", entity_type="state", name="Active"),
            "e6": InstanceElement(id="e6", entity_type="state", name="Idle"),
        }

    def test_valid_association(self, validator, elements):
        rel = InstanceRelation(
            id="r1", relation_type="association",
            source_id="e1", target_id="e2",
        )
        result = validator.validate_relation(rel, elements)
        assert result.valid is True

    def test_valid_transition(self, validator, elements):
        rel = InstanceRelation(
            id="r2", relation_type="transition",
            source_id="e5", target_id="e6",
        )
        result = validator.validate_relation(rel, elements)
        assert result.valid is True

    def test_source_not_found(self, validator, elements):
        rel = InstanceRelation(
            id="r3", relation_type="association",
            source_id="missing", target_id="e1",
        )
        result = validator.validate_relation(rel, elements)
        assert result.valid is False
        assert "Source" in result.details

    def test_target_not_found(self, validator, elements):
        rel = InstanceRelation(
            id="r4", relation_type="association",
            source_id="e1", target_id="missing",
        )
        result = validator.validate_relation(rel, elements)
        assert result.valid is False
        assert "Target" in result.details

    def test_result_has_rule_id(self, validator, elements):
        rel = InstanceRelation(
            id="r1", relation_type="association",
            source_id="e1", target_id="e2",
        )
        result = validator.validate_relation(rel, elements)
        assert result.rule_id is not None


# ═════════════════════════════════════════════════════════════════════════════
# 3. Model validation
# ═════════════════════════════════════════════════════════════════════════════

class TestValidateModel:
    @pytest.fixture
    def validator(self):
        return InstanceValidator(KERNEL_SPEC)

    def test_valid_model(self, validator):
        elements = (
            InstanceElement(id="e1", entity_type="structure", name="A"),
            InstanceElement(id="e2", entity_type="item", name="B"),
        )
        relations = (
            InstanceRelation(
                id="r1", relation_type="association",
                source_id="e1", target_id="e2",
            ),
        )
        results = validator.validate_model(elements, relations)
        assert all(r.valid for r in results)

    def test_model_with_invalid_element(self, validator):
        elements = (
            InstanceElement(id="e1", entity_type="structure"),
            InstanceElement(id="e2", entity_type="nonexistent"),
        )
        results = validator.validate_model(elements, ())
        invalid = [r for r in results if not r.valid]
        assert len(invalid) == 1
        assert invalid[0].element_id == "e2"

    def test_empty_model(self, validator):
        results = validator.validate_model((), ())
        assert results == ()

    def test_model_elements_and_relations(self, validator):
        elements = (
            InstanceElement(id="e1", entity_type="structure", name="A"),
            InstanceElement(id="e2", entity_type="item", name="B"),
        )
        relations = (
            InstanceRelation(
                id="r1", relation_type="association",
                source_id="e1", target_id="e2",
            ),
        )
        results = validator.validate_model(elements, relations)
        # 2 element checks + 1 relation check
        assert len(results) == 3


# ═════════════════════════════════════════════════════════════════════════════
# 4. Type tests
# ═════════════════════════════════════════════════════════════════════════════

class TestInstanceTypes:
    def test_instance_element_frozen(self):
        elem = InstanceElement(id="e1", entity_type="structure")
        with pytest.raises(AttributeError):
            elem.id = "e2"  # type: ignore[misc]

    def test_instance_relation_frozen(self):
        rel = InstanceRelation(
            id="r1", relation_type="association",
            source_id="e1", target_id="e2",
        )
        with pytest.raises(AttributeError):
            rel.id = "r2"  # type: ignore[misc]

    def test_conformance_result_frozen(self):
        result = ConformanceResult(
            valid=True, element_id="e1", check_type="type_validity",
        )
        with pytest.raises(AttributeError):
            result.valid = False  # type: ignore[misc]

    def test_instance_element_properties(self):
        elem = InstanceElement(
            id="e1", entity_type="structure",
            properties=(("key", "value"),),
        )
        assert elem.properties == (("key", "value"),)

    def test_instance_element_defaults(self):
        elem = InstanceElement(id="e1", entity_type="structure")
        assert elem.name == ""
        assert elem.properties == ()

    def test_conformance_result_defaults(self):
        result = ConformanceResult(
            valid=True, element_id="e1", check_type="type_validity",
        )
        assert result.details == ""
        assert result.rule_id is None


# ═════════════════════════════════════════════════════════════════════════════
# 6. All concrete types validated
# ═════════════════════════════════════════════════════════════════════════════

class TestAllConcreteTypes:
    @pytest.fixture
    def validator(self):
        return InstanceValidator(KERNEL_SPEC)

    @pytest.mark.parametrize("entity_type", [
        "structure", "item", "datatype", "feature", "port",
        "step", "action", "state", "event", "expression", "package",
    ])
    def test_all_concrete_valid(self, validator, entity_type):
        elem = InstanceElement(id="e1", entity_type=entity_type, name="Test")
        result = validator.validate_element(elem)
        assert result.valid is True

    @pytest.mark.parametrize("entity_type", [
        "element", "namespace", "metatype", "classifier",
    ])
    def test_all_abstract_rejected(self, validator, entity_type):
        elem = InstanceElement(id="e1", entity_type=entity_type)
        result = validator.validate_element(elem)
        assert result.valid is False


# ═════════════════════════════════════════════════════════════════════════════
# 7. Relation validation — additional cases
# ═════════════════════════════════════════════════════════════════════════════

class TestRelationValidationAdditional:
    @pytest.fixture
    def validator(self):
        return InstanceValidator(KERNEL_SPEC)

    @pytest.fixture
    def elements(self):
        return {
            "e1": InstanceElement(id="e1", entity_type="structure", name="A"),
            "e2": InstanceElement(id="e2", entity_type="item", name="B"),
            "e3": InstanceElement(id="e3", entity_type="step", name="Proc"),
            "e4": InstanceElement(id="e4", entity_type="step", name="Next"),
            "e5": InstanceElement(id="e5", entity_type="state", name="S1"),
            "e6": InstanceElement(id="e6", entity_type="state", name="S2"),
            "e7": InstanceElement(id="e7", entity_type="feature", name="f1"),
        }

    def test_step_succession(self, validator, elements):
        rel = InstanceRelation(
            id="r1", relation_type="succession",
            source_id="e3", target_id="e4",
        )
        result = validator.validate_relation(rel, elements)
        assert result.valid is True

    def test_state_transition(self, validator, elements):
        rel = InstanceRelation(
            id="r1", relation_type="transition",
            source_id="e5", target_id="e6",
        )
        result = validator.validate_relation(rel, elements)
        assert result.valid is True

    def test_structure_specialization(self, validator, elements):
        elems = {
            "e1": InstanceElement(id="e1", entity_type="structure", name="A"),
            "e2": InstanceElement(id="e2", entity_type="structure", name="B"),
        }
        rel = InstanceRelation(
            id="r1", relation_type="specialization",
            source_id="e1", target_id="e2",
        )
        result = validator.validate_relation(rel, elems)
        assert result.valid is True

    def test_result_check_type_is_relationship(self, validator, elements):
        rel = InstanceRelation(
            id="r1", relation_type="association",
            source_id="e1", target_id="e2",
        )
        result = validator.validate_relation(rel, elements)
        assert result.check_type == "relationship"

    def test_ownership_relation(self, validator, elements):
        rel = InstanceRelation(
            id="r1", relation_type="ownership",
            source_id="e1", target_id="e7",
        )
        result = validator.validate_relation(rel, elements)
        assert result.valid is True


