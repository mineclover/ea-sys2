"""M0 instance validation against kernel schema (M2).

Phase 3: Validates concrete model instances against the kernel metamodel,
checking type conformance and relation validity.
"""

from __future__ import annotations

from ea_kernel.types import (
    ConformanceResult,
    InstanceElement,
    InstanceRelation,
    KernelSchema,
)


class InstanceValidator:
    """Validates M0 instances against the kernel schema (M2)."""

    __slots__ = ("_schema",)

    def __init__(self, schema: KernelSchema) -> None:
        self._schema = schema

    def validate_element(self, element: InstanceElement) -> ConformanceResult:
        """Check if element's entity_type is valid."""
        entity = self._schema.get_entity(element.entity_type)
        if entity is None:
            return ConformanceResult(
                valid=False,
                element_id=element.id,
                check_type="type_validity",
                details=f"Unknown entity type: '{element.entity_type}'",
            )

        if entity.is_abstract:
            return ConformanceResult(
                valid=False,
                element_id=element.id,
                check_type="type_validity",
                details=f"Cannot instantiate abstract type: '{element.entity_type}'",
            )

        return ConformanceResult(
            valid=True,
            element_id=element.id,
            check_type="type_validity",
            details=f"Valid instance of '{element.entity_type}'",
        )

    def validate_relation(
        self,
        relation: InstanceRelation,
        elements: dict[str, InstanceElement],
    ) -> ConformanceResult:
        """Check if relation's source/target types are valid per kernel rules."""
        source = elements.get(relation.source_id)
        if source is None:
            return ConformanceResult(
                valid=False,
                element_id=relation.id,
                check_type="relationship",
                details=f"Source element not found: '{relation.source_id}'",
            )

        target = elements.get(relation.target_id)
        if target is None:
            return ConformanceResult(
                valid=False,
                element_id=relation.id,
                check_type="relationship",
                details=f"Target element not found: '{relation.target_id}'",
            )

        # Validate against kernel rules
        result = self._schema.validate_relationship(
            source.entity_type, target.entity_type, relation.relation_type,
        )

        return ConformanceResult(
            valid=result.valid,
            element_id=relation.id,
            check_type="relationship",
            details=(
                result.notes or ""
            ),
            rule_id=result.rule_id,
        )

    def validate_model(
        self,
        elements: tuple[InstanceElement, ...],
        relations: tuple[InstanceRelation, ...],
    ) -> tuple[ConformanceResult, ...]:
        """Full model validation — all elements and relations."""
        results: list[ConformanceResult] = []

        # Build element lookup
        elem_map: dict[str, InstanceElement] = {e.id: e for e in elements}

        # Validate all elements
        for element in elements:
            results.append(self.validate_element(element))

        # Validate all relations
        for relation in relations:
            results.append(self.validate_relation(relation, elem_map))

        return tuple(results)
