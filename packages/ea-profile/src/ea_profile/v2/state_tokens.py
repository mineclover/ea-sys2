"""Shared state-token alias/canonical mapping helpers."""

from __future__ import annotations

from collections.abc import Iterable


def canonicalize_state_token(value: str) -> str:
    """Normalize state token text for canonical comparisons."""

    normalized = str(value).strip()
    if "." in normalized:
        normalized = normalized.rsplit(".", 1)[-1]
    return normalized.upper()


def parse_state_reference(value: str) -> tuple[str | None, str]:
    """Parse a state reference into optional layer + normalized token."""

    raw = str(value).strip()
    if raw == "*":
        return None, raw
    if "." in raw:
        layer, _, token = raw.rpartition(".")
        if layer and token:
            return layer, canonicalize_state_token(token)
    return None, canonicalize_state_token(raw)


def state_reference_aliases(
    *,
    token_id: str,
    canonical: str,
    aliases: Iterable[str],
) -> tuple[str, ...]:
    """Build normalized reference aliases for one state token."""

    ordered = [
        canonicalize_state_token(token_id),
        canonicalize_state_token(canonical),
        *(canonicalize_state_token(alias) for alias in aliases),
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for item in ordered:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return tuple(unique)


def layered_state_reference(layer: str, value: str) -> str:
    """Build canonical layered state reference, preserving wildcard support."""

    if value == "*":
        return value
    return f"{layer}.{canonicalize_state_token(value).lower()}"
