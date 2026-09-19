"""SMTP email notifications for detected competitor changes."""

import os
import smtplib
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()


class EmailNotConfigured(Exception):
    pass


def _settings():
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    to_addr = os.getenv("NOTIFY_EMAIL", user)
    return host, port, user, password, to_addr


def is_configured() -> bool:
    _, _, user, password, to_addr = _settings()
    return bool(user and password and to_addr)


def send_change_notification(product_label: str, url: str, changes: list) -> None:
    if not is_configured():
        raise EmailNotConfigured(
            "SMTP_USER / SMTP_PASSWORD / NOTIFY_EMAIL are not set in .env — skipping email."
        )

    host, port, user, password, to_addr = _settings()

    lines = [f"Change detected for {product_label}", f"URL: {url}", ""]
    for c in changes:
        lines.append(f"- {c['field'].title()}: '{c['old']}' -> '{c['new']}'")
    lines.append("")
    lines.append("A pre-filled observation has been created in the tracker for review.")
    body = "\n".join(lines)

    msg = MIMEText(body)
    msg["Subject"] = f"[Competitive Tracker] Change detected: {product_label}"
    msg["From"] = user
    msg["To"] = to_addr

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())
