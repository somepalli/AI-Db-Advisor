"""Regression test: NotificationService must construct without AttributeError.

This guards against the SMTP/Slack settings on `Settings` (config.py) drifting away
from the attributes `NotificationService.__init__` reads.
"""

import pytest

from backend.services.notification_service import NotificationService


@pytest.mark.unit
def test_notification_service_constructs():
    service = NotificationService()
    # All channel-config attributes must be present (sourced from Settings).
    for attr in (
        "smtp_host",
        "smtp_port",
        "smtp_username",
        "smtp_password",
        "email_from",
        "email_to",
        "slack_webhook_url",
    ):
        assert hasattr(service, attr), f"NotificationService missing {attr}"
