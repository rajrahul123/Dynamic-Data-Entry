"""Outbound email utilities for the password-reset flow.

Uses only the Python standard library (``smtplib`` + ``email``) so no extra
dependency is required. When no SMTP host is configured the reset link is
written to the log instead of being emailed -- acceptable for development and
test environments only; production deployments must set ``SMTP_HOST``.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)

RESET_EMAIL_SUBJECT = "Reset your Dynamic Data Entry Platform password"
RESET_EMAIL_BODY = (
    "Someone requested a password reset for your account on "
    "Dynamic Data Entry Platform.\n\n"
    "Open the link below to choose a new password. It expires in "
    "{expire_minutes} minutes.\n\n{reset_link}\n\n"
    "If you did not request this, you can safely ignore this email."
)


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    """Deliver a password-reset email, or log the link when mail is off.

    Fails open: even if SMTP is unavailable the flow keeps the generic
    "we sent a link" response so an attacker cannot distinguish a real from a
    fake email through timing or error behavior.
    """
    settings = get_settings()

    if not settings.smtp_host:
        logger.warning(
            "SMTP is not configured (%s); password-reset link for %s will not "
            "be emailed. Reset link: %s",
            settings.environment,
            to_email,
            reset_link,
        )
        return

    message = EmailMessage()
    message["Subject"] = RESET_EMAIL_SUBJECT
    message["From"] = str(settings.emails_from_email or "no-reply@localhost")
    message["To"] = to_email
    message.set_content(
        RESET_EMAIL_BODY.format(
            expire_minutes=settings.password_reset_token_expire_minutes,
            reset_link=reset_link,
        )
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password or "")
            server.send_message(message)
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send password-reset email to %s", to_email)