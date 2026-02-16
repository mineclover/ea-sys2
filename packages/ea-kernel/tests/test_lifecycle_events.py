"""Tests for lifecycle_events — Event Bus and LifecycleEvent.

Extracted from test_governance_phase4.py for module-level focus.

Tests:
- LifecycleEvent factory methods
- InMemoryEventBus publish/subscribe/unsubscribe
- Event type isolation and history
"""

from __future__ import annotations

from ea_kernel.governance_types import TriggerEventType


# ═══════════════════════════════════════════════════════════════════════════════
# LifecycleEvent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLifecycleEvent:
    """Tests for LifecycleEvent factory methods."""

    def test_rule_submitted(self) -> None:
        from ea_kernel.lifecycle_events import LifecycleEvent

        event = LifecycleEvent.rule_submitted("rule-001", "human:alice")

        assert event.event_type == TriggerEventType.RULE_SUBMITTED
        assert event.rule_id == "rule-001"
        assert event.source_actor == "human:alice"
        assert event.from_state == "draft"
        assert event.to_state == "review"

    def test_rule_approved(self) -> None:
        from ea_kernel.lifecycle_events import LifecycleEvent

        event = LifecycleEvent.rule_approved("rule-002", "human:admin")

        assert event.event_type == TriggerEventType.RULE_APPROVED
        assert event.rule_id == "rule-002"

    def test_corpus_updated(self) -> None:
        from ea_kernel.lifecycle_events import LifecycleEvent

        event = LifecycleEvent.corpus_updated("v1.2.0")

        assert event.event_type == TriggerEventType.CORPUS_UPDATED
        assert event.corpus_version_id == "v1.2.0"


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryEventBus Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestInMemoryEventBus:
    """Tests for InMemoryEventBus."""

    def test_publish_subscribe(self) -> None:
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()
        received: list = []

        def handler(event: LifecycleEvent) -> None:
            received.append(event)

        bus.subscribe(TriggerEventType.RULE_SUBMITTED, handler)

        event = LifecycleEvent.rule_submitted("rule-001", "human:alice")
        bus.publish(event)

        assert len(received) == 1
        assert received[0].rule_id == "rule-001"

    def test_multiple_handlers(self) -> None:
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()
        count = {"a": 0, "b": 0}

        def handler_a(event: LifecycleEvent) -> None:
            count["a"] += 1

        def handler_b(event: LifecycleEvent) -> None:
            count["b"] += 1

        bus.subscribe(TriggerEventType.RULE_APPROVED, handler_a)
        bus.subscribe(TriggerEventType.RULE_APPROVED, handler_b)

        bus.publish(LifecycleEvent.rule_approved("rule-001", "admin"))

        assert count["a"] == 1
        assert count["b"] == 1

    def test_unsubscribe(self) -> None:
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()
        received: list = []

        def handler(event: LifecycleEvent) -> None:
            received.append(event)

        bus.subscribe(TriggerEventType.CORPUS_UPDATED, handler)
        bus.unsubscribe(TriggerEventType.CORPUS_UPDATED, handler)

        bus.publish(LifecycleEvent.corpus_updated("v2"))

        assert len(received) == 0

    def test_event_history(self) -> None:
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()

        bus.publish(LifecycleEvent.rule_submitted("r1", "alice"))
        bus.publish(LifecycleEvent.rule_approved("r1", "admin"))
        bus.publish(LifecycleEvent.corpus_updated("v2"))

        assert len(bus.history) == 3
        assert bus.history[0].event_type == TriggerEventType.RULE_SUBMITTED
        assert bus.history[1].event_type == TriggerEventType.RULE_APPROVED
        assert bus.history[2].event_type == TriggerEventType.CORPUS_UPDATED

    def test_event_type_isolation(self) -> None:
        """Events only go to handlers for their type."""
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()
        received: list = []

        def handler(event: LifecycleEvent) -> None:
            received.append(event)

        bus.subscribe(TriggerEventType.RULE_SUBMITTED, handler)

        # Publish different event type
        bus.publish(LifecycleEvent.corpus_updated("v2"))

        assert len(received) == 0  # Not delivered

    def test_handler_count(self) -> None:
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()

        def h1(e: LifecycleEvent) -> None: pass
        def h2(e: LifecycleEvent) -> None: pass

        bus.subscribe(TriggerEventType.RULE_SUBMITTED, h1)
        bus.subscribe(TriggerEventType.RULE_SUBMITTED, h2)

        assert bus.handler_count(TriggerEventType.RULE_SUBMITTED) == 2
        assert bus.handler_count(TriggerEventType.CORPUS_UPDATED) == 0
