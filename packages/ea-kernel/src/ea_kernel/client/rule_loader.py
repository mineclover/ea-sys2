"""Rule Corpus → TypeDB synchronization.

TOML is the single source of truth; TypeDB is a queryable mirror.
Generates INSERT TypeQL from RuleCorpusEntry instances and syncs
the full corpus into the validity_rule entity type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_kernel.client.connection import KernelDBClient
    from ea_kernel.rule_corpus import RuleCorpus
    from ea_kernel.types import RuleCorpusEntry

BATCH_SIZE = 15


def _escape(s: str) -> str:
    """Escape a string for TypeQL string literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _entry_to_typeql(entry: RuleCorpusEntry) -> str:
    """Convert a single RuleCorpusEntry to an INSERT TypeQL statement."""
    r = entry.rule
    m = entry.metadata

    parts = [
        "insert $r isa validity_rule",
        f'has rule_id "{_escape(r.id)}"',
        f'has source_pattern "{_escape(r.source_pattern)}"',
        f'has target_pattern "{_escape(r.target_pattern)}"',
        f'has relationship_name "{_escape(r.relationship_name)}"',
        f"has is_valid {str(r.valid).lower()}",
        f"has rule_priority {r.priority}",
    ]

    if r.notes:
        parts.append(f'has rule_notes "{_escape(r.notes)}"')

    # Metadata fields
    parts.append(f'has rule_domain "{_escape(m.domain)}"')

    for tag in m.tags:
        parts.append(f'has rule_tag "{_escape(tag)}"')

    parts.append(f'has rule_category "{_escape(m.category.value)}"')
    parts.append(f'has rule_confidence "{_escape(m.confidence.value)}"')
    parts.append(f'has rule_source "{_escape(m.source)}"')
    parts.append(f'has established_version "{_escape(m.established_version)}"')

    if m.rationale:
        parts.append(f'has rationale "{_escape(m.rationale)}"')

    return ", ".join(parts) + ";"


def sync_corpus_to_typedb(
    client: KernelDBClient,
    corpus: RuleCorpus,
    *,
    clear_existing: bool = True,
) -> int:
    """Synchronize a RuleCorpus into TypeDB validity_rule entities.

    Args:
        client: TypeDB client connection.
        corpus: The rule corpus to persist.
        clear_existing: If True, delete all existing validity_rule entities first.

    Returns:
        Number of rules inserted.
    """
    if clear_existing:
        client.execute_write(
            "match $r isa validity_rule; delete $r isa validity_rule;"
        )

    entries = corpus.entries
    inserted = 0

    for i in range(0, len(entries), BATCH_SIZE):
        batch = entries[i : i + BATCH_SIZE]
        stmts = [_entry_to_typeql(e) for e in batch]
        query = "\n".join(stmts)
        client.execute_write(query)
        inserted += len(batch)

    return inserted
