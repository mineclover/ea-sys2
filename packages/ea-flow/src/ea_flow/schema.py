
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SchemaSpec(ABC):
    """Base class for all schema specifications in the logic layer."""
    format: str

    @abstractmethod
    def validate(self, data: Any) -> bool:
        """Validate data against this schema."""
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize schema to a dictionary."""
        pass

class JsonSchema2020Spec(SchemaSpec):
    """Implementation for JSON Schema 2020-12 draft."""

    def __init__(self, raw_schema: dict[str, Any]):
        super().__init__(format="jsonschema-2020-12")
        self.raw_schema = raw_schema
        # Proactively import to avoid heavy dependencies if not used
        from jsonschema.validators import validator_for
        self._validator_cls = validator_for(raw_schema)
        # In actual production, we would use a more specific validator for 2020-12 if available
        # or customize the registry. For now, we use the best available.
        self._validator = self._validator_cls(raw_schema)

    def validate(self, data: Any) -> bool:
        try:
            self._validator.validate(data)
            return True
        except Exception:
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "schema": self.raw_schema
        }

class DbSchemaSpec(SchemaSpec):
    """Represents a database table/view schema (DDL approach)."""

    def __init__(self, table_name: str, columns: dict[str, str], ddl: str | None = None):
        super().__init__(format="db-schema")
        self.table_name = table_name
        self.columns = columns # column_name: type_string
        self.ddl = ddl

    def validate(self, data: Any) -> bool:
        # DB schema validation in the logic layer is usually structural check of dict keys
        if not isinstance(data, dict):
            return False
        # Simplistic check: all required columns present?
        return all(col in data for col in self.columns)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "table_name": self.table_name,
            "columns": self.columns,
            "ddl": self.ddl
        }
