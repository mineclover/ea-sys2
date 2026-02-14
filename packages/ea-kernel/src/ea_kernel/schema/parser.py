"""Pure Python TypeQL schema parser for kernel.tql.

Parses the define block to extract entity types, relation types,
and attribute types. No TypeDB dependency required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedAttribute:
    name: str
    value_type: str


@dataclass(frozen=True)
class ParsedRole:
    name: str


@dataclass(frozen=True)
class ParsedEntity:
    name: str
    parent: str | None = None
    is_abstract: bool = False
    owns: tuple[str, ...] = ()
    owns_key: tuple[str, ...] = ()
    plays: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedRelation:
    name: str
    parent: str | None = None
    roles: tuple[ParsedRole, ...] = ()
    owns: tuple[str, ...] = ()
    owns_key: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedSchema:
    attributes: tuple[ParsedAttribute, ...]
    entities: tuple[ParsedEntity, ...]
    relations: tuple[ParsedRelation, ...]


def _strip_comments(text: str) -> str:
    """Remove # and ## comments from TypeQL."""
    lines = []
    for line in text.splitlines():
        # Remove # comments (TypeQL standard single-hash comments)
        idx = line.find("#")
        if idx >= 0:
            line = line[:idx]
        lines.append(line)
    return "\n".join(lines)


def _split_statements(define_block: str) -> list[str]:
    """Split a define block into individual statements separated by semicolons."""
    statements: list[str] = []
    current: list[str] = []

    for line in define_block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        current.append(stripped)
        if stripped.endswith(";"):
            statements.append(" ".join(current))
            current = []

    if current:
        statements.append(" ".join(current))

    return statements


def _parse_attribute_stmt(stmt: str) -> ParsedAttribute | None:
    """Parse: attribute uid, value string;"""
    m = re.match(r"attribute\s+(\w+)\s*,\s*value\s+(\w+)\s*;?", stmt)
    if m:
        return ParsedAttribute(name=m.group(1), value_type=m.group(2))
    return None


def _parse_entity_stmt(stmt: str) -> ParsedEntity | None:
    """Parse entity definitions with optional @abstract, sub, owns, plays."""
    # Match: entity <name> [@abstract] [, sub <parent>] [, owns ...] [, plays ...];
    m = re.match(r"entity\s+(\w+)", stmt)
    if not m:
        return None

    name = m.group(1)
    is_abstract = "@abstract" in stmt
    parent: str | None = None

    sub_m = re.search(r"sub\s+(\w+)", stmt)
    if sub_m:
        parent = sub_m.group(1)

    owns: list[str] = []
    owns_key: list[str] = []
    for own_m in re.finditer(r"owns\s+(\w+)(\s+@key)?", stmt):
        attr_name = own_m.group(1)
        if own_m.group(2):
            owns_key.append(attr_name)
        else:
            owns.append(attr_name)

    plays: list[str] = []
    for play_m in re.finditer(r"plays\s+([\w]+:[\w]+)", stmt):
        plays.append(play_m.group(1))

    return ParsedEntity(
        name=name,
        parent=parent,
        is_abstract=is_abstract,
        owns=tuple(owns),
        owns_key=tuple(owns_key),
        plays=tuple(plays),
    )


def _parse_relation_stmt(stmt: str) -> ParsedRelation | None:
    """Parse relation definitions with optional sub, relates, owns."""
    m = re.match(r"relation\s+(\w+)", stmt)
    if not m:
        return None

    name = m.group(1)
    parent: str | None = None

    sub_m = re.search(r"sub\s+(\w+)", stmt)
    if sub_m:
        parent = sub_m.group(1)

    roles: list[ParsedRole] = []
    for rel_m in re.finditer(r"relates\s+(\w+)(?:\s+as\s+\w+)?", stmt):
        roles.append(ParsedRole(name=rel_m.group(1)))

    owns: list[str] = []
    owns_key: list[str] = []
    for own_m in re.finditer(r"owns\s+(\w+)(\s+@key)?", stmt):
        attr_name = own_m.group(1)
        if own_m.group(2):
            owns_key.append(attr_name)
        else:
            owns.append(attr_name)

    return ParsedRelation(
        name=name,
        parent=parent,
        roles=tuple(roles),
        owns=tuple(owns),
        owns_key=tuple(owns_key),
    )


def parse_typeql(content: str) -> ParsedSchema:
    """Parse a TypeQL define block into structured schema objects."""
    cleaned = _strip_comments(content)

    # Extract the define block
    define_idx = cleaned.find("define")
    if define_idx < 0:
        return ParsedSchema(attributes=(), entities=(), relations=())

    define_block = cleaned[define_idx + len("define"):]
    statements = _split_statements(define_block)

    attributes: list[ParsedAttribute] = []
    entities: list[ParsedEntity] = []
    relations: list[ParsedRelation] = []

    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue

        if stmt.startswith("attribute "):
            attr = _parse_attribute_stmt(stmt)
            if attr:
                attributes.append(attr)
        elif stmt.startswith("entity "):
            entity = _parse_entity_stmt(stmt)
            if entity:
                entities.append(entity)
        elif stmt.startswith("relation "):
            rel = _parse_relation_stmt(stmt)
            if rel:
                relations.append(rel)
        # Additional plays statements (standalone)
        elif "plays" in stmt and not stmt.startswith(("entity", "relation", "attribute")):
            # e.g., "feature plays triggering:event;"
            # These augment existing entities — skip for now (handled in .tql directly)
            pass

    return ParsedSchema(
        attributes=tuple(attributes),
        entities=tuple(entities),
        relations=tuple(relations),
    )
