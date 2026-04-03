from __future__ import annotations

from datetime import datetime, timedelta, timezone

from email.message import EmailMessage
import smtplib
import random

from ..config import OTP_EXPIRE_MINUTES, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM


def generate_otp(length: int = 6) -> str:
    return str(random.randint(100000, 999999))


def otp_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)


def format_otp_message(otp: str, channel: str) -> str:
    channel_label = "Email" if channel == "email" else "Phone"
    return f"{channel_label} OTP: {otp} (valid for {OTP_EXPIRE_MINUTES} minutes)"


async def send_email_otp(email: str, otp: str) -> None:
    if not SMTP_HOST or not SMTP_FROM or not SMTP_USER or not SMTP_PASS:
        print(f"[OTP] Email to {email}: {otp} (SMTP not configured)")
        return

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = email
    message["Subject"] = "UEBA Security Verification Code"
    message.set_content(
        "Hello,\n\n"
        f"Your verification code is: {otp}\n"
        f"This code will expire in {OTP_EXPIRE_MINUTES} minutes.\n\n"
        "If you did not request this, please ignore this message.\n\n"
        "UEBA Security Team"
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(message)
    except Exception as exc:
        print("OTP Email Error:", exc)
        raise


def send_test_email(to_email: str | None = None) -> None:
    recipient = to_email or SMTP_FROM
    if not recipient:
        raise RuntimeError("Missing recipient email")

    if not SMTP_HOST or not SMTP_FROM or not SMTP_USER or not SMTP_PASS:
        raise RuntimeError("SMTP not configured (missing SMTP_HOST/SMTP_FROM/SMTP_USER/SMTP_PASS)")

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = recipient
    message["Subject"] = "UEBA OTP Test"
    message.set_content(
        "UEBA SMTP test email.\n\n"
        "If you received this message, SMTP is configured correctly.\n"
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(message)
