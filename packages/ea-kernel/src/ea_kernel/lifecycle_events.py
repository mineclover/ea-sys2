"""Lifecycle Events — Phase 4 Governance (TriggerEvent Port).

Lifecycle event port for event-driven governance loop.
Provides:
- LifecycleEvent: 생명주기 이벤트 데이터
- LifecycleEventPort: 이벤트 포트 ABC
- InMemoryEventBus: 테스트용 인메모리 이벤트 버스

References:
- governance_lifecycle.toml: TriggerEvent 3종
  - RuleSubmitted, RuleApprovedEvent, CorpusUpdated
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Callable

from ea_kernel.governance_types import TriggerEventType


# ═══════════════════════════════════════════════════════════════════════════════
# Lifecycle Event — 이벤트 데이터
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class LifecycleEvent:
    """생명주기 이벤트.
    
    governance_lifecycle.toml의 TriggerEvent 3종 런타임 표현.
    """
    event_type: TriggerEventType
    timestamp: str
    
    # Event source
    source_actor: str = ""
    source_module: str = ""
    
    # Payload
    rule_id: str = ""
    corpus_version_id: str = ""
    previous_version_id: str = ""
    from_state: str = ""
    to_state: str = ""
    
    # Additional context
    metadata: tuple[tuple[str, str], ...] = ()
    
    @staticmethod
    def rule_submitted(
        rule_id: str,
        actor: str,
    ) -> LifecycleEvent:
        """RuleSubmitted 이벤트 팩토리."""
        return LifecycleEvent(
            event_type=TriggerEventType.RULE_SUBMITTED,
            timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            source_actor=actor,
            source_module="rule_asset_store",
            rule_id=rule_id,
            from_state="draft",
            to_state="review",
        )
    
    @staticmethod
    def rule_approved(
        rule_id: str,
        actor: str,
    ) -> LifecycleEvent:
        """RuleApprovedEvent 이벤트 팩토리."""
        return LifecycleEvent(
            event_type=TriggerEventType.RULE_APPROVED,
            timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            source_actor=actor,
            source_module="rule_asset_store",
            rule_id=rule_id,
            from_state="review",
            to_state="approved",
        )
    
    @staticmethod
    def corpus_updated(
        corpus_version_id: str,
        previous_version_id: str = "",
        actor: str = "system",
    ) -> LifecycleEvent:
        """CorpusUpdated 이벤트 팩토리."""
        return LifecycleEvent(
            event_type=TriggerEventType.CORPUS_UPDATED,
            timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            source_actor=actor,
            source_module="corpus_version_store",
            corpus_version_id=corpus_version_id,
            previous_version_id=previous_version_id,
        )


# Type alias for event handlers
EventHandler = Callable[[LifecycleEvent], None]


# ═══════════════════════════════════════════════════════════════════════════════
# Lifecycle Event Port ABC
# ═══════════════════════════════════════════════════════════════════════════════

class LifecycleEventPort(abc.ABC):
    """생명주기 이벤트 포트 ABC.
    
    governance_lifecycle.toml의 TriggerEvent 3종 실행 포트.
    이벤트 발행(publish)과 구독(subscribe)을 분리.
    """
    
    @abc.abstractmethod
    def publish(self, event: LifecycleEvent) -> None:
        """이벤트 발행.
        
        Args:
            event: 발행할 이벤트
        """
        ...
    
    @abc.abstractmethod
    def subscribe(
        self,
        event_type: TriggerEventType,
        handler: EventHandler,
    ) -> None:
        """이벤트 구독.
        
        Args:
            event_type: 구독할 이벤트 유형
            handler: 이벤트 핸들러 콜백
        """
        ...
    
    @abc.abstractmethod
    def unsubscribe(
        self,
        event_type: TriggerEventType,
        handler: EventHandler,
    ) -> None:
        """이벤트 구독 해제."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# InMemory Event Bus — 테스트용
# ═══════════════════════════════════════════════════════════════════════════════

class InMemoryEventBus(LifecycleEventPort):
    """인메모리 이벤트 버스.
    
    테스트 및 단일 프로세스용 구현.
    동기적으로 핸들러 호출.
    """
    
    __slots__ = ("_handlers", "_history")
    
    def __init__(self) -> None:
        self._handlers: dict[TriggerEventType, list[EventHandler]] = {}
        self._history: list[LifecycleEvent] = []
    
    def publish(self, event: LifecycleEvent) -> None:
        """이벤트 발행 — 등록된 핸들러를 동기적으로 호출."""
        self._history.append(event)
        
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            handler(event)
    
    def subscribe(
        self,
        event_type: TriggerEventType,
        handler: EventHandler,
    ) -> None:
        """이벤트 구독."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def unsubscribe(
        self,
        event_type: TriggerEventType,
        handler: EventHandler,
    ) -> None:
        """이벤트 구독 해제."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
    
    @property
    def history(self) -> tuple[LifecycleEvent, ...]:
        """발행된 이벤트 이력."""
        return tuple(self._history)
    
    def clear_history(self) -> None:
        """이벤트 이력 초기화."""
        self._history.clear()
    
    def handler_count(self, event_type: TriggerEventType) -> int:
        """특정 이벤트 유형의 핸들러 수."""
        return len(self._handlers.get(event_type, []))
