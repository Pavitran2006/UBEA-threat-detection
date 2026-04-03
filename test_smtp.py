import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

def test_smtp():
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", os.getenv("EMAIL_USER", ""))
    SMTP_PASS = os.getenv("SMTP_PASS", os.getenv("EMAIL_PASSWORD", ""))
    SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or os.getenv("EMAIL_USER", ""))

    print(f"SMTP Configuration:")
    print(f"Host: {SMTP_HOST}")
    print(f"Port: {SMTP_PORT}")
    print(f"User: {SMTP_USER}")
    print(f"From: {SMTP_FROM}")
    # Don't print pass in logs
    
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        print("Error: Missing SMTP configuration in .env")
        return

    try:
        print("\nAttempting to connect to SMTP server...")
        message = EmailMessage()
        message["From"] = SMTP_FROM
        message["To"] = SMTP_USER # Send test to self
        message["Subject"] = "UEBA Test Email"
        message.set_content("This is a test email from the UEBA application.")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.set_debuglevel(1)  # Enable debug output
            server.ehlo()
            print("EHLO successful")
            server.starttls()
            print("STARTTLS successful")
            server.login(SMTP_USER, SMTP_PASS)
            print("Login successful")
            server.send_message(message)
            print("Message sent successfully!")
            
    except Exception as e:
        print(f"\nSMTP Error: {type(e).__name__}")
        print(str(e))

if __name__ == "__main__":
    test_smtp()
