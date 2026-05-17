"""Slack webhook integration service"""

import asyncio
import requests
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from policy_engine.models.alert import Alert, AlertSeverity

logger = logging.getLogger(__name__)


def _running_loop() -> Optional[asyncio.AbstractEventLoop]:
    """Return the running event loop, or ``None`` if called from sync context."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


class SlackService:
    """Service for sending alerts to Slack via webhooks"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack service
        
        Args:
            webhook_url: Default Slack webhook URL
        """
        self.default_webhook_url = webhook_url
        self.retry_attempts = 3
        self.retry_delay_seconds = 1
    
    def send_alert(
        self,
        alert: Alert,
        agent_name: Optional[str] = None,
        policy_violated: Optional[str] = None,
        action_attempted: Optional[str] = None,
        webhook_url: Optional[str] = None
    ) -> bool:
        """
        Send an alert to Slack
        
        Args:
            alert: Alert object to send
            agent_name: Name of the agent (optional, falls back to agent_id)
            policy_violated: Name of the policy that was violated
            action_attempted: Description of the action attempted
            webhook_url: Specific webhook URL (overrides default)
            
        Returns:
            True if message was sent successfully
        """
        # Determine webhook URL to use
        target_webhook = webhook_url or self.default_webhook_url
        
        if not target_webhook:
            logger.error("No Slack webhook URL configured")
            return False
        
        # Format the Slack message
        message = self._format_message(
            alert=alert,
            agent_name=agent_name,
            policy_violated=policy_violated,
            action_attempted=action_attempted
        )

        # If called from inside an asyncio event loop (e.g. the FastAPI policy
        # check handler), offload the blocking ``requests`` call onto the
        # default executor so it never stalls the loop. The caller treats this
        # as fire-and-forget (see policy_check.py:199), so returning True
        # immediately preserves the historical contract.
        loop = _running_loop()
        if loop is not None:
            alert_id = alert.id
            alert_type = alert.alert_type
            loop.run_in_executor(
                None,
                self._perform_send,
                target_webhook,
                message,
                alert_id,
                alert_type,
            )
            return True

        return self._perform_send(target_webhook, message, alert.id, alert.alert_type)

    def _perform_send(
        self,
        target_webhook: str,
        message: Dict[str, Any],
        alert_id: str,
        alert_type: str,
    ) -> bool:
        """Synchronous network worker (called inline or via executor)."""
        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(
                    target_webhook,
                    json=message,
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )

                if response.status_code == 200:
                    logger.info(
                        f"Slack alert sent successfully: alert_id={alert_id}, "
                        f"type={alert_type}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Slack webhook returned {response.status_code}: {response.text}"
                    )

            except requests.exceptions.RequestException as e:
                logger.error(
                    f"Slack webhook request failed (attempt {attempt + 1}/{self.retry_attempts}): {str(e)}"
                )

                if attempt < self.retry_attempts - 1:
                    import time
                    time.sleep(self.retry_delay_seconds * (attempt + 1))  # Exponential backoff

        logger.error(f"Failed to send Slack alert after {self.retry_attempts} attempts")
        return False
    
    def _format_message(
        self,
        alert: Alert,
        agent_name: Optional[str] = None,
        policy_violated: Optional[str] = None,
        action_attempted: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format alert as Slack block message
        
        Args:
            alert: Alert object
            agent_name: Name of the agent
            policy_violated: Policy that was violated
            action_attempted: Action that was attempted
            
        Returns:
            Slack message payload
        """
        # Determine emoji and color based on severity
        emoji_map = {
            AlertSeverity.LOW: ":information_source:",
            AlertSeverity.MEDIUM: ":warning:",
            AlertSeverity.HIGH: ":rotating_light:",
            AlertSeverity.CRITICAL: ":sos:"
        }
        
        color_map = {
            AlertSeverity.LOW: "#36a64f",  # Green
            AlertSeverity.MEDIUM: "#ff9900",  # Orange
            AlertSeverity.HIGH: "#ff0000",  # Red
            AlertSeverity.CRITICAL: "#8B0000"  # Dark red
        }
        
        severity = AlertSeverity(alert.severity)
        emoji = emoji_map.get(severity, ":warning:")
        color = color_map.get(severity, "#ff9900")
        
        # Format timestamp
        timestamp_str = alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Build alert title
        title = f"{emoji} {alert.alert_type.replace('_', ' ').title()}"
        
        # Build fields
        fields = [
            {
                "title": "Severity",
                "value": alert.severity.upper(),
                "short": True
            },
            {
                "title": "Agent",
                "value": agent_name or alert.agent_id,
                "short": True
            },
            {
                "title": "Timestamp",
                "value": timestamp_str,
                "short": True
            }
        ]
        
        if action_attempted:
            fields.append({
                "title": "Action Attempted",
                "value": action_attempted,
                "short": False
            })
        
        if policy_violated:
            fields.append({
                "title": "Policy Violated",
                "value": policy_violated,
                "short": False
            })
        
        # Add audit log link if available
        if alert.audit_log_id:
            fields.append({
                "title": "Audit Log ID",
                "value": f"`{alert.audit_log_id}`",
                "short": False
            })
        
        # Build Slack message with blocks
        message = {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": title,
                                "emoji": True
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": alert.description
                            }
                        },
                        {
                            "type": "section",
                            "fields": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"*{field['title']}*\n{field['value']}"
                                }
                                for field in fields
                            ]
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"Alert ID: `{alert.id}`"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        return message
    
    def send_test_message(self, webhook_url: Optional[str] = None) -> bool:
        """
        Send a test message to verify Slack integration
        
        Args:
            webhook_url: Webhook URL to test (uses default if not provided)
            
        Returns:
            True if test message sent successfully
        """
        target_webhook = webhook_url or self.default_webhook_url
        
        if not target_webhook:
            logger.error("No webhook URL provided for test")
            return False
        
        test_message = {
            "text": ":white_check_mark: Sentinel AI Alert System - Test Message",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Sentinel AI Alert System*\n\nThis is a test message to verify your Slack webhook integration is working correctly."
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Test sent at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(
                target_webhook,
                json=test_message,
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info("Slack test message sent successfully")
                return True
            else:
                logger.error(f"Slack test failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Slack test message failed: {str(e)}")
            return False


# Global Slack service instance (can be configured at runtime)
slack_service = SlackService()
