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
    "projection": "70-projection.toml",
    "web-kernel-viz": "60-web-kernel-viz.toml",
    "development": "80-development.toml",
}

EXPERIMENTAL_FILE_MAP: dict[str, str] = {
    "recursive-node": "85-recursive-node.toml",
}

LAYER_ORDER: tuple[str, ...] = (
    "infra",
    "governance",
    "decision",
    "needs",
    "kernel",
    "flow",
    "projection",
    "web-kernel-viz",
    "development",
)

# Experimental profiles (not part of LAYER_ORDER / validation pipeline)
EXPERIMENTAL_PROFILES: tuple[str, ...] = (
    "recursive-node",
)

PROFILE_DIR = Path(__file__).resolve().parent


def layer_path(layer: str) -> Path:
    """Return the filesystem path for an EA System layer profile file."""
    all_maps = {**LAYER_FILE_MAP, **EXPERIMENTAL_FILE_MAP}
    try:
        filename = all_maps[layer]
    except KeyError as exc:
        allowed = ", ".join(sorted(all_maps))
        raise KeyError(f"Unknown EA System layer '{layer}'. Allowed: {allowed}") from exc
    return PROFILE_DIR / filename


__all__ = ["LAYER_FILE_MAP", "LAYER_ORDER", "EXPERIMENTAL_PROFILES", "EXPERIMENTAL_FILE_MAP", "PROFILE_DIR", "layer_path"]
