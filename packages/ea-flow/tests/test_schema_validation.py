
from ea_flow.schema import DbSchemaSpec, JsonSchema2020Spec


def test_json_schema_2020_validation():
    # A simple 2020-12 schema
    raw_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer", "minimum": 0}
        },
        "required": ["name"]
    }

    spec = JsonSchema2020Spec(raw_schema)

    # Valid data
    assert spec.validate({"name": "Alice", "age": 30}) is True
    assert spec.validate({"name": "Bob"}) is True # age is optional

    # Invalid data
    assert spec.validate({"age": 30}) is False # name missing
    assert spec.validate({"name": "Alice", "age": -1}) is False # age minimum fail
    assert spec.validate("not an object") is False

def test_db_schema_validation():
    spec = DbSchemaSpec(
        table_name="users",
        columns={"id": "INT", "name": "TEXT"}
    )

    assert spec.validate({"id": 1, "name": "Alice"}) is True
    assert spec.validate({"id": 1}) is False # name missing
    assert spec.validate("invalid") is False
