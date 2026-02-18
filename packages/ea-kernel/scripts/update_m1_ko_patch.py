#!/usr/bin/env python3
"""Fill missing Korean profile i18n patch entries from audit report.

Usage:
  python packages/ea-kernel/scripts/update_m1_ko_patch.py \
      --profiles EASystem-Infra EASystem-Needs
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import toml

API_BASE = "http://localhost:9000"
LANG = "ko"

SECTION_BY_KIND = {
    "element": "elements",
    "relation": "relations",
    "validity_rule": "validity_rules",
}


def fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:
        raw = response.read().decode("utf-8")
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return loaded


def split_camel(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name).replace("_", " ")


class Translator:
    def __init__(self) -> None:
        self.cache: dict[str, str] = {}

    def en_to_ko(self, text: str) -> str:
        source = text.strip()
        if not source:
            return ""
        cached = self.cache.get(source)
        if cached is not None:
            return cached
        query = urllib.parse.quote(source)
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl=en&tl=ko&dt=t&q={query}"
        )
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                raw = response.read().decode("utf-8")
            payload = json.loads(raw)
            translated = "".join(part[0] for part in payload[0]).strip()
            if translated:
                self.cache[source] = translated
                return translated
        except Exception:
            pass
        self.cache[source] = source
        return source

    def fallback_display_name(self, item_name: str) -> str:
        return self.en_to_ko(split_camel(item_name))

    def fallback_description(self, kind: str, item_name: str) -> str:
        if kind == "validity_rule":
            if item_name.startswith("eas-allow-"):
                return f"프로파일 허용 규칙({item_name})입니다."
            if item_name.startswith("eas-fallback-"):
                return f"프로파일 기본 규칙({item_name})입니다."
            return f"프로파일 정합성 규칙({item_name})입니다."
        if kind == "relation":
            return f"관계({item_name})에 대한 설명입니다."
        return f"요소({item_name})에 대한 설명입니다."


def load_patch(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    return dict(loaded)


def ensure_table(
    patch: dict[str, Any],
    section: str,
    item_name: str,
) -> dict[str, Any]:
    section_table = patch.get(section)
    if not isinstance(section_table, dict):
        section_table = {}
        patch[section] = section_table
    item_table = section_table.get(item_name)
    if not isinstance(item_table, dict):
        item_table = {}
        section_table[item_name] = item_table
    return item_table


def update_profile(profile: str, translator: Translator) -> tuple[str, int, int]:
    audit_url = f"{API_BASE}/i18n/audit/profiles/{urllib.parse.quote(profile)}?lang={LANG}"
    audit = fetch_json(audit_url)
    patch_path_raw = audit.get("patch_path")
    if not isinstance(patch_path_raw, str) or not patch_path_raw:
        raise RuntimeError(f"patch_path missing in audit response for {profile}")

    patch_path = Path(patch_path_raw)
    patch = load_patch(patch_path)
    missing = audit.get("missing", [])
    if not isinstance(missing, list):
        raise RuntimeError(f"missing list malformed for {profile}")

    added = 0
    for entry in missing:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind", ""))
        name = str(entry.get("name", ""))
        field = str(entry.get("field", ""))
        en_current = str(entry.get("en_current", "") or "")
        if kind not in SECTION_BY_KIND or not name or not field:
            continue
        section = SECTION_BY_KIND[kind]
        item = ensure_table(patch, section, name)
        if field in item:
            continue

        if en_current:
            value = translator.en_to_ko(en_current)
        elif field == "display_name":
            value = translator.fallback_display_name(name)
        else:
            value = translator.fallback_description(kind, name)

        item[field] = value
        added += 1

    content = toml.dumps(patch)
    header = f"# {profile} — Korean (ko) i18n Patch (auto-updated)\n\n"
    patch_path.write_text(header + content, encoding="utf-8")

    post = fetch_json(audit_url)
    missing_after = int(post.get("missing_count", 0) or 0)
    total_after = int(post.get("total_issues", 0) or 0)
    return str(patch_path), added, missing_after if total_after >= 0 else missing_after


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["EASystem-Infra", "EASystem-Needs"],
        help="Profile names to patch.",
    )
    args = parser.parse_args()

    translator = Translator()
    for profile in args.profiles:
        path, added, missing_after = update_profile(profile, translator)
        print(f"{profile}: added={added} missing_after={missing_after} path={path}")


if __name__ == "__main__":
    main()
