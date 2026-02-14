"""Schema file metadata and content access."""

from pathlib import Path

from ea_kernel.types import SchemaFile, SchemaType


SCHEMA_DIR = Path(__file__).parent.parent / "schemas"

SCHEMA_FILES: tuple[SchemaFile, ...] = (
    SchemaFile("kernel.tql", 0, SchemaType.DEFINE,
               "Kernel metamodel schema: L1-L4 types and relations"),
    SchemaFile("seed.tql", 1, SchemaType.INSERT,
               "Seed data: root namespace and primitive datatypes"),
)


def get_schema_content(filename: str) -> str:
    """Read a schema file's content by filename."""
    path = SCHEMA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")
    return path.read_text(encoding="utf-8")
