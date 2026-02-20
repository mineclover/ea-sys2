"""SDLC Analyzer — S4 Analysis for SDLC domain snapshots.

The analyzer compiles analysis dimensions from SDLC profile ``elements`` and
``state_transitions`` metadata, then evaluates snapshot trends from SDLCStore.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import TYPE_CHECKING

from ea_kernel.profiles.sdlc import PROFILE_FILE_MAP, profile_path
from ea_profile.loader import load_profile
from ea_profile.types import KernelProfile

if TYPE_CHECKING:
    from sdlc_domain.sdlc_store import SDLCStore, StoredSDLCSnapshot


_STATE_ALIAS_SUFFIX_RE = re.compile(
    r"(?:status|state)([A-Za-z0-9_]+)$",
    flags=re.IGNORECASE,
)
_STATE_ALIAS_SPLIT_RE = re.compile(r"[_\-\s]+")
_CAMEL_CASE_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+")
_STATE_ALIAS_CATEGORIES = frozenset({"goal", "context", "state"})


def _now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"


def _normalize_token(token: str) -> str:
    normalized = str(token).strip()
    if "." in normalized:
        normalized = normalized.rsplit(".", 1)[-1]
    return normalized.upper()


def _state_alias_from_element_name(name: str) -> str:
    """Extract canonical state alias from element names like NeedStatusDraft."""

    match = _STATE_ALIAS_SUFFIX_RE.search(name)
    if match is None:
        return ""

    suffix = match.group(1).strip()
    if not suffix:
        return ""

    split_tokens = [token for token in _STATE_ALIAS_SPLIT_RE.split(suffix) if token]
    if split_tokens:
        return _normalize_token(split_tokens[-1])

    camel_tokens = _CAMEL_CASE_TOKEN_RE.findall(suffix)
    if camel_tokens:
        return _normalize_token(camel_tokens[-1])

    return _normalize_token(suffix)


def _parse_iso_datetime(raw: str) -> datetime | None:
    token = raw.strip()
    if not token:
        return None

    if token.endswith("Z"):
        token = token[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(token)
    except ValueError:
        return None


def _metadata_lookup(snapshot: StoredSDLCSnapshot, key: str) -> str:
    key_token = key.casefold()
    for meta_key, value in snapshot.metadata:
        if meta_key.casefold() == key_token:
            return value
    return ""


@dataclass(frozen=True)
class SDLCProfileDimension:
    """Profile-derived analysis dimensions for a single SDLC profile."""

    profile_id: str
    profile_name: str
    active_elements: tuple[str, ...] = ()
    passive_elements: tuple[str, ...] = ()
    behavior_elements: tuple[str, ...] = ()
    governance_elements: tuple[str, ...] = ()
    state_tokens: tuple[str, ...] = ()
    terminal_states: tuple[str, ...] = ()
    success_states: tuple[str, ...] = ()
    state_depth: tuple[tuple[str, int], ...] = ()

    @property
    def all_elements(self) -> tuple[str, ...]:
        seen: list[str] = []
        for name in (
            self.active_elements
            + self.passive_elements
            + self.behavior_elements
            + self.governance_elements
        ):
            if name not in seen:
                seen.append(name)
        return tuple(seen)


@dataclass(frozen=True)
class SDLCProfileMetric:
    """Computed metrics for one SDLC profile stream."""

    profile_id: str
    total_snapshots: int = 0
    total_lineages: int = 0
    throughput_per_day: float = 0.0
    completed_snapshots: int = 0
    completed_throughput_per_day: float = 0.0
    completion_rate: float = 0.0
    success_rate: float = 0.0
    avg_state_progress: float = 0.0
    dimension_coverage: float = 0.0
    latest_state_distribution: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class SDLCAnalysisReport:
    """S4 aggregate output for SDLC snapshots."""

    report_id: str
    created_at: str
    total_snapshots_analyzed: int = 0
    analysis_period_start: str = ""
    analysis_period_end: str = ""
    profile_dimensions: tuple[SDLCProfileDimension, ...] = ()
    profile_metrics: tuple[SDLCProfileMetric, ...] = ()
    requirements_throughput: float = 0.0
    pipeline_success_rate: float = 0.0
    adr_effectiveness: float = 0.0

    @property
    def health_score(self) -> float:
        """Weighted health score from the three SDLC headline metrics (0-100)."""
        if not self.profile_metrics:
            return 0.0

        throughput_component = max(0.0, min(1.0, self.requirements_throughput))
        success_component = max(0.0, min(1.0, self.pipeline_success_rate))
        adr_component = max(0.0, min(1.0, self.adr_effectiveness))
        blended = (throughput_component * 0.3) + (success_component * 0.4) + (adr_component * 0.3)
        return max(0.0, min(100.0, blended * 100.0))


def _collect_state_tokens(profile: KernelProfile) -> tuple[str, ...]:
    transition_tokens = {
        _normalize_token(transition.from_state)
        for transition in profile.state_transitions
        if transition.from_state != "*"
    }
    transition_tokens.update(
        _normalize_token(transition.to_state)
        for transition in profile.state_transitions
        if transition.to_state != "*"
    )

    element_tokens: set[str] = set()
    for element in profile.elements:
        if element.kernel_type != "state":
            continue
        element_tokens.add(_normalize_token(element.name))
        if element.category.casefold() in _STATE_ALIAS_CATEGORIES:
            alias = _state_alias_from_element_name(element.name)
            if alias:
                element_tokens.add(alias)

    if transition_tokens:
        if not element_tokens:
            return tuple(sorted(transition_tokens))
        shared = sorted(token for token in transition_tokens if token in element_tokens)
        if shared:
            return tuple(shared)
        return tuple(sorted(transition_tokens))

    return tuple(sorted(element_tokens))


def _build_transition_model(
    profile: KernelProfile,
    state_tokens: tuple[str, ...],
) -> tuple[dict[str, int], tuple[str, ...], tuple[str, ...]]:
    edges: dict[str, set[str]] = {}
    states: set[str] = set(state_tokens)

    for transition in profile.state_transitions:
        source = _normalize_token(transition.from_state)
        target = _normalize_token(transition.to_state)
        if source == "*" or target == "*":
            continue
        states.add(source)
        states.add(target)
        edges.setdefault(source, set()).add(target)

    if not states:
        return {}, (), ()

    depth: dict[str, int] = dict.fromkeys(states, 0)
    for _ in range(len(states)):
        changed = False
        for source, targets in edges.items():
            src_depth = depth[source]
            for target in targets:
                candidate = src_depth + 1
                if candidate > depth[target]:
                    depth[target] = candidate
                    changed = True
        if not changed:
            break

    source_states = set(edges)
    terminal_states = tuple(sorted(state for state in states if state not in source_states))

    non_terminal_states = [state for state in states if state in source_states]
    if non_terminal_states:
        best_depth = max(depth[state] for state in non_terminal_states)
        success_states = tuple(sorted(state for state in non_terminal_states if depth[state] == best_depth))
    else:
        best_depth = max(depth.values())
        success_states = tuple(sorted(state for state in states if depth[state] == best_depth))

    return depth, terminal_states, success_states


def _build_dimension(profile_id: str, profile: KernelProfile) -> SDLCProfileDimension:
    active_elements = tuple(element.name for element in profile.elements if element.kernel_type == "structure")
    passive_elements = tuple(element.name for element in profile.elements if element.kernel_type == "item")
    behavior_elements = tuple(element.name for element in profile.elements if element.kernel_type == "step")
    governance_elements = tuple(element.name for element in profile.elements if element.kernel_type == "feature")

    state_tokens = _collect_state_tokens(profile)
    depth, terminal_states, success_states = _build_transition_model(profile, state_tokens)
    state_depth = tuple(sorted(depth.items()))

    return SDLCProfileDimension(
        profile_id=profile_id,
        profile_name=profile.name,
        active_elements=active_elements,
        passive_elements=passive_elements,
        behavior_elements=behavior_elements,
        governance_elements=governance_elements,
        state_tokens=state_tokens,
        terminal_states=terminal_states,
        success_states=success_states,
        state_depth=state_depth,
    )


@lru_cache(maxsize=1)
def _compiled_dimensions() -> tuple[SDLCProfileDimension, ...]:
    dimensions: list[SDLCProfileDimension] = []
    for profile_id in sorted(PROFILE_FILE_MAP):
        if profile_id == "layer-stack":
            continue
        profile = load_profile(profile_path(profile_id))
        if not profile.state_transitions:
            continue
        dimensions.append(_build_dimension(profile_id, profile))
    return tuple(dimensions)


def _record_sort_key(snapshot: StoredSDLCSnapshot) -> tuple[str, int, str]:
    return snapshot.recorded_at, snapshot.version, snapshot.stored_at


def _period_days(records: tuple[StoredSDLCSnapshot, ...]) -> float:
    timestamps = [
        parsed
        for parsed in (_parse_iso_datetime(record.recorded_at) for record in records)
        if parsed is not None
    ]
    if not timestamps:
        return 1.0
    elapsed = (max(timestamps) - min(timestamps)).total_seconds() / 86_400.0
    return max(1.0, elapsed)


def _analyze_profile_records(
    dimension: SDLCProfileDimension,
    records: tuple[StoredSDLCSnapshot, ...],
) -> SDLCProfileMetric:
    if not records:
        return SDLCProfileMetric(profile_id=dimension.profile_id)

    total_snapshots = len(records)
    period_days = _period_days(records)
    throughput_per_day = total_snapshots / period_days

    terminal_states = set(dimension.terminal_states)
    completed_snapshots = sum(
        1 for record in records if _normalize_token(record.status) in terminal_states
    )
    completed_throughput_per_day = completed_snapshots / period_days

    latest_by_lineage: dict[str, StoredSDLCSnapshot] = {}
    for record in records:
        previous = latest_by_lineage.get(record.lineage_id)
        if previous is None or _record_sort_key(record) > _record_sort_key(previous):
            latest_by_lineage[record.lineage_id] = record

    latest_records = tuple(latest_by_lineage.values())
    total_lineages = len(latest_records)

    completion_rate = (
        sum(1 for record in latest_records if _normalize_token(record.status) in terminal_states)
        / total_lineages
        if total_lineages > 0
        else 0.0
    )

    success_states = set(dimension.success_states)
    success_rate = (
        sum(1 for record in latest_records if _normalize_token(record.status) in success_states)
        / total_lineages
        if total_lineages > 0 and success_states
        else 0.0
    )

    state_depth_map = dict(dimension.state_depth)
    max_depth = max(state_depth_map.values()) if state_depth_map else 0
    if total_lineages == 0 or max_depth == 0:
        avg_state_progress = 0.0
    else:
        avg_state_progress = sum(
            state_depth_map.get(_normalize_token(record.status), 0) / max_depth
            for record in latest_records
        ) / total_lineages

    latest_states = Counter(_normalize_token(record.status) for record in latest_records)
    latest_state_distribution = tuple(
        sorted(latest_states.items(), key=lambda item: (-item[1], item[0]))
    )

    known_elements = set(dimension.all_elements)
    seen_elements = {
        element_name
        for element_name in (_metadata_lookup(record, "element") for record in records)
        if element_name in known_elements
    }
    dimension_coverage = (
        len(seen_elements) / len(known_elements)
        if known_elements
        else 0.0
    )

    return SDLCProfileMetric(
        profile_id=dimension.profile_id,
        total_snapshots=total_snapshots,
        total_lineages=total_lineages,
        throughput_per_day=throughput_per_day,
        completed_snapshots=completed_snapshots,
        completed_throughput_per_day=completed_throughput_per_day,
        completion_rate=completion_rate,
        success_rate=success_rate,
        avg_state_progress=avg_state_progress,
        dimension_coverage=dimension_coverage,
        latest_state_distribution=latest_state_distribution,
    )


class SDLCAnalyzer:
    """Analyze SDLC snapshots and generate S4 aggregate reports."""

    __slots__ = ("_store",)

    def __init__(self, sdlc_store: SDLCStore) -> None:
        self._store = sdlc_store

    def profile_dimensions(self) -> tuple[SDLCProfileDimension, ...]:
        """Return profile-derived analysis dimensions."""
        return _compiled_dimensions()

    def analyze_profile_metrics(self) -> tuple[SDLCProfileMetric, ...]:
        """Compute metrics for each profile with state-transition dimensions."""
        dimensions = self.profile_dimensions()
        records = self._store.query()
        records_by_profile: dict[str, list[StoredSDLCSnapshot]] = {}
        for record in records:
            records_by_profile.setdefault(record.profile_id, []).append(record)

        metrics = [
            _analyze_profile_records(
                dimension,
                tuple(records_by_profile.get(dimension.profile_id, [])),
            )
            for dimension in dimensions
        ]
        return tuple(metrics)

    def generate_report(self, report_id: str | None = None) -> SDLCAnalysisReport:
        """Generate an SDLC analysis report from all stored snapshots."""
        if report_id is None:
            report_id = f"sdlc-report-{uuid.uuid4().hex[:8]}"

        now = _now_iso()
        dimensions = self.profile_dimensions()
        metrics = self.analyze_profile_metrics()
        metrics_by_profile = {metric.profile_id: metric for metric in metrics}

        requirements_metric = metrics_by_profile.get("requirements")
        pipeline_metric = metrics_by_profile.get("pipeline")
        adr_metric = metrics_by_profile.get("arch-decision")

        requirements_throughput = (
            requirements_metric.completed_throughput_per_day
            if requirements_metric is not None
            else 0.0
        )
        pipeline_success_rate = (
            pipeline_metric.success_rate
            if pipeline_metric is not None
            else 0.0
        )
        adr_effectiveness = (
            adr_metric.avg_state_progress
            if adr_metric is not None
            else 0.0
        )

        all_records = self._store.query()
        period_start = ""
        period_end = ""
        if all_records:
            times = [record.recorded_at for record in all_records if record.recorded_at]
            if times:
                period_start = min(times)
                period_end = max(times)

        return SDLCAnalysisReport(
            report_id=report_id,
            created_at=now,
            total_snapshots_analyzed=len(all_records),
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            profile_dimensions=dimensions,
            profile_metrics=metrics,
            requirements_throughput=requirements_throughput,
            pipeline_success_rate=pipeline_success_rate,
            adr_effectiveness=adr_effectiveness,
        )
