"""Tests for TypeQL schema parsing and consistency."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ea_kernel.definition import KERNEL_SCHEMA
from ea_kernel.schema import SCHEMA_FILES, get_schema_content, parse_typeql


class TestSchemaFiles:
    """Verify schema file management."""

    def test_schema_files_ordered(self):
        orders = [sf.order for sf in SCHEMA_FILES]
        assert orders == sorted(orders)

    def test_kernel_tql_exists(self):
        content = get_schema_content("kernel.tql")
        assert len(content) > 0
        assert "define" in content

    def test_seed_tql_exists(self):
        content = get_schema_content("seed.tql")
        assert len(content) > 0
        assert "insert" in content

    def test_nonexistent_file_raises(self):
        try:
            get_schema_content("nonexistent.tql")
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("Should have raised FileNotFoundError")


class TestSchemaParser:
    """Verify the pure Python TypeQL parser."""

    def setup_method(self):
        content = get_schema_content("kernel.tql")
        self.schema = parse_typeql(content)

    def test_parses_attributes(self):
        attr_names = {a.name for a in self.schema.attributes}
        assert "uid" in attr_names
        assert "name" in attr_names
        assert "is_abstract" in attr_names
        assert "guard_expr" in attr_names

    def test_attribute_types(self):
        by_name = {a.name: a.value_type for a in self.schema.attributes}
        assert by_name["uid"] == "string"
        assert by_name["is_abstract"] == "boolean"
        assert by_name["multiplicity_lower"] == "integer"

    def test_parses_entities(self):
        entity_names = {e.name for e in self.schema.entities}
        # L1
        assert "element" in entity_names
        assert "namespace" in entity_names
        assert "metatype" in entity_names
        assert "feature" in entity_names
        assert "classifier" in entity_names
        assert "structure" in entity_names
        assert "datatype" in entity_names
        # L4
        assert "step" in entity_names
        assert "action" in entity_names
        assert "expression" in entity_names
        assert "state" in entity_names

    def test_parses_relations(self):
        rel_names = {r.name for r in self.schema.relations}
        # L2
        assert "membership" in rel_names
        assert "specialization" in rel_names
        assert "connector" in rel_names
        # L3
        assert "flow" in rel_names
        assert "succession" in rel_names
        assert "triggering" in rel_names

    def test_entity_inheritance(self):
        by_name = {e.name: e for e in self.schema.entities}
        assert by_name["namespace"].parent == "element"
        assert by_name["metatype"].parent == "namespace"
        assert by_name["feature"].parent == "metatype"
        assert by_name["step"].parent == "feature"
        assert by_name["action"].parent == "step"

    def test_entity_abstract(self):
        by_name = {e.name: e for e in self.schema.entities}
        assert by_name["element"].is_abstract
        assert by_name["namespace"].is_abstract
        assert by_name["metatype"].is_abstract
        assert by_name["classifier"].is_abstract
        assert not by_name["feature"].is_abstract
        assert not by_name["structure"].is_abstract
        assert not by_name["package"].is_abstract

    def test_relation_inheritance(self):
        by_name = {r.name: r for r in self.schema.relations}
        assert by_name["flow"].parent == "connector"
        assert by_name["succession"].parent == "connector"
        assert by_name["interaction"].parent == "connector"
        assert by_name["membership"].parent is None

    def test_relation_roles(self):
        by_name = {r.name: r for r in self.schema.relations}
        mem_roles = {r.name for r in by_name["membership"].roles}
        assert "container" in mem_roles
        assert "member" in mem_roles

    def test_entity_owns_key(self):
        by_name = {e.name: e for e in self.schema.entities}
        assert "uid" in by_name["element"].owns_key

    def test_entity_plays(self):
        by_name = {e.name: e for e in self.schema.entities}
        assert "membership:member" in by_name["element"].plays
        assert "membership:container" in by_name["namespace"].plays


class TestSchemaDefinitionConsistency:
    """Verify that parsed .tql matches Python definitions."""

    # Infrastructure entities/attributes live in kernel.tql but not in definition.py.
    # They are intentionally outside the metamodel hierarchy (Rule Corpus mirror).
    INFRA_ENTITIES = {"validity_rule"}
    INFRA_ATTRIBUTES = {
        "rule_id", "source_pattern", "target_pattern", "relationship_name",
        "is_valid", "rule_priority", "rule_notes", "rule_domain", "rule_tag",
        "rule_category", "rule_confidence", "rule_source",
        "established_version", "rationale",
    }

    def setup_method(self):
        content = get_schema_content("kernel.tql")
        self.parsed = parse_typeql(content)

    def test_entity_count_matches(self):
        parsed_names = {e.name for e in self.parsed.entities} - self.INFRA_ENTITIES
        def_names = {e.name for e in KERNEL_SCHEMA.entities}
        assert parsed_names == def_names, (
            f"Mismatch: parsed={parsed_names - def_names}, "
            f"definition={def_names - parsed_names}"
        )

    def test_relation_count_matches(self):
        parsed_names = {r.name for r in self.parsed.relations}
        def_names = {r.name for r in KERNEL_SCHEMA.relations}
        assert parsed_names == def_names, (
            f"Mismatch: parsed={parsed_names - def_names}, "
            f"definition={def_names - parsed_names}"
        )

    def test_attribute_count_matches(self):
        parsed_names = {a.name for a in self.parsed.attributes} - self.INFRA_ATTRIBUTES
        def_names = {a.name for a in KERNEL_SCHEMA.attributes}
        assert parsed_names == def_names, (
            f"Mismatch: parsed={parsed_names - def_names}, "
            f"definition={def_names - parsed_names}"
        )

    def test_entity_parents_match(self):
        parsed_by_name = {e.name: e for e in self.parsed.entities}
        for entity in KERNEL_SCHEMA.entities:
            parsed = parsed_by_name.get(entity.name)
            assert parsed is not None, f"Missing parsed entity: {entity.name}"
            assert parsed.parent == entity.parent, (
                f"{entity.name}: parsed parent={parsed.parent}, "
                f"def parent={entity.parent}"
            )

    def test_relation_parents_match(self):
        parsed_by_name = {r.name: r for r in self.parsed.relations}
        for rel in KERNEL_SCHEMA.relations:
            parsed = parsed_by_name.get(rel.name)
            assert parsed is not None, f"Missing parsed relation: {rel.name}"
            assert parsed.parent == rel.parent, (
                f"{rel.name}: parsed parent={parsed.parent}, "
                f"def parent={rel.parent}"
            )
