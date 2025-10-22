import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from app.core.config import SMTP_FROM_NAME, SMTP_FROM_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD


def send_email(to: str, subject: str, html: str, text: str | None = None):
    """
    Send transactional email via Brevo SMTP.
    Uses TLS on port 587 and an SMTP key (NOT API key).
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM_EMAIL))
    msg["To"] = to

    if text:
        msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, int(SMTP_PORT)) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.sendmail(SMTP_FROM_EMAIL, [to], msg.as_string())
