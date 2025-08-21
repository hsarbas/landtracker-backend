import os

# Optional: Twilio config
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")  # e.g. +15005550006

_twilio_client = None
if TWILIO_SID and TWILIO_TOKEN:
    try:
        from twilio.rest import Client  # type: ignore
        _twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)
    except Exception:
        _twilio_client = None


def send_sms(to: str, body: str) -> None:
    if _twilio_client and TWILIO_FROM:
        _twilio_client.messages.create(to=to, from_=TWILIO_FROM, body=body)
    else:
        # Fallback: just print to console
        print(f"[SMS][FAKE] To {to}: {body}")
