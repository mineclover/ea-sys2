"""Tests for notification_service — ABC + Logging + Mock implementations."""

from __future__ import annotations

import logging

from ea_kernel.notification_service import (
    LoggingNotificationService,
    MockNotificationService,
    Notification,
)


class TestLoggingNotificationService:
    """Tests for LoggingNotificationService."""

    def test_send_info(self, caplog) -> None:
        """Info-level notification logs at INFO."""
        svc = LoggingNotificationService(logger_name="test.notifications")
        note = Notification(
            recipient="role:reviewer",
            subject="Rule Submitted: r1",
            message="Please review.",
        )

        with caplog.at_level(logging.DEBUG, logger="test.notifications"):
            svc.send(note)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.INFO
        assert "role:reviewer" in caplog.records[0].message
        assert "Rule Submitted: r1" in caplog.records[0].message

    def test_send_warning(self, caplog) -> None:
        """Warning-level notification logs at WARNING."""
        svc = LoggingNotificationService(logger_name="test.notifications")
        note = Notification(
            recipient="admin",
            subject="Impact Alert",
            message="High severity detected.",
            level="warning",
        )

        with caplog.at_level(logging.DEBUG, logger="test.notifications"):
            svc.send(note)

        assert caplog.records[0].levelno == logging.WARNING

    def test_send_error(self, caplog) -> None:
        """Error-level notification logs at ERROR."""
        svc = LoggingNotificationService(logger_name="test.notifications")
        note = Notification(
            recipient="admin",
            subject="Rule Not Found",
            message="Asset missing.",
            level="error",
        )

        with caplog.at_level(logging.DEBUG, logger="test.notifications"):
            svc.send(note)

        assert caplog.records[0].levelno == logging.ERROR

    def test_send_urgent(self, caplog) -> None:
        """Urgent-level notification logs at CRITICAL."""
        svc = LoggingNotificationService(logger_name="test.notifications")
        note = Notification(
            recipient="all",
            subject="System Down",
            message="Immediate action required.",
            level="urgent",
        )

        with caplog.at_level(logging.DEBUG, logger="test.notifications"):
            svc.send(note)

        assert caplog.records[0].levelno == logging.CRITICAL

    def test_send_success_maps_to_info(self, caplog) -> None:
        """Success level maps to INFO."""
        svc = LoggingNotificationService(logger_name="test.notifications")
        note = Notification(
            recipient="human:alice",
            subject="Rule Approved",
            message="Done.",
            level="success",
        )

        with caplog.at_level(logging.DEBUG, logger="test.notifications"):
            svc.send(note)

        assert caplog.records[0].levelno == logging.INFO

    def test_unknown_level_defaults_to_info(self, caplog) -> None:
        """Unknown level defaults to INFO."""
        svc = LoggingNotificationService(logger_name="test.notifications")
        note = Notification(
            recipient="admin",
            subject="Test",
            message="Test.",
            level="unknown",
        )

        with caplog.at_level(logging.DEBUG, logger="test.notifications"):
            svc.send(note)

        assert caplog.records[0].levelno == logging.INFO

    def test_custom_logger_name(self, caplog) -> None:
        """Custom logger name is used."""
        svc = LoggingNotificationService(logger_name="custom.logger")
        note = Notification(recipient="x", subject="y", message="z")

        with caplog.at_level(logging.DEBUG, logger="custom.logger"):
            svc.send(note)

        assert caplog.records[0].name == "custom.logger"


class TestMockNotificationService:
    """Tests for MockNotificationService."""

    def test_send_collects(self) -> None:
        svc = MockNotificationService()
        note = Notification(recipient="a", subject="b", message="c")
        svc.send(note)
        assert len(svc.sent) == 1
        assert svc.sent[0] is note

    def test_clear(self) -> None:
        svc = MockNotificationService()
        svc.send(Notification(recipient="a", subject="b", message="c"))
        svc.clear()
        assert len(svc.sent) == 0
