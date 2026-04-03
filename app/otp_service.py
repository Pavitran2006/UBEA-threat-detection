from __future__ import annotations

from email.message import EmailMessage
import os
import random
import smtplib
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "5"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "3"))
OTP_RATE_LIMIT_WINDOW_MINUTES = int(os.getenv("OTP_RATE_LIMIT_WINDOW_MINUTES", "10"))
OTP_RATE_LIMIT_MAX = int(os.getenv("OTP_RATE_LIMIT_MAX", "5"))

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", os.getenv("EMAIL_USER", ""))
SMTP_PASS = os.getenv("SMTP_PASS", os.getenv("EMAIL_PASSWORD", ""))
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or os.getenv("EMAIL_USER", ""))


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


def otp_expiry() -> datetime:
    return datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)


def send_email_otp(email: str, otp: str) -> None:
    subject = "UEBA Password Reset Code"
    content = (
        f"Hi,\n\n"
        f"Your password reset code is: {otp}\n\n"
        f"This code expires in {OTP_EXPIRE_MINUTES} minutes.\n\n"
        f"If you didn't request this, ignore this email.\n\n"
        f"UEBA Security Team"
    )
    send_email(email, subject, content)


def send_email(to_email: str, subject: str, content: str) -> None:
    # Always print the email to the console as a reliable fallback for dev/testing
    print(f"\n" + "="*50)
    print(f"[EMAIL SENDING] To: {to_email} | Subject: {subject}")
    print(f"Content:\n{content}")
    print("="*50 + "\n")

    if not SMTP_HOST or not SMTP_FROM or not SMTP_USER or not SMTP_PASS:
        print("[SMTP Error] SMTP environment variables are missing. Email not sent.")
        return

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(content)

    try:
        print(f"Attempting to send email to {to_email} via {SMTP_HOST}:{SMTP_PORT}...")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(message)
        print("[SMTP Success] Email sent successfully to " + to_email)
    except Exception as e:
        print(f"[SMTP Error] Failed to send email to {to_email}. Error: {type(e).__name__} - {str(e)}")

