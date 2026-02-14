import json
import logging
from pathlib import Path
from typing import Any, cast

from ea_kernel.governance import GovernanceSystem
from ea_kernel.governance_types import (
    RuleAsset,
    RuleLifecycle,
    RuleLifecycleState,
    RuleProvenance,
)
from ea_kernel.schema_loader import load_kernel_schema_from_package
from ea_kernel.types import (
    KernelConditionType,
    KernelRuleCondition,
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("seed_demo")

def get_data_dir() -> Path:
    import os
    env_path = os.getenv("EA_KERNEL_DATA_DIR", "./governance_data")
    path = Path(env_path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path

def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))

def create_rule_entry(rule_data: dict[str, Any], domain: str) -> RuleCorpusEntry:
    # 1. Rule Object
    try:
        rel = rule_data["relationship_name"]
        group = RuleGroup.from_relation(rel)
    except ValueError:
        # Fallback if from_relation fails or is strict, though it has fallback to MEMBERSHIP
        group = RuleGroup.MEMBERSHIP

    # Simplified conditions (none in demo data for now)
    conditions = tuple(
        KernelRuleCondition(
            condition_type=KernelConditionType(c["type"]),
            parameters=tuple(tuple(p) for p in c["params"]),
        )
        for c in rule_data.get("conditions", [])
    )

    rule = KernelValidityRule(
        id=rule_data["id"],
        source_pattern=rule_data["source_pattern"],
        target_pattern=rule_data["target_pattern"],
        relationship_name=rule_data["relationship_name"],
        valid=rule_data["valid"],
        priority=rule_data.get("priority", 0),
        conditions=conditions,
        notes=rule_data.get("notes", ""),
    )

    # 2. Metadata
    meta = RuleMetadata(
        domain=domain,
        tags=(domain, "demo", rule_data["relationship_name"]),
        category=RuleCategory.DOMAIN,  # Demo rules are Domain specific
        confidence=RuleConfidence.COMMON,
        source="demo_seed",
        established_version="1.0.0",
        rationale=rule_data.get("notes", "Demo rule"),
        group=group,
    )

    return RuleCorpusEntry(rule=rule, metadata=meta)

def seed_system() -> None:
    logger.info("Starting demo data seeding...")

    # 1. Setup System
    data_dir = get_data_dir()
    schema = load_kernel_schema_from_package()
    # Assuming 'default' tenant path as used in server.py
    system = GovernanceSystem(data_dir / "default", schema)

    # 2. Load Data
    seed_file = Path(__file__).parent.parent / "seeds/demo_data.json"
    if not seed_file.exists():
        logger.error(f"Seed file not found: {seed_file}")
        return

    data = load_json(seed_file)
    profiles = data.get("profiles", [])

    total_added = 0

    for profile in profiles:
        domain = profile["name"]
        rules = profile.get("rules", [])

        logger.info(f"Processing profile: {domain} ({len(rules)} rules)")

        for rule_data in rules:
            rule_id = rule_data["id"]

            # Check if exists
            existing = system.rule_store.get(rule_id)
            if existing:
                logger.info(f"  Skipping existing rule: {rule_id}")
                continue

            # Create Entry
            entry = create_rule_entry(rule_data, domain)

            # Create Asset (Draft)
            provenance = RuleProvenance(
                author="system:seeder",
                source_type="manual",
                source_reference="demo_data.json",
                version=1,
            )

            asset = RuleAsset(
                entry=entry,
                provenance=provenance,
                lifecycle=RuleLifecycle(current_state=RuleLifecycleState.DRAFT),
            )

            # Submit
            try:
                system.submit_rule(asset)
                logger.info(f"  Submitted: {rule_id}")

                # Auto-approve for demo
                system.approve_rule(rule_id, actor="system:seeder")
                logger.info(f"  Approved: {rule_id}")

                total_added += 1
            except ValueError as e:
                logger.error(f"  Failed to submit {rule_id}: {e}")

    logger.info(f"Seeding complete. Added {total_added} rules.")

    if total_added > 0:
        # Create Snapshot
        version_info = system.create_snapshot(
            name="demo-initial",
            description=f"Initial demo data load ({total_added} new rules)",
        )
        logger.info(f"Created snapshot: {version_info.version_id}")

    # Log current stats
    count = system.rule_store.count()
    active = len(system.rule_store.active_rules())
    logger.info(f"System State: Total Rules={count}, Active={active}")

if __name__ == "__main__":
    seed_system()
