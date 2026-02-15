"""CLI entry point for ea-kernel DX tools.

Usage:
    python -m ea_kernel audit [profile_name]  — audit profiles against kernel
    python -m ea_kernel verify                — run rule verifier (kernel self-consistency)
    python -m ea_kernel info [profile_name]   — show profile/kernel info
    python -m ea_kernel show entities         — list kernel entities by layer
    python -m ea_kernel show relations        — list kernel relations by layer
    python -m ea_kernel show rules [--group] [--relation]  — list/filter rules
    python -m ea_kernel show profile <name>   — describe a profile
    python -m ea_kernel show rule <id>        — describe a single rule
    python -m ea_kernel show reachable <profile> <element>  — reachable elements
    python -m ea_kernel show paths <profile> <src> <tgt>    — find paths
    python -m ea_kernel show impact <profile> <element>     — impact analysis
    python -m ea_kernel judge <src> <tgt> <rel>  — evidence-based judgment
    python -m ea_kernel model register <toml> [--db-path ...]  — register model
    python -m ea_kernel model validate <name> <version>        — validate model
    python -m ea_kernel model activate <name> <version>        — activate model
    python -m ea_kernel model show <name>                      — show model state
    python -m ea_kernel mcp                   — run MCP server (stdio transport)
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


def _cmd_audit(args: argparse.Namespace) -> int:
    """Audit built-in profiles against the kernel."""
    from ea_kernel.profile_auditor import ProfileAuditor
    from ea_kernel.profile_registry import ProfileRegistry
    from ea_kernel.spec import KERNEL_SPEC

    auditor = ProfileAuditor(KERNEL_SPEC)

    if args.profile:
        registry = ProfileRegistry()
        registry.bootstrap()
        profile = registry.get(args.profile)
        if profile is None:
            print(f"Profile not found: {args.profile}", file=sys.stderr)
            return 1
        result = auditor.audit_profile(profile)
        _print_audit_result(result)
        return 0 if result.passed else 1
    else:
        registry = ProfileRegistry()
        registry.bootstrap()
        report = auditor.audit_registry(registry)
        for result in report.results:
            _print_audit_result(result)
        print(f"\n{'='*60}")
        print(f"Total: {report.total_profiles} profiles, "
              f"{report.passed_profiles} passed")
        return 0 if report.passed_profiles == report.total_profiles else 1


def _print_audit_result(result: Any) -> None:
    """Print a single AuditResult."""
    status = "PASS" if result.passed else "FAIL"
    print(f"\n[{status}] {result.profile_name}")
    print(f"  Coverage: {result.quality.coverage:.0%}")
    if result.findings:
        for f in result.findings:
            prefix = {"error": "  !", "warning": "  ~", "info": "  -"}
            print(f"{prefix.get(f.severity.value, '  ?')} [{f.category}] {f.message}")
    else:
        print("  No issues found.")


def _cmd_verify(args: argparse.Namespace) -> int:
    """Run the rule verifier for kernel self-consistency."""
    from ea_kernel.rule_corpus import RuleCorpus
    from ea_kernel.rule_verifier import RuleVerifier
    from ea_kernel.spec import KERNEL_SPEC
    from ea_kernel.spec_loader import load_kernel_rules_with_metadata

    _, _, metadata_map = load_kernel_rules_with_metadata()
    corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC, metadata_map)
    verifier = RuleVerifier(KERNEL_SPEC, corpus)
    report = verifier.verify_all()

    for gr in report.group_results:
        status = "PASS" if gr.pass_rate == 1.0 else "FAIL"
        print(f"[{status}] {gr.group.value}: "
              f"{gr.passed_rules}/{gr.total_rules} rules passed")
        if gr.pass_rate < 1.0:
            for entry in gr.entries:
                if not entry.passed:
                    print(f"  ! {entry.rule_id}: expected {entry.expected_valid}, "
                          f"got {entry.actual_valid}")

    print(f"\nOverall: {report.total_passed}/{report.total_rules} rules, "
          f"{report.passed_groups}/{report.total_groups} groups passed "
          f"({report.overall_pass_rate:.0%})")
    return 0 if report.overall_pass_rate == 1.0 else 1


def _cmd_info(args: argparse.Namespace) -> int:
    """Show profile or kernel info."""
    from ea_kernel.definition import KERNEL_VERSION
    from ea_kernel.profile_registry import ProfileRegistry
    from ea_kernel.spec import KERNEL_SPEC

    if args.profile:
        registry = ProfileRegistry()
        registry.bootstrap()
        profile = registry.get(args.profile)
        if profile is None:
            print(f"Profile not found: {args.profile}", file=sys.stderr)
            return 1
        print(f"Profile: {profile.name} v{profile.version}")
        print(f"  Kernel version: {profile.kernel_version}")
        print(f"  Elements: {len(profile.elements)}")
        print(f"  Relations: {len(profile.relations)}")
        print(f"  Rules: {len(profile.validity_rules)}")
        if profile.metadata:
            print(f"  Standard: {profile.metadata.standard}")
            print(f"  Organization: {profile.metadata.organization}")
        layers = profile.domain_layers()
        print(f"  Layers: {', '.join(layers)}")
    else:
        print(f"Kernel v{KERNEL_VERSION}")
        print(f"  Entities: {len(KERNEL_SPEC.entities)}")
        print(f"  Relations: {len(KERNEL_SPEC.relations)}")
        print(f"  Validity rules: {len(KERNEL_SPEC.validity_rules)}")
        print(f"  Layer constraints: {len(KERNEL_SPEC.layer_constraints)}")

        registry = ProfileRegistry()
        registry.bootstrap()
        print(f"\nBuilt-in profiles ({len(registry.list_names())}):")
        for name in registry.list_names():
            p = registry.get(name)
            if p:
                print(f"  {name} v{p.version} — "
                      f"{len(p.elements)} elements, "
                      f"{len(p.relations)} relations, "
                      f"{len(p.validity_rules)} rules")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# Show commands — onboarding use cases
# ═══════════════════════════════════════════════════════════════════════════════


def _cmd_show(args: argparse.Namespace) -> int:
    """Dispatch show subcommands."""
    target = args.show_target
    if target == "entities":
        return _show_entities()
    elif target == "relations":
        return _show_relations()
    elif target == "rules":
        return _show_rules(args)
    elif target == "profile":
        return _show_profile(args)
    elif target == "rule":
        return _show_rule(args)
    elif target == "reachable":
        return _show_reachable(args)
    elif target == "paths":
        return _show_paths(args)
    elif target == "impact":
        return _show_impact(args)
    else:
        print(f"Unknown show target: {target}", file=sys.stderr)
        return 1


def _show_entities() -> int:
    """show entities — tree view of kernel entities by layer."""
    from ea_kernel.kernel_service import list_entities

    data = list_entities()
    print(f"Kernel Entities ({data['total']})")

    for layer in data["layers"]:
        if not layer["entities"]:
            continue
        print(f"\n{layer['name']} ({layer['count']}):")

        # Build hierarchy tree
        entities = layer["entities"]
        _print_entity_tree(entities, parent=None, indent=2)

    return 0


def _print_entity_tree(
    entities: list[dict[str, Any]], parent: str | None, indent: int,
) -> None:
    """Recursively print entity hierarchy as indented tree."""
    children = [e for e in entities if e["parent"] == parent]
    # Also include entities whose parent is outside this layer
    if parent is None:
        entity_names = {e["name"] for e in entities}
        children = [
            e for e in entities
            if e["parent"] is None or e["parent"] not in entity_names
        ]

    for e in children:
        prefix = " " * indent
        abstract_mark = " (abstract)" if e["is_abstract"] else ""
        parent_note = ""
        if parent is None and e["parent"] is not None:
            parent_note = f" -> {e['parent']}"
        print(f"{prefix}{e['name']}{abstract_mark}{parent_note}")
        # Recurse into children within this layer
        _print_entity_tree(entities, e["name"], indent + 2)


def _show_relations() -> int:
    """show relations — list kernel relations with roles."""
    from ea_kernel.kernel_service import list_relations

    data = list_relations()
    print(f"Kernel Relations ({data['total']})")

    for layer in data["layers"]:
        if not layer["relations"]:
            continue
        print(f"\n{layer['name']} ({layer['count']}):")
        for r in layer["relations"]:
            roles = r["roles"]
            if len(roles) >= 2:
                role_str = f"{roles[0]['name']}({roles[0]['player']}) -> {roles[1]['name']}({roles[1]['player']})"
            elif len(roles) == 1:
                role_str = f"{roles[0]['name']}({roles[0]['player']})"
            else:
                role_str = ""
            print(f"  {r['name']:<20s}{role_str}")

    return 0


def _show_rules(args: argparse.Namespace) -> int:
    """show rules — list/filter rules."""
    from ea_kernel.kernel_service import list_rules

    group = getattr(args, "group", None)
    relation = getattr(args, "relation", None)
    data = list_rules(group=group, relation=relation)

    if "error" in data:
        print(f"Error: {data['error']}", file=sys.stderr)
        if "valid_groups" in data:
            print(f"Valid groups: {', '.join(data['valid_groups'])}", file=sys.stderr)
        return 1

    if "groups" in data:
        print(f"Rules ({data['total']})")
        print()
        for g in data["groups"]:
            print(f"  {g['name']:<24s}{g['count']:>3d} rules")
        return 0

    # Filtered view
    label = data.get("group") or data.get("relation", "")
    print(f"Rules: {label} ({data['total']})")
    for r in data["rules"]:
        valid_str = "ALLOW" if r["valid"] else "DENY "
        print(f"  {r['id']:<30s}{valid_str}  {r['source']:<16s}-> {r['target']:<16s}p={r['priority']}")

    return 0


def _show_profile(args: argparse.Namespace) -> int:
    """show profile <name> — describe a profile."""
    from ea_kernel.kernel_service import describe_profile

    name = args.profile_name
    data = describe_profile(name)
    if data is None:
        print(f"Profile not found: {name}", file=sys.stderr)
        return 1

    org = f" ({data['organization']})" if data["organization"] else ""
    print(f"Profile: {data['name']} v{data['version']}{org}")
    if data["standard"]:
        print(f"  Standard: {data['standard']}")
    print(f"  Elements: {data['element_count']} | "
          f"Relations: {data['relation_count']} | "
          f"Rules: {data['rule_count']}")

    print("\nElements by Layer:")
    for layer_data in data["elements_by_layer"]:
        elems = layer_data["elements"]
        elem_strs = [f"{e['name']} -> {e['kernel_type']}" for e in elems[:5]]
        suffix = " ..." if len(elems) > 5 else ""
        print(f"  {layer_data['layer']} ({layer_data['count']}):")
        for s in elem_strs:
            print(f"    {s}")
        if suffix:
            print(f"    {suffix}")

    print("\nRelations:")
    for r in data["relations"]:
        print(f"  {r['name']} -> {r['kernel_relation']}")

    summary = data["rule_summary"]
    print(f"\nRules: {summary['allow']} allow, {summary['deny']} deny")

    return 0


def _show_rule(args: argparse.Namespace) -> int:
    """show rule <id> — describe a single rule."""
    from ea_kernel.kernel_service import describe_rule

    rule_id = args.rule_id
    data = describe_rule(rule_id)
    if data is None:
        print(f"Rule not found: {rule_id}", file=sys.stderr)
        return 1

    valid_str = "ALLOW" if data["valid"] else "DENY"
    print(f"Rule: {data['id']}")
    print(f"  Source:   {data['source']}")
    print(f"  Target:   {data['target']}")
    print(f"  Relation: {data['relation']}")
    print(f"  Valid:    {valid_str}")
    print(f"  Priority: {data['priority']}")

    if data["conditions"]:
        print("\nConditions:")
        for c in data["conditions"]:
            params = ", ".join(f"{k}={v}" for k, v in c["parameters"].items())
            print(f"  {c['type']}{' (' + params + ')' if params else ''}")

    if data["notes"]:
        print(f"\nNotes: {data['notes']}")

    meta = data["metadata"]
    print("\nMetadata:")
    print(f"  Group:      {meta['group']}")
    print(f"  Category:   {meta['category']}")
    print(f"  Confidence: {meta['confidence']}")
    if meta["source"]:
        print(f"  Source:     {meta['source']}")
    if meta["rationale"]:
        print(f"  Rationale:  {meta['rationale']}")
    if meta["tags"]:
        print(f"  Tags:       {', '.join(meta['tags'])}")
    if meta["established_version"]:
        print(f"  Since:      {meta['established_version']}")

    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# Profile graph commands
# ═══════════════════════════════════════════════════════════════════════════════


def _show_reachable(args: argparse.Namespace) -> int:
    """show reachable <profile> <element> — reachable elements."""
    from ea_kernel.kernel_service import profile_reachable

    data = profile_reachable(
        args.profile_name,
        args.element,
        max_depth=args.depth,
        relation=getattr(args, "relation", None),
    )
    if "error" in data:
        print(f"Error: {data['error']}", file=sys.stderr)
        return 1

    print(f"Reachable from {data['source']} in {data['profile']} "
          f"(depth={data['max_depth']}, count={data['count']})")
    for name in data["reachable"]:
        print(f"  {name}")
    return 0


def _show_paths(args: argparse.Namespace) -> int:
    """show paths <profile> <source> <target> — find paths."""
    from ea_kernel.kernel_service import profile_paths

    data = profile_paths(
        args.profile_name,
        args.source,
        args.target,
        max_depth=args.depth,
        relation=getattr(args, "relation", None),
    )
    if "error" in data:
        print(f"Error: {data['error']}", file=sys.stderr)
        return 1

    print(f"Paths: {data['source']} -> {data['target']} in {data['profile']} "
          f"(count={data['count']})")
    for i, p in enumerate(data["paths"], 1):
        edges = p["edges"]
        chain = " -> ".join(e["source"] for e in edges)
        chain += f" -> {edges[-1]['target']}" if edges else ""
        relations = [e["relation"] for e in edges]
        print(f"\n  [{i}] length={p['length']}")
        print(f"      {chain}")
        print(f"      via: {' > '.join(relations)}")
    return 0


def _show_impact(args: argparse.Namespace) -> int:
    """show impact <profile> <element> — impact analysis."""
    from ea_kernel.kernel_service import profile_impact

    data = profile_impact(
        args.profile_name,
        args.element,
        direction=args.direction,
        max_depth=args.depth,
    )
    if "error" in data:
        print(f"Error: {data['error']}", file=sys.stderr)
        return 1

    print(f"Impact of {data['element']} in {data['profile']} "
          f"(direction={data['direction']}, affected={data['affected_count']})")
    for name, paths in data["impact"].items():
        print(f"\n  {name} ({len(paths)} path(s)):")
        for p in paths[:3]:
            edges = p["edges"]
            chain = " -> ".join(e["source"] for e in edges)
            chain += f" -> {edges[-1]['target']}" if edges else ""
            print(f"    {chain}")
        if len(paths) > 3:
            print(f"    ... and {len(paths) - 3} more")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# Judge command
# ═══════════════════════════════════════════════════════════════════════════════


def _cmd_judge(args: argparse.Namespace) -> int:
    """judge <source> <target> <relation> — evidence-based judgment."""
    from ea_kernel.kernel_service import judge

    data = judge(args.source, args.target, args.relation)

    if "error" in data:
        print(f"Error: {data['error']}", file=sys.stderr)
        return 1

    verdict_str = "ALLOW" if data["verdict"] else "DENY"
    print(f"Judge: {args.source} -> {args.target} via {args.relation}")
    print()
    print(f"Verdict: {verdict_str} (confidence: {data['confidence']})")

    if data["evidence"]:
        print("\nEvidence:")
        for ev in data["evidence"]:
            valid_str = "ALLOW" if ev["valid"] else "DENY "
            marker = "* " if ev["winner"] else "  "
            winner_tag = "  [winner]" if ev["winner"] else ""
            print(f"  {marker}{ev['rule_id']:<30s}{valid_str}  "
                  f"{ev['source']:<16s}-> {ev['target']:<16s}"
                  f"p={ev['priority']}{winner_tag}")

    if data["conflicts"]:
        print("\nConflicts:")
        for c in data["conflicts"]:
            print(f"  ! {c}")
    else:
        print("\nNo conflicts.")

    return 0


def _load_registration_service(db_path: str) -> Any:
    from pathlib import Path

    from ea_kernel.model_registration import KernelModelRegistrationService
    from ea_kernel.spec import KERNEL_SPEC

    return KernelModelRegistrationService(Path(db_path), KERNEL_SPEC)


def _profile_with_name(profile: Any, model_name: str) -> Any:
    from ea_kernel.profile_types import KernelProfile

    if profile.name == model_name:
        return profile
    return KernelProfile(
        name=model_name,
        version=profile.version,
        kernel_version=profile.kernel_version,
        elements=profile.elements,
        relations=profile.relations,
        validity_rules=profile.validity_rules,
        metadata=profile.metadata,
    )


def _parse_context_args(raw_values: list[str] | None) -> dict[str, str]:
    context: dict[str, str] = {}
    if not raw_values:
        return context

    for item in raw_values:
        if "=" not in item:
            raise ValueError(f"Invalid context '{item}'. Use key=value format.")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid context '{item}'. Key cannot be empty.")
        context[key] = value
    return context


def _cmd_model_register(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ea_kernel.model_registration import ModelRegistrationError
    from ea_kernel.profile_loader import ProfileLoadError, load_profile
    from ea_kernel.spec import KERNEL_SPEC

    try:
        context = _parse_context_args(args.context)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    profile_path = Path(args.profile_toml)
    try:
        profile = load_profile(profile_path, KERNEL_SPEC)
    except (ProfileLoadError, FileNotFoundError) as exc:
        print(f"Failed to load profile: {exc}", file=sys.stderr)
        return 1

    if args.model_name:
        profile = _profile_with_name(profile, args.model_name)

    context = {
        "source": "cli:model-register",
        "profile_toml": str(profile_path),
        **context,
    }

    service = _load_registration_service(args.db_path)

    try:
        result = service.register(
            profile,
            owner=args.owner,
            created_by=args.created_by,
            context=context,
        )
        print(
            f"[ok] registered model={result.model_name} "
            f"version={result.version} run={result.validation_run_id}"
        )
    except ModelRegistrationError as exc:
        text = str(exc)
        if args.on_exists == "validate" and "already exists" in text:
            rerun = service.validate_registered(
                profile.name,
                profile.version,
                context={**context, "mode": "reregister"},
            )
            status = "pass" if rerun.passed else "fail"
            print(
                f"[ok] existing model revalidated model={profile.name} "
                f"version={profile.version} run={rerun.run_id} status={status}"
            )
            if not rerun.passed:
                return 1
        else:
            print(f"Registration failed: {exc}", file=sys.stderr)
            return 1

    if args.activate:
        try:
            model = service.activate(profile.name, profile.version, actor=args.created_by)
        except ModelRegistrationError as exc:
            print(f"Activation failed: {exc}", file=sys.stderr)
            return 1
        print(
            f"[ok] activated model={model.model_name} "
            f"version={profile.version} active_version_id={model.active_version_id}"
        )

    return 0


def _cmd_model_validate(args: argparse.Namespace) -> int:
    from ea_kernel.model_registration import ModelRegistrationError

    try:
        context = _parse_context_args(args.context)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    service = _load_registration_service(args.db_path)
    try:
        run = service.validate_registered(
            args.model_name,
            args.version,
            context={"source": "cli:model-validate", **context},
        )
    except ModelRegistrationError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1

    status = "PASS" if run.passed else "FAIL"
    print(
        f"[{status}] model={args.model_name} "
        f"version={args.version} run={run.run_id} errors={len(run.errors)}"
    )
    return 0 if run.passed else 1


def _cmd_model_activate(args: argparse.Namespace) -> int:
    from ea_kernel.model_registration import ModelRegistrationError

    service = _load_registration_service(args.db_path)
    try:
        model = service.activate(args.model_name, args.version, actor=args.actor)
    except ModelRegistrationError as exc:
        print(f"Activation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"[ok] model={model.model_name} status={model.status} "
        f"active_version_id={model.active_version_id}"
    )
    return 0


def _cmd_model_show(args: argparse.Namespace) -> int:
    service = _load_registration_service(args.db_path)
    model = service.get_model(args.model_name)
    if model is None:
        print(f"Model not found: {args.model_name}", file=sys.stderr)
        return 1

    versions = service.list_versions(args.model_name)
    runs = service.list_validation_runs(model_name=args.model_name, limit=args.limit_runs)

    print(f"Model: {model.model_name}")
    print(f"  Status: {model.status}")
    print(f"  Owner: {model.owner}")
    print(f"  Active version id: {model.active_version_id or '-'}")
    print(f"  Versions: {len(versions)}")
    for entry in versions:
        mark = " *" if entry.version_id == model.active_version_id else ""
        print(f"    - {entry.version} ({entry.version_id}){mark}")

    print(f"  Validation runs (latest {len(runs)}):")
    for run in runs:
        status = "PASS" if run.passed else "FAIL"
        print(f"    - {run.run_id} [{status}] version_id={run.version_id}")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# Main parser
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ea_kernel",
        description="ea-kernel DX tools",
    )
    sub = parser.add_subparsers(dest="command")

    # Existing commands
    audit_p = sub.add_parser("audit", help="Audit profiles against kernel")
    audit_p.add_argument("profile", nargs="?", help="Profile name (omit for all)")

    sub.add_parser("verify", help="Run rule verifier (kernel self-consistency)")

    info_p = sub.add_parser("info", help="Show profile/kernel info")
    info_p.add_argument("profile", nargs="?", help="Profile name (omit for kernel)")

    # Show command with subtargets
    show_p = sub.add_parser("show", help="Explore kernel entities, relations, rules, profiles")
    show_sub = show_p.add_subparsers(dest="show_target")

    show_sub.add_parser("entities", help="List kernel entities by layer")
    show_sub.add_parser("relations", help="List kernel relations by layer")

    rules_p = show_sub.add_parser("rules", help="List/filter rules")
    rules_p.add_argument("--group", help="Filter by rule group")
    rules_p.add_argument("--relation", help="Filter by relation name")

    profile_p = show_sub.add_parser("profile", help="Describe a profile")
    profile_p.add_argument("profile_name", help="Profile name")

    rule_p = show_sub.add_parser("rule", help="Describe a single rule")
    rule_p.add_argument("rule_id", help="Rule ID")

    reachable_p = show_sub.add_parser("reachable", help="Reachable elements from a profile element")
    reachable_p.add_argument("profile_name", help="Profile name")
    reachable_p.add_argument("element", help="Source element name")
    reachable_p.add_argument("--depth", type=int, default=3, help="Max traversal depth")
    reachable_p.add_argument("--relation", help="Filter by relation name")

    paths_p = show_sub.add_parser("paths", help="Find paths between profile elements")
    paths_p.add_argument("profile_name", help="Profile name")
    paths_p.add_argument("source", help="Source element name")
    paths_p.add_argument("target", help="Target element name")
    paths_p.add_argument("--depth", type=int, default=5, help="Max path depth")
    paths_p.add_argument("--relation", help="Filter by relation name")

    impact_p = show_sub.add_parser("impact", help="Impact analysis for a profile element")
    impact_p.add_argument("profile_name", help="Profile name")
    impact_p.add_argument("element", help="Element to analyze")
    impact_p.add_argument("--direction", choices=("outgoing", "incoming", "both"), default="both", help="Analysis direction")
    impact_p.add_argument("--depth", type=int, default=3, help="Max traversal depth")

    # MCP server
    sub.add_parser("mcp", help="Run MCP server (stdio transport)")

    # Judge command
    judge_p = sub.add_parser("judge", help="Evidence-based judgment for a triple")
    judge_p.add_argument("source", help="Source entity name")
    judge_p.add_argument("target", help="Target entity name")
    judge_p.add_argument("relation", help="Relation name")

    # Model registration commands
    model_p = sub.add_parser("model", help="Model registration/validation workflow")
    model_sub = model_p.add_subparsers(dest="model_target")

    model_register_p = model_sub.add_parser("register", help="Register a profile TOML as model")
    model_register_p.add_argument("profile_toml", help="Path to profile TOML")
    model_register_p.add_argument("--db-path", default="profiles.db", help="Profiles DB path")
    model_register_p.add_argument("--owner", default="kernel-team", help="Model owner")
    model_register_p.add_argument("--created-by", default="cli", help="Actor for registration")
    model_register_p.add_argument("--model-name", help="Override model name")
    model_register_p.add_argument(
        "--on-exists",
        choices=("validate", "error"),
        default="validate",
        help="Action when model version already exists",
    )
    model_register_p.add_argument(
        "--context",
        action="append",
        help="Context metadata in key=value format (repeatable)",
    )
    model_register_p.add_argument(
        "--activate",
        action="store_true",
        help="Activate the registered version",
    )

    model_validate_p = model_sub.add_parser("validate", help="Validate an already registered model")
    model_validate_p.add_argument("model_name", help="Registered model name")
    model_validate_p.add_argument("version", help="Model version")
    model_validate_p.add_argument("--db-path", default="profiles.db", help="Profiles DB path")
    model_validate_p.add_argument(
        "--context",
        action="append",
        help="Validation context in key=value format (repeatable)",
    )

    model_activate_p = model_sub.add_parser("activate", help="Activate a validated model version")
    model_activate_p.add_argument("model_name", help="Registered model name")
    model_activate_p.add_argument("version", help="Model version")
    model_activate_p.add_argument("--db-path", default="profiles.db", help="Profiles DB path")
    model_activate_p.add_argument("--actor", default="cli", help="Activation actor")

    model_show_p = model_sub.add_parser("show", help="Show model state and versions")
    model_show_p.add_argument("model_name", help="Registered model name")
    model_show_p.add_argument("--db-path", default="profiles.db", help="Profiles DB path")
    model_show_p.add_argument("--limit-runs", type=int, default=5, help="Recent validation run count")

    args = parser.parse_args()

    if args.command == "audit":
        return _cmd_audit(args)
    elif args.command == "verify":
        return _cmd_verify(args)
    elif args.command == "info":
        return _cmd_info(args)
    elif args.command == "show":
        if args.show_target is None:
            show_p.print_help()
            return 0
        return _cmd_show(args)
    elif args.command == "judge":
        return _cmd_judge(args)
    elif args.command == "mcp":
        from ea_kernel.mcp_server import run_stdio
        run_stdio()
        return 0
    elif args.command == "model":
        if args.model_target is None:
            model_p.print_help()
            return 0
        if args.model_target == "register":
            return _cmd_model_register(args)
        elif args.model_target == "validate":
            return _cmd_model_validate(args)
        elif args.model_target == "activate":
            return _cmd_model_activate(args)
        elif args.model_target == "show":
            return _cmd_model_show(args)
        print(f"Unknown model target: {args.model_target}", file=sys.stderr)
        return 1
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
