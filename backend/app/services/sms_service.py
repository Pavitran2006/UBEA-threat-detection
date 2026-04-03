from __future__ import annotations

import base64
import httpx

from ..config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER


async def send_sms_otp(phone: str, otp: str) -> None:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_FROM_NUMBER:
        print(f"[OTP] SMS to {phone}: {otp} (Twilio not configured)")
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    auth = base64.b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "From": TWILIO_FROM_NUMBER,
        "To": phone,
        "Body": f"UEBA Security Verification Code: {otp} (valid for 5 minutes)",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, headers=headers, data=data)
        if resp.status_code >= 400:
            raise RuntimeError(f"Twilio error {resp.status_code}: {resp.text}")
