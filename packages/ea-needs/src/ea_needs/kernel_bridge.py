"""Kernel integration bridge (N3).

This is the only module that imports ea_kernel types (lazily).
All other modules use string-based ID references for Kernel entities.
"""

from __future__ import annotations

from typing import Any


def validate_kernel_refs(
    refs: list[str],
    schema: Any = None,
) -> dict[str, bool]:
    """Check whether kernel entity names exist in the loaded schema.

    Args:
        refs: List of kernel entity name strings to validate.
        schema: Optional KernelSchema instance. If None, loads the default.

    Returns:
        Dict mapping each ref to True (found) or False (not found).
    """
    try:
        from ea_kernel.definition import KERNEL_SCHEMA

        target_schema = schema if schema is not None else KERNEL_SCHEMA
        entity_names = {e.name for e in target_schema.entities}
        return {ref: ref in entity_names for ref in refs}
    except ImportError:
        # ea_kernel not available — cannot validate, return all False
        return dict.fromkeys(refs, False)


def kernel_entity_summary(
    name: str,
    schema: Any = None,
) -> dict[str, Any] | None:
    """Retrieve metadata for a kernel entity by name.

    Args:
        name: Entity name to look up.
        schema: Optional KernelSchema instance. If None, loads the default.

    Returns:
        Dict with entity metadata, or None if not found.
    """
    try:
        from ea_kernel.definition import KERNEL_SCHEMA

        target_schema = schema if schema is not None else KERNEL_SCHEMA
        for entity in target_schema.entities:
            if entity.name == name:
                return {
                    "name": entity.name,
                    "layer": entity.layer.value if hasattr(entity.layer, "value") else str(entity.layer),
                    "description": entity.description,
                    "is_abstract": entity.is_abstract,
                }
        return None
    except ImportError:
        return None
