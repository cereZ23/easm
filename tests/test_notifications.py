"""
Unit tests for notification severity thresholds and Notifier enable/skip logic.
"""

from unittest.mock import patch

from app.utils.notifications import severity_at_least, Notifier


class TestSeverityThreshold:
    def test_critical_meets_high(self):
        assert severity_at_least("critical", "high") is True

    def test_high_meets_high(self):
        assert severity_at_least("high", "high") is True

    def test_medium_below_high(self):
        assert severity_at_least("medium", "high") is False

    def test_unknown_severity_is_lowest(self):
        assert severity_at_least("bogus", "low") is False

    def test_case_insensitive(self):
        assert severity_at_least("CRITICAL", "High") is True


class TestNotifierEnablement:
    def test_disabled_when_feature_off(self):
        with patch("app.utils.notifications.settings") as s:
            s.feature_notifications_enabled = False
            s.alert_webhook_url = "https://example.com/hook"
            s.alert_slack_webhook_url = None
            s.alert_delivery_timeout = 10
            assert Notifier().is_enabled() is False

    def test_disabled_when_no_channel(self):
        with patch("app.utils.notifications.settings") as s:
            s.feature_notifications_enabled = True
            s.alert_webhook_url = None
            s.alert_slack_webhook_url = None
            s.alert_delivery_timeout = 10
            assert Notifier().is_enabled() is False

    def test_enabled_with_feature_and_channel(self):
        with patch("app.utils.notifications.settings") as s:
            s.feature_notifications_enabled = True
            s.alert_webhook_url = "https://example.com/hook"
            s.alert_slack_webhook_url = None
            s.alert_delivery_timeout = 10
            assert Notifier().is_enabled() is True

    def test_send_skips_when_disabled(self):
        with patch("app.utils.notifications.settings") as s:
            s.feature_notifications_enabled = False
            s.alert_webhook_url = None
            s.alert_slack_webhook_url = None
            s.alert_delivery_timeout = 10
            result = Notifier().send("title", "body")
            assert result["skipped"] is True
            assert result["delivered"] == []
