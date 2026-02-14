"""Kernel metamodel validity rules — the formal specification.

Rules loaded from specs/kernel_rules.toml.
Priority bands:
  1       = deny-by-default fallback (one per relation)
  40-50   = broad metatype-level allows
  60      = general structural patterns
  70      = specific behavioral patterns
  80-90   = explicit prohibitions (override allows)
"""

from ea_kernel.definition import KERNEL_SCHEMA
from ea_kernel.spec_loader import load_kernel_rules
from ea_kernel.types import KernelSchema

KERNEL_VALIDITY_RULES, KERNEL_LAYER_CONSTRAINTS = load_kernel_rules()


def build_validated_schema() -> KernelSchema:
    """Build KERNEL_SCHEMA with validity rules and layer constraints attached."""
    return KernelSchema(
        attributes=KERNEL_SCHEMA.attributes,
        entities=KERNEL_SCHEMA.entities,
        relations=KERNEL_SCHEMA.relations,
        validity_rules=KERNEL_VALIDITY_RULES,
        layer_constraints=KERNEL_LAYER_CONSTRAINTS,
    )


KERNEL_SPEC = build_validated_schema()
