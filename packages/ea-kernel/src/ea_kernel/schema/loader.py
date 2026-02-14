"""Schema loader for TypeDB — loads kernel.tql and seed.tql in order."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ea_kernel.schema._files import SCHEMA_FILES, get_schema_content
from ea_kernel.types import SchemaType

if TYPE_CHECKING:
    from ea_kernel.client.connection import KernelDBClient


@dataclass
class FileLoadResult:
    filename: str
    schema_type: SchemaType
    success: bool = True
    error: str | None = None


@dataclass
class SchemaLoadReport:
    results: list[FileLoadResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def errors(self) -> list[FileLoadResult]:
        return [r for r in self.results if not r.success]

    def summary(self) -> str:
        lines = []
        for r in self.results:
            status = "OK" if r.success else f"FAIL: {r.error}"
            lines.append(f"  [{r.schema_type.value:6s}] {r.filename:20s} {status}")
        return "\n".join(lines)


class SchemaLoader:
    """Loads kernel schema files into TypeDB in dependency order."""

    def __init__(self, client: KernelDBClient) -> None:
        self._client = client

    def load_all(self) -> SchemaLoadReport:
        report = SchemaLoadReport()
        for sf in SCHEMA_FILES:
            result = self._load_file(sf)
            report.results.append(result)
            if not result.success:
                break
        return report

    def _load_file(self, sf) -> FileLoadResult:
        try:
            content = get_schema_content(sf.filename)
            if sf.schema_type == SchemaType.DEFINE:
                self._execute_define(content)
            else:
                self._execute_insert(content)
            return FileLoadResult(sf.filename, sf.schema_type, success=True)
        except Exception as exc:
            return FileLoadResult(sf.filename, sf.schema_type, success=False, error=str(exc))

    def _execute_define(self, content: str) -> None:
        """Extract and execute the define block."""
        lines: list[str] = []
        in_define = False
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped == "define":
                in_define = True
                lines.append("define")
                continue
            if stripped.startswith("insert"):
                break
            if in_define and not stripped.startswith("#") and stripped:
                lines.append(line)

        if lines:
            self._client.execute_schema("\n".join(lines))

    def _execute_insert(self, content: str) -> None:
        """Extract and execute the insert block."""
        lines: list[str] = []
        in_insert = False
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped == "insert":
                in_insert = True
                lines.append("insert")
                continue
            if in_insert and not stripped.startswith("#") and stripped:
                lines.append(line)

        if lines:
            self._client.execute_write("\n".join(lines))
