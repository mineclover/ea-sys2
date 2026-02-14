#!/usr/bin/env python3
"""
FruitRetail Profile Example

Demonstrates loading and validating a fruit retail business model
using ea-kernel.

Usage:
    python examples/fruit_retail_example.py
"""

from __future__ import annotations

import json
from pathlib import Path

from ea_kernel.profile_loader import load_profile
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.rule_corpus import RuleCorpus
from ea_kernel.spec_loader import load_kernel_rules_with_metadata
from ea_kernel.profile_auditor import ProfileAuditor


def main() -> None:
    profile_path = Path(__file__).parent / "fruit_retail_profile.toml"

    print("=" * 80)
    print("FruitRetail Profile Example")
    print("=" * 80)
    print()

    # ── Load Profile ──
    print("1. Loading profile from TOML...")
    profile = load_profile(profile_path)
    print(f"   ✓ Loaded: {profile.name} v{profile.version}")
    print(f"     Elements: {len(profile.elements)}")
    print(f"     Relations: {len(profile.relations)}")
    print(f"     Rules: {len(profile.validity_rules)}")
    print()

    # ── Audit Profile ──
    print("2. Auditing profile against kernel...")
    auditor = ProfileAuditor(KERNEL_SPEC)
    result = auditor.audit_profile(profile)
    status = "✓ PASS" if result.passed else "✗ FAIL"
    print(f"   {status}")
    print(f"     Coverage: {result.quality.coverage:.0%}")
    if result.findings:
        for f in result.findings[:5]:
            print(f"     - [{f.category}] {f.message}")
    print()

    # ── Load Kernel Rules ──
    print("3. Loading kernel validity rules...")
    _, _, metadata_map = load_kernel_rules_with_metadata()
    corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC, metadata_map)
    print(f"   ✓ Loaded {len(corpus.entries)} kernel rules")
    print(f"   Note: Profile validation uses profile's own rules (17), not kernel rules")
    print()

    # ── Validate Defined Relations ──
    print("4. Validating that defined relations exist in profile:")
    print()

    # Check that relations defined in TOML are present
    rel_names = {r.name for r in profile.relations}
    expected_relations = [
        ("supplies", "Store-Supplier relationship"),
        ("stocks", "Store-Inventory relationship"),
        ("contains", "Inventory contains Products"),
        ("sells_to", "Store-Customer relationship"),
        ("supply_flow", "Product flow from Supplier to Store"),
        ("display_flow", "Product display from Inventory to Store"),
        ("receive_then_check", "Process: Receive then Check"),
        ("check_then_display", "Process: Check then Display"),
        ("display_then_sale", "Process: Display then Sale"),
    ]

    for rel_name, description in expected_relations:
        exists = rel_name in rel_names
        marker = "✓" if exists else "✗"
        print(f"   {marker} {rel_name:<25s} — {description}")

    print()

    # ── Explore Profile ──
    print("5. Profile structure:")
    print()

    # Elements by layer
    print("   Elements by layer:")
    for layer in profile.domain_layers():
        elems = profile.elements_in_layer(layer)
        elem_names = [e.name for e in elems]
        print(f"     {layer}: {', '.join(elem_names[:5])}")
        if len(elem_names) > 5:
            print(f"            (... and {len(elem_names) - 5} more)")
    print()

    # Relations by type
    print("   Relations by kernel_relation:")
    rel_types: dict[str, list[str]] = {}
    for r in profile.relations:
        rel_types.setdefault(r.kernel_relation, []).append(r.name)
    for rel_type, names in sorted(rel_types.items()):
        print(f"     {rel_type}: {', '.join(names[:4])}")
        if len(names) > 4:
            print(f"              (... and {len(names) - 4} more)")
    print()

    # Process flow
    print("   Process flow (succession chain):")
    succession_rels = [r for r in profile.relations if r.kernel_relation == "succession"]
    for r in succession_rels[:8]:
        print(f"     {r.name}")
    if len(succession_rels) > 8:
        print(f"     (... and {len(succession_rels) - 8} more)")
    print()

    # ── Rule Statistics ──
    print("6. Rule statistics:")
    print()
    allow_count = sum(1 for r in profile.validity_rules if r.valid)
    deny_count = sum(1 for r in profile.validity_rules if not r.valid)
    print(f"   Total rules: {len(profile.validity_rules)}")
    print(f"   Allow rules: {allow_count}")
    print(f"   Deny rules: {deny_count}")
    print()

    # Rules by type
    print("   Rules by relationship type:")
    rules_count: dict[str, int] = {}
    for r in profile.validity_rules:
        rules_count[r.relationship_name] = rules_count.get(r.relationship_name, 0) + 1
    for rel_type in sorted(rules_count.keys()):
        print(f"     {rel_type}: {rules_count[rel_type]} rules")
    print()

    print("=" * 80)
    print("✓ Example complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
