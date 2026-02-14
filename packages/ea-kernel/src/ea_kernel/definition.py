"""Kernel metamodel element definitions.

Data loaded from specs/kernel_schema.toml — this module is a thin wrapper
preserving the original import interface.
"""

from ea_kernel.schema_loader import load_kernel_schema

(KERNEL_VERSION, KERNEL_SCHEMA, ATTRIBUTES,
 L1_ENTITIES, L2_RELATIONS, L3_RELATIONS, L4_ENTITIES) = load_kernel_schema()


KERNEL_METADATA: dict[str, int | str] = {
    "version": KERNEL_VERSION,
    "entities": len(KERNEL_SCHEMA.entities),
    "relations": len(KERNEL_SCHEMA.relations),
    "attributes": len(KERNEL_SCHEMA.attributes),
}


def get_kernel_metadata() -> dict[str, int | str]:
    """Get full kernel metadata including validity_rules count.

    This imports spec.py lazily to avoid circular dependencies.
    """
    from ea_kernel.spec import KERNEL_SPEC
    meta = dict(KERNEL_METADATA)
    meta["validity_rules"] = len(KERNEL_SPEC.validity_rules)
    return meta
