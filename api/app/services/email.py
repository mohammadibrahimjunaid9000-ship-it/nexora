"""
Nexora API - Email Service
Provides an email notification abstraction for password recovery and account alerts.
Development and testing safe: captures notifications in-memory and logs only safe metadata.
Never logs tokens, passwords, or credentials.
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timezone

logger = logging.getLogger("nexora.api.email")


class EmailService:
    """
    Email notification service abstraction.
    In development and testing, records messages in-memory and emits safe log entries.
    Designed for seamless production provider integration without modifying route logic.
    """

    def __init__(self) -> None:
        self.sent_messages: List[Dict[str, Any]] = []

    def send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_token: str
    ) -> bool:
        """
        Dispatches password reset instructions.
        Logs only safe metadata (notification type, recipient email in non-prod).
        NEVER logs reset tokens, reset URLs containing tokens, passwords, or secrets.
        Stores the notification record in memory for test verification.
        """
        logger.info(f"Password reset notification requested for recipient: {to_email}")

        message_record = {
            "type": "password_reset",
            "to_email": to_email,
            "user_name": user_name,
            "reset_token": reset_token,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.sent_messages.append(message_record)
        return True

    def clear(self) -> None:
        """Clears in-memory sent messages (useful between test runs)."""
        self.sent_messages.clear()


# Singleton accessor
_email_service_instance: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """FastAPI dependency provider / singleton accessor for EmailService."""
    global _email_service_instance
    if _email_service_instance is None:
        _email_service_instance = EmailService()
    return _email_service_instance
