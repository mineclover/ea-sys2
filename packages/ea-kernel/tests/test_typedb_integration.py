"""Integration tests — real TypeDB queries against the kernel schema.

Requires a running TypeDB instance at localhost:1729.
Run with: pytest tests/test_typedb_integration.py -v
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

try:
    from ea_kernel.client.connection import KernelDBClient
    from ea_kernel.schema.loader import SchemaLoader
    HAS_TYPEDB = True
except ImportError:
    HAS_TYPEDB = False

pytestmark = pytest.mark.skipif(not HAS_TYPEDB, reason="typedb-driver not installed")

DB_NAME = f"kernel_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def client():
    """Module-scoped client with a fresh kernel database."""
    c = KernelDBClient()
    try:
        c.driver.databases.all()
    except Exception:
        pytest.skip("TypeDB not available at localhost:1729")

    c.reset_database(DB_NAME)
    loader = SchemaLoader(c)
    report = loader.load_all()
    if not report.success:
        errors = "; ".join(r.error or "" for r in report.errors)
        pytest.fail(f"Schema loading failed: {errors}")

    yield c

    c.drop_database(DB_NAME)
    c.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Seed data verification
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeedData:
    """Verify seed data was loaded correctly."""

    def test_root_namespace_exists(self, client):
        results = client.execute_read(
            'match $p isa package, has uid "kernel:root"; select $p;'
        )
        assert len(list(results)) == 1

    def test_primitive_types_count(self, client):
        results = client.execute_read(
            "match $d isa datatype; select $d;"
        )
        # Boolean, Integer, Real, String, UnlimitedNatural
        assert len(list(results)) == 5

    def test_primitive_type_names(self, client):
        results = client.execute_read(
            "match $d isa datatype, has name $n; select $n;"
        )
        names = {row.get("n").get_string() for row in results}
        assert names == {"Boolean", "Integer", "Real", "String", "UnlimitedNatural"}

    def test_membership_relations(self, client):
        results = client.execute_read(
            "match (container: $c, member: $m) isa membership; select $c, $m;"
        )
        assert len(list(results)) == 5  # 5 primitives in root


# ═══════════════════════════════════════════════════════════════════════════════
# L1 Structure — entity hierarchy
# ═══════════════════════════════════════════════════════════════════════════════

class TestEntityHierarchy:
    """Test TypeDB type hierarchy with real instances."""

    def test_insert_structure(self, client):
        client.execute_write(
            'insert $s isa structure, '
            'has uid "test:struct/person", '
            'has name "Person", '
            'has is_abstract false;'
        )
        results = client.execute_read(
            'match $s isa structure, has uid "test:struct/person"; select $s;'
        )
        assert len(list(results)) == 1

    def test_insert_feature(self, client):
        client.execute_write(
            'insert $f isa feature, '
            'has uid "test:feat/person_name", '
            'has name "name", '
            'has multiplicity_lower 1, '
            'has multiplicity_upper 1;'
        )
        results = client.execute_read(
            'match $f isa feature, has uid "test:feat/person_name"; select $f;'
        )
        assert len(list(results)) == 1

    def test_polymorphic_query_metatype(self, client):
        """Query for metatype should return structure, feature, datatype, state."""
        results = client.execute_read(
            "match $m isa metatype, has name $n; select $n;"
        )
        names = {row.get("n").get_string() for row in results}
        # Person (structure), name (feature), + 5 seed datatypes
        assert "Person" in names
        assert "name" in names
        # All 5 primitive datatypes
        assert "Boolean" in names

    def test_polymorphic_query_namespace(self, client):
        """Query for namespace should return package, structure, datatype, feature, etc."""
        results = client.execute_read(
            "match $ns isa namespace, has name $n; select $n;"
        )
        names = {row.get("n").get_string() for row in results}
        # package (kernel root), structure (Person), feature (name), datatypes
        assert "kernel" in names
        assert "Person" in names

    def test_polymorphic_query_element(self, client):
        """Query for element (root) should return everything."""
        results = client.execute_read(
            "match $e isa element, has uid $u; select $u;"
        )
        uids = {row.get("u").get_string() for row in results}
        assert "kernel:root" in uids
        assert "test:struct/person" in uids
        assert "test:feat/person_name" in uids


# ═══════════════════════════════════════════════════════════════════════════════
# L2 Relationship — structural connections
# ═══════════════════════════════════════════════════════════════════════════════

class TestRelationships:
    """Test L2 structural relationships."""

    def test_specialization(self, client):
        """Structure specializes another structure."""
        client.execute_write(
            'insert $s isa structure, '
            'has uid "test:struct/employee", '
            'has name "Employee", '
            'has is_abstract false;'
        )
        client.execute_write(
            'match '
            '$sup isa structure, has uid "test:struct/person"; '
            '$sub isa structure, has uid "test:struct/employee"; '
            'insert (supertype: $sup, subtype: $sub) isa specialization, '
            'has uid "test:spec/employee_person";'
        )
        results = client.execute_read(
            'match (supertype: $sup, subtype: $sub) isa specialization; '
            '$sup has name $sn; $sub has name $en; select $sn, $en;'
        )
        rows = list(results)
        assert len(rows) == 1
        assert rows[0].get("sn").get_string() == "Person"
        assert rows[0].get("en").get_string() == "Employee"

    def test_feature_typing(self, client):
        """Feature typed by a datatype."""
        client.execute_write(
            'match '
            '$f isa feature, has uid "test:feat/person_name"; '
            '$t isa datatype, has uid "kernel:type/string"; '
            'insert (typed_feature: $f, typing: $t) isa feature_typing, '
            'has uid "test:ft/name_string";'
        )
        results = client.execute_read(
            'match (typed_feature: $f, typing: $t) isa feature_typing; '
            '$f has name $fn; $t has name $tn; select $fn, $tn;'
        )
        rows = list(results)
        assert len(rows) == 1
        assert rows[0].get("fn").get_string() == "name"
        assert rows[0].get("tn").get_string() == "String"

    def test_ownership(self, client):
        """Structure owns a feature."""
        client.execute_write(
            'match '
            '$s isa structure, has uid "test:struct/person"; '
            '$f isa feature, has uid "test:feat/person_name"; '
            'insert (owner: $s, owned: $f) isa ownership, '
            'has uid "test:own/person_name";'
        )
        results = client.execute_read(
            'match (owner: $s, owned: $f) isa ownership; '
            '$s has name $sn; $f has name $fn; select $sn, $fn;'
        )
        rows = list(results)
        assert len(rows) == 1
        assert rows[0].get("sn").get_string() == "Person"
        assert rows[0].get("fn").get_string() == "name"

    def test_connector_between_features(self, client):
        """Connector links two features."""
        client.execute_write(
            'insert $f isa feature, '
            'has uid "test:feat/order_id", '
            'has name "orderId", '
            'has multiplicity_lower 1, '
            'has multiplicity_upper 1;'
        )
        client.execute_write(
            'match '
            '$a isa feature, has uid "test:feat/person_name"; '
            '$b isa feature, has uid "test:feat/order_id"; '
            'insert (source: $a, target: $b) isa connector, '
            'has uid "test:conn/name_order", '
            'has name "nameToOrder";'
        )
        results = client.execute_read(
            'match (source: $s, target: $t) isa connector; '
            '$s has name $sn; $t has name $tn; select $sn, $tn;'
        )
        rows = list(results)
        assert len(rows) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# L3 Behavioral — L2→L3 transition (polymorphic queries)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBehavioralQualification:
    """Test L2→L3 behavioral qualification and polymorphic queries."""

    def test_insert_flow(self, client):
        """Flow is a behavioral Connector with direction."""
        client.execute_write(
            'insert $p1 isa feature, '
            'has uid "test:feat/port_in", '
            'has name "portIn";'
        )
        client.execute_write(
            'insert $p2 isa feature, '
            'has uid "test:feat/port_out", '
            'has name "portOut";'
        )
        client.execute_write(
            'match '
            '$a isa feature, has uid "test:feat/port_in"; '
            '$b isa feature, has uid "test:feat/port_out"; '
            'insert (source: $a, target: $b) isa flow, '
            'has uid "test:flow/data", '
            'has name "dataFlow", '
            'has direction "out";'
        )
        results = client.execute_read(
            'match $f isa flow, has direction $d; select $f, $d;'
        )
        assert len(list(results)) == 1

    def test_flow_is_also_connector(self, client):
        """Polymorphic query: querying Connector should return Flow too."""
        results = client.execute_read(
            'match (source: $s, target: $t) isa connector, has name $n; '
            'select $n;'
        )
        names = {row.get("n").get_string() for row in results}
        # Both the plain connector AND the flow should appear
        assert "nameToOrder" in names
        assert "dataFlow" in names

    def test_insert_succession(self, client):
        """Succession links steps in temporal order."""
        client.execute_write(
            'insert $s1 isa action, '
            'has uid "test:action/validate", '
            'has name "validate";'
        )
        client.execute_write(
            'insert $s2 isa action, '
            'has uid "test:action/process", '
            'has name "process";'
        )
        client.execute_write(
            'match '
            '$a isa action, has uid "test:action/validate"; '
            '$b isa action, has uid "test:action/process"; '
            'insert (predecessor: $a, successor: $b) isa succession, '
            'has uid "test:succ/val_proc", '
            'has name "validateThenProcess";'
        )
        results = client.execute_read(
            'match (predecessor: $p, successor: $s) isa succession; '
            '$p has name $pn; $s has name $sn; select $pn, $sn;'
        )
        rows = list(results)
        assert len(rows) == 1
        assert rows[0].get("pn").get_string() == "validate"
        assert rows[0].get("sn").get_string() == "process"

    def test_succession_is_also_connector(self, client):
        """Succession should appear in connector queries."""
        results = client.execute_read(
            "match $c isa connector, has name $n; select $n;"
        )
        names = {row.get("n").get_string() for row in results}
        assert "validateThenProcess" in names

    def test_actions_are_features(self, client):
        """Actions (L4) are features (L1) — polymorphic hierarchy."""
        results = client.execute_read(
            "match $f isa feature, has name $n; select $n;"
        )
        names = {row.get("n").get_string() for row in results}
        assert "validate" in names
        assert "process" in names

    def test_actions_are_steps(self, client):
        """Actions are steps."""
        results = client.execute_read(
            "match $s isa step, has name $n; select $n;"
        )
        names = {row.get("n").get_string() for row in results}
        assert "validate" in names
        assert "process" in names


# ═══════════════════════════════════════════════════════════════════════════════
# Complex queries — type hierarchy exploration
# ═══════════════════════════════════════════════════════════════════════════════

class TestTypeHierarchyExploration:
    """Complex queries demonstrating TypeDB's type hierarchy strength."""

    def test_find_all_features_of_person(self, client):
        """Navigate ownership to find features of a structure."""
        results = client.execute_read(
            'match '
            '$s isa structure, has name "Person"; '
            '(owner: $s, owned: $f) isa ownership; '
            '$f has name $fn; '
            'select $fn;'
        )
        names = {row.get("fn").get_string() for row in results}
        assert "name" in names

    def test_find_type_of_feature(self, client):
        """Navigate feature_typing to find what types a feature."""
        results = client.execute_read(
            'match '
            '$f isa feature, has name "name"; '
            '(typed_feature: $f, typing: $t) isa feature_typing; '
            '$t has name $tn; '
            'select $tn;'
        )
        names = {row.get("tn").get_string() for row in results}
        assert "String" in names

    def test_find_subtypes(self, client):
        """Find all specializations of Person."""
        results = client.execute_read(
            'match '
            '$sup isa structure, has name "Person"; '
            '(supertype: $sup, subtype: $sub) isa specialization; '
            '$sub has name $n; '
            'select $n;'
        )
        names = {row.get("n").get_string() for row in results}
        assert "Employee" in names

    def test_behavioral_chain_query(self, client):
        """Find the behavioral sequence: what comes after validate?"""
        results = client.execute_read(
            'match '
            '$a isa action, has name "validate"; '
            '(predecessor: $a, successor: $next) isa succession; '
            '$next has name $nn; '
            'select $nn;'
        )
        names = {row.get("nn").get_string() for row in results}
        assert "process" in names

    def test_count_all_elements(self, client):
        """Count total instances by type category."""
        # All metatypes (structure, datatype, feature, state + their instances)
        results = client.execute_read(
            "match $m isa metatype; select $m;"
        )
        metatype_count = len(list(results))
        # 5 datatypes + 1 Person + 1 Employee + features + actions
        assert metatype_count >= 8

    def test_mixed_structural_behavioral_query(self, client):
        """Cross-layer query: find structure → ownership → feature → flow."""
        results = client.execute_read(
            'match '
            '$s isa structure, has name "Person"; '
            '(owner: $s, owned: $f) isa ownership; '
            '(source: $f, target: $t) isa connector; '
            '$t has name $tn; '
            'select $tn;'
        )
        # Person owns name → name connects to orderId
        names = {row.get("tn").get_string() for row in results}
        assert "orderId" in names
