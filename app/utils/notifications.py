"""
Notification delivery for alerting.

Sends alert messages to the channels configured in settings:
- A generic JSON webhook (POST of a structured payload)
- A Slack incoming webhook (POST of {"text": ...})

Delivery is best-effort: each channel is attempted independently, failures are
logged and reported in the return value rather than raised, so one broken
channel never blocks the others. If no channel is configured, the notifier is
disabled and callers can detect that via ``is_enabled()``.
"""

import logging
from typing import Dict, List, Optional

import requests

from app.config import settings

logger = logging.getLogger(__name__)

# Severity ordering for threshold comparisons (higher = more severe)
SEVERITY_ORDER = {
    'info': 0,
    'low': 1,
    'medium': 2,
    'high': 3,
    'critical': 4,
}


def severity_at_least(severity: str, threshold: str) -> bool:
    """Return True if ``severity`` is at least as severe as ``threshold``."""
    s = SEVERITY_ORDER.get((severity or '').lower(), 0)
    t = SEVERITY_ORDER.get((threshold or '').lower(), 0)
    return s >= t


class Notifier:
    """Delivers alert notifications to configured channels."""

    def __init__(self):
        self.webhook_url = settings.alert_webhook_url
        self.slack_webhook_url = settings.alert_slack_webhook_url
        self.timeout = settings.alert_delivery_timeout

    def is_enabled(self) -> bool:
        """True if notifications are turned on and at least one channel exists."""
        return bool(
            settings.feature_notifications_enabled
            and (self.webhook_url or self.slack_webhook_url)
        )

    def send(self, title: str, text: str, payload: Optional[Dict] = None) -> Dict:
        """
        Send an alert to all configured channels.

        Args:
            title: Short alert title (used as Slack heading)
            text: Human-readable alert body (plain text)
            payload: Optional structured data included in the generic webhook

        Returns:
            Dict summarising delivery: {'delivered': [...], 'failed': [...],
            'skipped': bool}
        """
        if not self.is_enabled():
            logger.info("Notifications disabled or no channel configured; skipping delivery")
            return {'delivered': [], 'failed': [], 'skipped': True}

        delivered: List[str] = []
        failed: List[str] = []

        if self.webhook_url:
            body = {'title': title, 'text': text}
            if payload:
                body['data'] = payload
            if self._post('webhook', self.webhook_url, body):
                delivered.append('webhook')
            else:
                failed.append('webhook')

        if self.slack_webhook_url:
            slack_body = {'text': f"*{title}*\n{text}"}
            if self._post('slack', self.slack_webhook_url, slack_body):
                delivered.append('slack')
            else:
                failed.append('slack')

        return {'delivered': delivered, 'failed': failed, 'skipped': False}

    def _post(self, channel: str, url: str, body: Dict) -> bool:
        """POST a JSON body to a webhook, returning success as a bool."""
        try:
            resp = requests.post(url, json=body, timeout=self.timeout)
            if 200 <= resp.status_code < 300:
                return True
            logger.warning(f"Notification via {channel} returned HTTP {resp.status_code}")
            return False
        except requests.RequestException as e:
            logger.warning(f"Notification via {channel} failed: {e}")
            return False
