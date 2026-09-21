"""Outbound email utilities for the password-reset OTP flow.

Uses only the Python standard library (``smtplib`` + ``email``) so no extra
dependency is required. When no SMTP host is configured the OTP is written to
the log instead of being emailed -- acceptable for development and test
environments only; production deployments must set ``SMTP_HOST``.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)

RESET_EMAIL_SUBJECT = "Your Dynamic Data Entry Platform password reset code"
RESET_EMAIL_BODY = (
    "Your password reset code for Dynamic Data Entry Platform is:\n\n"
    "        {otp}\n\n"
    "Enter this code to set a new password. It expires in {expire_minutes} "
    "minutes. If you did not request a password reset, you can ignore this "
    "email."
)


def send_password_reset_otp_email(to_email: str, otp: str) -> None:
    """Deliver a 6-digit password-reset OTP, or log it when mail is off.

    Fails open: even if SMTP is unavailable the flow keeps the generic
    "we sent a code" response so an attacker cannot distinguish a real from a
    fake email through timing or error behavior.
    """
    settings = get_settings()

    if not settings.smtp_host:
        logger.warning(
            "SMTP is not configured (%s); password-reset OTP for %s will not "
            "be emailed. OTP: %s",
            settings.environment,
            to_email,
            otp,
        )
        return

    message = EmailMessage()
    message["Subject"] = RESET_EMAIL_SUBJECT
    message["From"] = str(settings.emails_from_email or "no-reply@localhost")
    message["To"] = to_email
    message.set_content(
        RESET_EMAIL_BODY.format(
            otp=otp,
            expire_minutes=settings.password_reset_otp_expire_minutes,
        )
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password or "")
            server.send_message(message)
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send password-reset OTP email to %s", to_email)