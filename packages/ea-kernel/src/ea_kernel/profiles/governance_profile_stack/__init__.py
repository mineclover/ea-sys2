"""Official governance profile stack catalog."""

from __future__ import annotations

from pathlib import Path

PROFILE_FILE_MAP: dict[str, str] = {
    "meta": "00-governance-meta-model.toml",
    "external": "20-external-governance.toml",
}

PROFILE_DIR = Path(__file__).resolve().parent


def profile_path(profile_id: str) -> Path:
    """Return the filesystem path for governance profile stack spec files."""
    try:
        filename = PROFILE_FILE_MAP[profile_id]
    except KeyError as exc:
        allowed = ", ".join(sorted(PROFILE_FILE_MAP))
        raise KeyError(
            f"Unknown governance profile stack id '{profile_id}'. Allowed: {allowed}"
        ) from exc
    return PROFILE_DIR / filename


__all__ = ["PROFILE_FILE_MAP", "PROFILE_DIR", "profile_path"]
