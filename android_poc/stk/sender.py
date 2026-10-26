"""SMTP 发送，移植自桌面版 app/sender.py。

与桌面版的差异：
- MIME 主类型按实际类型拆分，不再写死 application。
- SSL/STARTTLS 显式使用带 CA 包的 SSLContext（Android 上 OpenSSL 找不到系统 CA 路径）。
- quit() 的异常不会覆盖登录失败等原始错误。
- 不限制附件大小，超限由邮箱服务商或 Amazon 拒收。
"""
from __future__ import annotations

import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

_MIME_OVERRIDES = {
    ".epub": "application/epub+zip",
    ".pdf": "application/pdf",
    ".mobi": "application/x-mobipocket-ebook",
    ".azw": "application/vnd.amazon.ebook",
    ".azw3": "application/vnd.amazon.ebook",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}

SMTP_TIMEOUT = 60


def guess_mime(path: Path) -> str:
    override = _MIME_OVERRIDES.get(path.suffix.lower())
    if override:
        return override
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def build_message(subject: str, from_addr: str, to_addr: str, attachment: Path) -> EmailMessage:
    attachment = Path(attachment)
    maintype, subtype = guess_mime(attachment).split("/", 1)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(subject)
    msg.add_attachment(
        attachment.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=attachment.name,
    )
    return msg


def send_via_smtp(smtp_config: dict, message: EmailMessage) -> None:
    server = str(smtp_config["server"]).strip()
    port = int(smtp_config["port"])
    username = str(smtp_config["username"]).strip()
    password = smtp_config["password"]
    security = smtp_config.get("security", "ssl")
    if security not in ("ssl", "starttls"):
        raise ValueError(f"不支持的加密方式: {security}")

    context = ssl_context()
    if security == "ssl":
        client: smtplib.SMTP = smtplib.SMTP_SSL(server, port, timeout=SMTP_TIMEOUT, context=context)
    else:
        client = smtplib.SMTP(server, port, timeout=SMTP_TIMEOUT)
    try:
        client.ehlo()
        if security == "starttls":
            client.starttls(context=context)
            client.ehlo()
        client.login(username, password)
        client.send_message(message)
    finally:
        try:
            client.quit()
        except Exception:
            # 连接已断开或服务器拒绝时 quit 也会失败，不能覆盖原始错误
            client.close()


def send_book(smtp_config: dict, target_email: str, subject: str, attachment: Path) -> None:
    message = build_message(
        subject, str(smtp_config["username"]).strip(), target_email.strip(), attachment
    )
    send_via_smtp(smtp_config, message)
