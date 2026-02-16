"""Notification Service — Governance notification interface (Phase 5)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

_LEVEL_MAP: dict[str, int] = {
    "info": logging.INFO,
    "success": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "urgent": logging.CRITICAL,
}


@dataclass(frozen=True)
class Notification:
    recipient: str
    subject: str
    message: str
    level: str = "info"  # info, success, warning, error, urgent


class NotificationService(ABC):
    """Abstract interface for sending notifications."""

    @abstractmethod
    def send(self, notification: Notification) -> None:
        """Send a notification."""
        ...


class LoggingNotificationService(NotificationService):
    """Notification service that emits to Python's logging framework.

    Each notification is logged at the appropriate level (info/warning/error/critical)
    with structured fields (recipient, subject, message).  This is the default
    production implementation — lightweight, zero-dependency, easily routed via
    standard logging handlers (file, syslog, cloud, etc.).
    """

    def __init__(self, *, logger_name: str = "ea_kernel.notifications") -> None:
        self._logger = logging.getLogger(logger_name)

    def send(self, notification: Notification) -> None:
        log_level = _LEVEL_MAP.get(notification.level, logging.INFO)
        self._logger.log(
            log_level,
            "[%s] %s — %s",
            notification.recipient,
            notification.subject,
            notification.message,
        )


class MockNotificationService(NotificationService):
    """In-memory notification service for testing/dev."""

    def __init__(self) -> None:
        self.sent: list[Notification] = []

    def send(self, notification: Notification) -> None:
        self.sent.append(notification)

    def clear(self) -> None:
        self.sent.clear()
