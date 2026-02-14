"""Types for ea-kernel contract snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class ContractPaths:
    """Resolved snapshot file paths."""

    contract_dir: Path
    schema_path: Path
    rules_path: Path
    vectors_path: Path


@dataclass(frozen=True)
class ContractBundle:
    """Loaded contract payloads."""

    paths: ContractPaths
    schema: JsonObject
    rules: JsonObject
    vectors: JsonObject

    @property
    def kernel_version(self) -> str:
        """Kernel version declared by the schema snapshot."""
        version = self.schema.get("kernel_version")
        if not isinstance(version, str):
            return ""
        return version
