from __future__ import annotations

import mimetypes
from email.message import EmailMessage
from pathlib import Path
import smtplib

_MIME_OVERRIDES = {
    ".epub": "application/epub+zip",
    ".mobi": "application/x-mobipocket-ebook",
    ".azw": "application/vnd.amazon.ebook",
    ".azw3": "application/vnd.amazon.ebook",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


def _guess_mime(path: Path) -> str:
    override = _MIME_OVERRIDES.get(path.suffix.lower())
    if override:
        return override
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def build_message(
    subject: str, from_addr: str, to_addr: str, attachment: Path
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(subject)
    msg.add_attachment(
        attachment.read_bytes(),
        maintype="application",
        subtype=_guess_mime(attachment).split("/", 1)[1],
        filename=attachment.name,
    )
    return msg


def send_via_smtp(smtp_config: dict, to_addr: str, message: EmailMessage) -> None:
    server = smtp_config["server"].strip()
    port = int(smtp_config["port"])
    username = smtp_config["username"].strip()
    password = smtp_config["password"]
    security = smtp_config.get("security", "ssl")

    if security == "ssl":
        client: smtplib.SMTP = smtplib.SMTP_SSL(server, port, timeout=30)
    else:
        client = smtplib.SMTP(server, port, timeout=30)
    try:
        client.ehlo()
        if security == "starttls":
            client.starttls()
            client.ehlo()
        client.login(username, password)
        client.send_message(message)
    finally:
        client.quit()


def send_book(
    smtp_config: dict,
    target_email: str,
    subject: str,
    attachment: Path,
) -> None:
    message = build_message(subject, smtp_config["username"].strip(), target_email, attachment)
    send_via_smtp(smtp_config, target_email, message)
