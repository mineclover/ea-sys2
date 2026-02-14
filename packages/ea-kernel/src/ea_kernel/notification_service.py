"""Notification Service — Governance notification interface (Phase 5)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Notification:
    recipient: str
    subject: str
    message: str
    level: str = "info"  # info, warning, error, urgent


class NotificationService(ABC):
    """Abstract interface for sending notifications."""

    @abstractmethod
    def send(self, notification: Notification) -> None:
        """Send a notification."""
        ...


class MockNotificationService(NotificationService):
    """In-memory notification service for testing/dev."""

    def __init__(self) -> None:
        self.sent: list[Notification] = []

    def send(self, notification: Notification) -> None:
        self.sent.append(notification)
        # For debug visibility
        # print(f"[NOTIFY] To: {notification.recipient} | {notification.subject}")

    def clear(self) -> None:
        self.sent.clear()
