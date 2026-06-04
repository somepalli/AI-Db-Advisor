"""
Notification service for sending alert notifications via multiple channels.

Supports:
- Email (SMTP)
- Slack (Incoming Webhooks)
"""

import logging
import smtplib
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime

from ..services.alert_engine import Alert
from ..config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Multi-channel notification service for alerts.

    Sends alert notifications via configured channels (Email, Slack).
    """

    def __init__(self):
        # Email configuration
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.email_from = settings.EMAIL_FROM or settings.SMTP_USERNAME
        self.email_to = settings.EMAIL_TO

        # Slack configuration
        self.slack_webhook_url = settings.SLACK_WEBHOOK_URL

        # Enable/disable channels based on configuration
        self.email_enabled = bool(self.smtp_username and self.smtp_password and self.email_to)
        self.slack_enabled = bool(self.slack_webhook_url)

        logger.info(f"Notification service initialized - Email: {self.email_enabled}, Slack: {self.slack_enabled}")

    async def send_alert_notification(self, alert: Alert):
        """
        Send notification for an alert via all enabled channels.

        Args:
            alert: The alert to send notification for
        """
        try:
            logger.info(f"Sending notification for alert: {alert.id} ({alert.title})")

            # Send via email if enabled
            if self.email_enabled:
                await self._send_email_notification(alert)

            # Send via Slack if enabled
            if self.slack_enabled:
                await self._send_slack_notification(alert)

            if not self.email_enabled and not self.slack_enabled:
                logger.warning("No notification channels enabled - skipping notification")

        except Exception as e:
            logger.error(f"Failed to send notification for alert {alert.id}: {e}", exc_info=True)

    async def _send_email_notification(self, alert: Alert):
        """Send email notification for an alert"""
        try:
            logger.info(f"Sending email notification for alert: {alert.id}")

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{alert.severity.upper()}] {alert.title}"
            msg["From"] = self.email_from
            msg["To"] = self.email_to
            msg["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

            # Create email body
            text_body = self._create_text_email_body(alert)
            html_body = self._create_html_email_body(alert)

            # Attach both plain text and HTML versions
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"✅ Email notification sent for alert {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}", exc_info=True)
            raise

    async def _send_slack_notification(self, alert: Alert):
        """Send Slack notification for an alert"""
        try:
            logger.info(f"Sending Slack notification for alert: {alert.id}")

            # Create Slack message payload
            payload = self._create_slack_payload(alert)

            # Send to Slack webhook
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.slack_webhook_url,
                    json=payload,
                    timeout=10.0
                )

                if response.status_code == 200:
                    logger.info(f"✅ Slack notification sent for alert {alert.id}")
                else:
                    logger.error(f"Slack notification failed: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}", exc_info=True)
            raise

    def _create_text_email_body(self, alert: Alert) -> str:
        """Create plain text email body"""
        ai_analysis = alert.metadata.get("ai_analysis", {}) if alert.metadata else {}

        body = f"""Database Alert Notification

Alert: {alert.title}
Severity: {alert.severity.upper()}
Datasource: {alert.datasource_id}
Status: {alert.status}

Message:
{alert.message}

Details:
- Current Value: {alert.metric_value}
- Threshold: {alert.threshold}
- Triggered At: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
"""

        # Add AI analysis if available
        if ai_analysis and not ai_analysis.get("error"):
            body += f"""
AI Analysis:

Root Cause:
{ai_analysis.get('root_cause', 'Not available')}

Risk Level: {ai_analysis.get('risk_level', 'unknown').upper()}

Immediate Actions:
"""
            for i, action in enumerate(ai_analysis.get('immediate_actions', []), 1):
                body += f"{i}. {action}\n"

            if ai_analysis.get('runbook_steps'):
                body += "\nRunbook Steps:\n"
                for i, step in enumerate(ai_analysis.get('runbook_steps', []), 1):
                    body += f"{i}. {step}\n"

        body += f"""
---
Alert ID: {alert.id}
View in Dashboard: http://localhost:8000/
"""

        return body

    def _create_html_email_body(self, alert: Alert) -> str:
        """Create HTML email body"""
        ai_analysis = alert.metadata.get("ai_analysis", {}) if alert.metadata else {}

        # Severity color
        severity_colors = {
            "critical": "#dc2626",
            "warning": "#f59e0b",
            "info": "#3b82f6"
        }
        severity_color = severity_colors.get(alert.severity, "#6b7280")

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: {severity_color}; color: white; padding: 15px; border-radius: 5px 5px 0 0; }}
        .content {{ background-color: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; border-radius: 0 0 5px 5px; }}
        .section {{ margin-bottom: 20px; }}
        .label {{ font-weight: bold; color: #374151; }}
        .value {{ color: #1f2937; }}
        .ai-section {{ background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 15px; margin-top: 15px; border-radius: 4px; }}
        .action-list {{ margin-left: 20px; }}
        .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">Database Alert: {alert.title}</h2>
        </div>
        <div class="content">
            <div class="section">
                <span class="label">Severity:</span>
                <span class="value" style="color: {severity_color}; font-weight: bold;">{alert.severity.upper()}</span>
            </div>
            <div class="section">
                <span class="label">Datasource:</span>
                <span class="value">{alert.datasource_id}</span>
            </div>
            <div class="section">
                <span class="label">Message:</span><br>
                <span class="value">{alert.message}</span>
            </div>
            <div class="section">
                <span class="label">Current Value:</span> <span class="value">{alert.metric_value}</span><br>
                <span class="label">Threshold:</span> <span class="value">{alert.threshold}</span>
            </div>
            <div class="section">
                <span class="label">Triggered At:</span>
                <span class="value">{alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</span>
            </div>
"""

        # Add AI analysis if available
        if ai_analysis and not ai_analysis.get("error"):
            html += f"""
            <div class="ai-section">
                <h3 style="margin-top: 0; color: #1e40af;">🤖 AI Analysis</h3>

                <div class="section">
                    <span class="label">Root Cause:</span><br>
                    <span class="value">{ai_analysis.get('root_cause', 'Not available')}</span>
                </div>

                <div class="section">
                    <span class="label">Risk Level:</span>
                    <span class="value" style="font-weight: bold;">{ai_analysis.get('risk_level', 'unknown').upper()}</span>
                </div>
"""

            if ai_analysis.get('immediate_actions'):
                html += """
                <div class="section">
                    <span class="label">Immediate Actions:</span>
                    <ol class="action-list">
"""
                for action in ai_analysis.get('immediate_actions', []):
                    html += f"<li>{action}</li>"
                html += """
                    </ol>
                </div>
"""

            if ai_analysis.get('runbook_steps'):
                html += """
                <div class="section">
                    <span class="label">Runbook Steps:</span>
                    <ol class="action-list">
"""
                for step in ai_analysis.get('runbook_steps', []):
                    html += f"<li>{step}</li>"
                html += """
                    </ol>
                </div>
"""

            html += """
            </div>
"""

        html += f"""
            <div class="footer">
                Alert ID: {alert.id}<br>
                <a href="http://localhost:8000/">View in Dashboard</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

        return html

    def _create_slack_payload(self, alert: Alert) -> dict:
        """Create Slack webhook payload"""
        ai_analysis = alert.metadata.get("ai_analysis", {}) if alert.metadata else {}

        # Severity emoji and color
        severity_emojis = {
            "critical": "🔴",
            "warning": "🟡",
            "info": "🔵"
        }
        severity_colors = {
            "critical": "danger",
            "warning": "warning",
            "info": "#3b82f6"
        }

        emoji = severity_emojis.get(alert.severity, "⚪")
        color = severity_colors.get(alert.severity, "#6b7280")

        # Build fields
        fields = [
            {
                "title": "Datasource",
                "value": alert.datasource_id,
                "short": True
            },
            {
                "title": "Severity",
                "value": alert.severity.upper(),
                "short": True
            },
            {
                "title": "Current Value",
                "value": str(alert.metric_value),
                "short": True
            },
            {
                "title": "Threshold",
                "value": str(alert.threshold),
                "short": True
            }
        ]

        # Add AI analysis fields if available
        if ai_analysis and not ai_analysis.get("error"):
            if ai_analysis.get('root_cause'):
                fields.append({
                    "title": "🤖 Root Cause",
                    "value": ai_analysis.get('root_cause'),
                    "short": False
                })

            if ai_analysis.get('immediate_actions'):
                actions_text = "\n".join([f"• {action}" for action in ai_analysis.get('immediate_actions', [])])
                fields.append({
                    "title": "⚡ Immediate Actions",
                    "value": actions_text,
                    "short": False
                })

        # Create attachment
        attachment = {
            "color": color,
            "title": f"{emoji} {alert.title}",
            "text": alert.message,
            "fields": fields,
            "footer": f"Alert ID: {alert.id}",
            "ts": int(alert.triggered_at.timestamp())
        }

        # Create payload
        payload = {
            "text": f"*Database Alert Triggered*",
            "attachments": [attachment]
        }

        return payload


# Singleton instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get or create the notification service singleton"""
    global _notification_service

    if _notification_service is None:
        _notification_service = NotificationService()

    return _notification_service
