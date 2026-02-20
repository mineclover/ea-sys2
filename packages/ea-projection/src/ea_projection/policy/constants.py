"""Policy constants — default values for projection UI, topic query, and tier definitions.

Extracted from kernel_service.py lines 312-411.
"""

from __future__ import annotations

from typing import Any

PROJECTION_POLICY_FILE_NAME = "projection_policy.toml"

TOPIC_QUERY_POLICY_DEFAULT: dict[str, Any] = {
    "default_depth": 2,
    "max_scope_nodes_per_depth": 40,
    "seed_score_ratio": 0.72,
    "seed_score_floor": 60,
    "min_token_coverage": 0.5,
    "max_seed_count": 8,
    "max_match_count": 16,
    "max_available_topics": 60,
    "scoring": {
        "name_token": 34,
        "display_token": 22,
        "description_token": 10,
        "name_exact": 220,
        "name_contains": 120,
        "display_exact": 180,
        "display_contains": 90,
        "description_contains": 40,
    },
}

PROJECTION_UI_PRESET_KEYS: tuple[str, ...] = ("overview", "actor-route", "trace")

PROJECTION_UI_DEFAULT: dict[str, Any] = {
    "edge_budget_options": [220, 320, 420, 620, 900, 1200, 1600],
    "preset_order": list(PROJECTION_UI_PRESET_KEYS),
    "defaults": {
        "safety_mode": True,
        "surface_only": True,
        "domain_scope": "owned",
    },
    "safety_caps": {
        "topology": {
            "raw": 700,
            "summary": 900,
            "focus": 780,
        },
        "composed": {
            "summary": 760,
            "focus": 700,
        },
        "projection": {
            "l0": 220,
            "l1": 320,
            "l2": 520,
            "l3": 760,
            "l4": 900,
        },
    },
    "presets": {
        "overview": {
            "source_mode": "topology",
            "view_mode": "summary",
            "focus_mode": "core",
            "domain_scope": "owned",
            "surface_only": True,
            "max_edges": 420,
        },
        "actor-route": {
            "source_mode": "projection",
            "projection_level": "l2",
            "focus_depth": 3,
            "domain_scope": "owned",
            "surface_only": True,
            "max_edges": 620,
        },
        "trace": {
            "source_mode": "projection",
            "projection_level": "l4",
            "domain_scope": "all",
            "surface_only": True,
            "max_edges": 900,
        },
    },
}

PROJECTION_UI_LAYER_TUNING: dict[str, dict[str, dict[str, Any]]] = {
    "overview": {
        "infra": {"max_edges": 320},
        "needs": {"max_edges": 360},
        "governance": {"max_edges": 420},
        "decision": {"max_edges": 420},
        "kernel": {"max_edges": 420},
        "flow": {"max_edges": 480},
    },
    "actor-route": {
        "infra": {"focus_depth": 2, "max_edges": 420},
        "needs": {"focus_depth": 3, "max_edges": 480},
        "governance": {"focus_depth": 3, "max_edges": 520},
        "decision": {"focus_depth": 3, "max_edges": 520},
        "kernel": {"focus_depth": 4, "max_edges": 620},
        "flow": {"focus_depth": 4, "max_edges": 620},
    },
    "trace": {
        "infra": {"max_edges": 620, "domain_scope": "all"},
        "needs": {"max_edges": 700, "domain_scope": "all"},
        "governance": {"max_edges": 760, "domain_scope": "all"},
        "decision": {"max_edges": 760, "domain_scope": "all"},
        "kernel": {"max_edges": 900, "domain_scope": "all"},
        "flow": {"max_edges": 900, "domain_scope": "all"},
    },
}
