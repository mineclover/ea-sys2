"""SDLC symmetric profile catalog."""

from __future__ import annotations

from pathlib import Path

PROFILE_FILE_MAP: dict[str, str] = {
    "layer-stack": "00-layer-stack.toml",
    "arch-decision": "20-arch-decision.toml",
    "requirements": "30-requirements.toml",
    "domain-model": "40-domain-model.toml",
    "pipeline": "50-pipeline.toml",
    "projection": "60-projection.toml",
}

PROFILE_DIR = Path(__file__).resolve().parent


def profile_path(profile_id: str) -> Path:
    """Return the filesystem path for SDLC profile spec files."""
    try:
        filename = PROFILE_FILE_MAP[profile_id]
    except KeyError as exc:
        allowed = ", ".join(sorted(PROFILE_FILE_MAP))
        raise KeyError(f"Unknown SDLC profile id '{profile_id}'. Allowed: {allowed}") from exc
    return PROFILE_DIR / filename


__all__ = ["PROFILE_FILE_MAP", "PROFILE_DIR", "profile_path"]
