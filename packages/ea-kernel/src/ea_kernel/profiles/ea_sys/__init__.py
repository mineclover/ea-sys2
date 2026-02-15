"""Official EA System layer profile catalog."""

from __future__ import annotations

from pathlib import Path

LAYER_FILE_MAP: dict[str, str] = {
    "infra": "00-infra.toml",
    "governance": "10-governance.toml",
    "decision": "20-decision.toml",
    "needs": "30-needs.toml",
    "kernel": "40-kernel.toml",
    "flow": "50-flow.toml",
}

LAYER_ORDER: tuple[str, ...] = (
    "infra",
    "governance",
    "decision",
    "needs",
    "kernel",
    "flow",
)

PROFILE_DIR = Path(__file__).resolve().parent


def layer_path(layer: str) -> Path:
    """Return the filesystem path for an EA System layer profile file."""
    try:
        filename = LAYER_FILE_MAP[layer]
    except KeyError as exc:
        allowed = ", ".join(sorted(LAYER_FILE_MAP))
        raise KeyError(f"Unknown EA System layer '{layer}'. Allowed: {allowed}") from exc
    return PROFILE_DIR / filename


__all__ = ["LAYER_FILE_MAP", "LAYER_ORDER", "PROFILE_DIR", "layer_path"]
