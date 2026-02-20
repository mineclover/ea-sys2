"""Need lifecycle transition validation using profile metadata (N2)."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from ea_needs.profile_bridge import load_needs_profile


@lru_cache(maxsize=1)
def _profile_transition_table() -> tuple[dict[str, frozenset[str]], frozenset[str], frozenset[str]]:
    """Load and compile transition rules from the needs layer profile."""
    from ea_kernel.profiles.ea_sys import layer_path

    profile = load_needs_profile(layer_path("needs"), validate=False)
    if not profile.state_transitions:
        raise RuntimeError("Needs profile has no [[state_transitions]] entries.")

    explicit_targets: dict[str, set[str]] = {}
    wildcard_targets: set[str] = set()
    known_states: set[str] = set()

    for transition in profile.state_transitions:
        from_state = _normalize_state(transition.from_state)
        to_state = _normalize_state(transition.to_state)

        if from_state != "*":
            known_states.add(from_state)
        if to_state != "*":
            known_states.add(to_state)

        if from_state == "*":
            if to_state != "*":
                wildcard_targets.add(to_state)
            continue

        bucket = explicit_targets.setdefault(from_state, set())
        bucket.add(to_state)

    frozen_explicit = {
        state: frozenset(targets)
        for state, targets in explicit_targets.items()
    }
    return frozen_explicit, frozenset(wildcard_targets), frozenset(known_states)


def _normalize_state(state: str | Enum) -> str:
    raw = state.value if isinstance(state, Enum) else state
    token = str(raw).strip()
    if "." in token:
        token = token.rsplit(".", 1)[-1]
    return token.upper()


def allowed_profile_targets(source_state: str | Enum) -> tuple[str, ...]:
    """Return allowed target states for a source state using profile rules."""
    explicit_targets, wildcard_targets, _ = _profile_transition_table()
    source = _normalize_state(source_state)
    allowed = set(explicit_targets.get(source, frozenset()))
    allowed.update(wildcard_targets)
    return tuple(sorted(allowed))


def ensure_profile_transition(source_state: str | Enum, target_state: str | Enum) -> None:
    """Validate a need state transition against profile-defined rules."""
    explicit_targets, wildcard_targets, known_states = _profile_transition_table()
    source = _normalize_state(source_state)
    target = _normalize_state(target_state)

    if source not in known_states:
        raise ValueError(
            f"Invalid transition source state: {source}. "
            "State is not declared in needs profile transitions."
        )
    if target not in known_states:
        raise ValueError(
            f"Invalid transition target state: {target}. "
            "State is not declared in needs profile transitions."
        )

    allowed = set(explicit_targets.get(source, frozenset()))
    allowed.update(wildcard_targets)
    if target not in allowed:
        raise ValueError(
            f"Invalid transition: {source} -> {target}. "
            f"Allowed by needs profile: {sorted(allowed)}"
        )
