#!/usr/bin/env python3
"""Normalize Korean terminology in M1 profile patch files."""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path
from typing import Any

import toml

PATCH_DIR = Path("packages/ea-kernel/src/ea_kernel/profiles/ea_sys")

TEXT_REPLACEMENTS = {
    "S Q Lite": "SQLite",
    "행-데이터": "로우 데이터",
    "냉동 복합": "불변 복합체",
    "동결가치대상": "불변 값 객체",
    "요구 사항": "요구",
    "요구을": "요구를",
    "요구이": "요구가",
    "수명 주기": "수명주기",
    "라이프사이클": "수명주기",
    "수명주기 상태 필요:": "요구 수명주기 상태:",
    "수명주기 필요 상태:": "요구 수명주기 상태:",
    "카탈로그 방법": "카탈로그 메서드",
    "또 다른 욕구": "다른 요구",
    "욕구 관계 유형": "요구 관계 유형",
    "욕구를 생성하는": "요구를 생성하는",
    "욕구가 다른 욕구": "요구가 다른 요구",
    "욕구는 또 다른 욕구": "요구가 다른 요구",
    "필요한 프로세스를 위한": "요구 프로세스를 위한",
    "동결된": "불변",
    "저장소 필요": "요구 저장소",
    "카탈로그 필요": "요구 카탈로그",
    "필요 상태": "요구 상태",
    "필요 관계": "요구 관계",
    "필요를": "요구를",
    "필요가": "요구가",
    "필요성": "요구",
    "를 위한layers/{layer}.db": "를 위한 layers/{layer}.db",
    "위한layers/{layer}.db": "위한 layers/{layer}.db",
    "거버넌스, 결정, 요구": "거버넌스, 의사결정, 요구",
    "결정 증거": "의사결정 증거",
}

NEEDS_DISPLAY_NAME_OVERRIDES = {
    "NeedCatalog": "요구 카탈로그",
    "NeedStatement": "요구 명세",
    "Need": "요구",
    "NeedRelation": "요구 관계",
    "NeedProcessUnit": "요구 프로세스 단위",
    "NeedStatusDraft": "요구 상태: 초안",
    "NeedStatusExpressed": "요구 상태: 표현됨",
    "NeedStatusAcknowledged": "요구 상태: 확인됨",
    "NeedStatusAddressed": "요구 상태: 해결됨",
    "NeedStatusWithdrawn": "요구 상태: 철회됨",
    "NeedPriorityCritical": "요구 우선순위: 긴급",
    "NeedPriorityHigh": "요구 우선순위: 높음",
    "NeedPriorityMedium": "요구 우선순위: 중간",
    "NeedPriorityLow": "요구 우선순위: 낮음",
    "CauseTypeEmotional": "원인 유형: 감정",
    "CauseTypeSituational": "원인 유형: 상황",
    "CauseTypePhysical": "원인 유형: 물리",
    "CauseTypeLogical": "원인 유형: 논리",
    "CauseTypeMental": "원인 유형: 정신",
    "CauseTypePhilosophical": "원인 유형: 철학",
    "ResolutionComplexitySimple": "해결 복잡도: 단순",
    "ResolutionComplexityProcedural": "해결 복잡도: 절차형",
    "ResolutionComplexityComplex": "해결 복잡도: 복합",
    "JustificationBecause": "정당화: 이유",
    "JustificationInOrderTo": "정당화: 목적",
    "NeedRelDependsOn": "요구 관계: 의존",
    "NeedRelConflictsWith": "요구 관계: 충돌",
    "NeedRelSupports": "요구 관계: 지원",
    "NeedRelRefines": "요구 관계: 정제",
    "NeedRelSupersedes": "요구 관계: 대체",
    "NeedPurposeSafety": "목적: 안전",
    "NeedPurposeEfficiency": "목적: 효율",
    "NeedPurposeUsability": "목적: 사용성",
    "NeedPurposeCompliance": "목적: 준수",
    "NeedPurposeGrowth": "목적: 성장",
    "NeedPurposeTrust": "목적: 신뢰",
    "IdentifyStage": "단계: 식별",
    "QueryStage": "단계: 탐색",
    "ModelDetailStage": "단계: 모델 상세화",
    "NeedsSchema": "요구 스키마",
    "NeedsQueryService": "요구 조회 서비스",
    "NeedRepository": "요구 저장소",
    "ConditionRegistry": "조건 레지스트리",
    "NeedExpressedEvent": "요구 표현 이벤트",
    "NeedRevisedEvent": "요구 수정 이벤트",
    "NeedStatusTransitionEvent": "요구 상태 전이 이벤트",
}

INFRA_DISPLAY_NAME_OVERRIDES = {
    "SQLiteStorageBackend": "SQLite 저장소 백엔드",
}


def _replace_text(value: str) -> str:
    out = value
    for before, after in TEXT_REPLACEMENTS.items():
        out = out.replace(before, after)
    return out.strip()


def _normalize_table_strings(table: dict[str, Any]) -> None:
    for key, raw in list(table.items()):
        if not isinstance(raw, dict):
            continue
        for field in ("display_name", "description"):
            value = raw.get(field)
            if isinstance(value, str):
                raw[field] = _replace_text(value)


def _apply_overrides(
    doc: dict[str, Any],
    *,
    element_overrides: dict[str, str],
) -> None:
    elements = doc.get("elements")
    if not isinstance(elements, dict):
        return
    for name, display_name in element_overrides.items():
        item = elements.get(name)
        if not isinstance(item, dict):
            continue
        item["display_name"] = display_name


def _resolve_patch_path(profile: str) -> Path:
    filename = f"{profile.lower()}.ko.patch.toml"
    return PATCH_DIR / filename


def _load_doc(path: Path) -> dict[str, Any]:
    loaded = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Invalid TOML document: {path}")
    return dict(loaded)


def normalize_profile(profile: str, path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    doc = _load_doc(path)
    for section in ("elements", "relations", "validity_rules"):
        table = doc.get(section)
        if isinstance(table, dict):
            _normalize_table_strings(table)

    if profile == "EASystem-Needs":
        _apply_overrides(doc, element_overrides=NEEDS_DISPLAY_NAME_OVERRIDES)
    elif profile == "EASystem-Infra":
        _apply_overrides(doc, element_overrides=INFRA_DISPLAY_NAME_OVERRIDES)

    content = toml.dumps(doc)
    header = f"# {profile} — Korean (ko) i18n Patch (normalized)\n\n"
    path.write_text(header + content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["EASystem-Infra", "EASystem-Needs"],
        help="Profile names to normalize.",
    )
    args = parser.parse_args()

    for profile in args.profiles:
        path = _resolve_patch_path(profile)
        if not path.exists():
            raise FileNotFoundError(path)
        normalize_profile(profile, path)
        print(f"{profile}: normalized ({path})")


if __name__ == "__main__":
    main()
