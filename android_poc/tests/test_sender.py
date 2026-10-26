import smtplib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stk import sender


def _smtp_config(security: str) -> dict:
    return {
        "server": " smtp.example.com ",
        "port": "465" if security == "ssl" else "587",
        "security": security,
        "username": " me@example.com ",
        "password": "secret",
    }


class BuildMessageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _attachment_type(self, name: str) -> str:
        path = self.dir / name
        path.write_bytes(b"data")
        msg = sender.build_message("书名", "a@example.com", "b@kindle.com", path)
        part = next(msg.iter_attachments())
        self.assertEqual(part.get_filename(), name)
        self.assertEqual(part.get_payload(decode=True), b"data")
        return part.get_content_type()

    def test_epub_mime(self) -> None:
        self.assertEqual(self._attachment_type("书.epub"), "application/epub+zip")

    def test_pdf_mime(self) -> None:
        self.assertEqual(self._attachment_type("a.pdf"), "application/pdf")

    def test_text_maintype_not_forced_to_application(self) -> None:
        self.assertEqual(self._attachment_type("a.md"), "text/markdown")

    def test_unknown_ext_falls_back_to_octet_stream(self) -> None:
        self.assertEqual(self._attachment_type("a.unknownext"), "application/octet-stream")

    def test_headers(self) -> None:
        path = self.dir / "a.epub"
        path.write_bytes(b"x")
        msg = sender.build_message("中文书名", "a@example.com", "b@kindle.com", path)
        self.assertEqual(msg["Subject"], "中文书名")
        self.assertEqual(msg["To"], "b@kindle.com")


class SendViaSmtpTest(unittest.TestCase):
    def setUp(self) -> None:
        self.message = mock.sentinel.message

    @mock.patch("smtplib.SMTP")
    @mock.patch("smtplib.SMTP_SSL")
    def test_ssl_branch(self, smtp_ssl, smtp_plain) -> None:
        client = smtp_ssl.return_value
        sender.send_via_smtp(_smtp_config("ssl"), self.message)
        args, kwargs = smtp_ssl.call_args
        self.assertEqual(args, ("smtp.example.com", 465))
        self.assertIsNotNone(kwargs.get("context"))
        smtp_plain.assert_not_called()
        client.starttls.assert_not_called()
        client.login.assert_called_once_with("me@example.com", "secret")
        client.send_message.assert_called_once_with(self.message)
        client.quit.assert_called_once()

    @mock.patch("smtplib.SMTP_SSL")
    @mock.patch("smtplib.SMTP")
    def test_starttls_branch(self, smtp_plain, smtp_ssl) -> None:
        client = smtp_plain.return_value
        sender.send_via_smtp(_smtp_config("starttls"), self.message)
        smtp_ssl.assert_not_called()
        self.assertEqual(smtp_plain.call_args[0], ("smtp.example.com", 587))
        self.assertIsNotNone(client.starttls.call_args.kwargs.get("context"))
        client.login.assert_called_once()
        client.send_message.assert_called_once_with(self.message)

    def test_plain_rejected(self) -> None:
        with self.assertRaises(ValueError):
            sender.send_via_smtp(_smtp_config("plain"), self.message)

    @mock.patch("smtplib.SMTP_SSL")
    def test_login_error_not_masked_by_quit(self, smtp_ssl) -> None:
        client = smtp_ssl.return_value
        client.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")
        client.quit.side_effect = smtplib.SMTPServerDisconnected("gone")
        with self.assertRaises(smtplib.SMTPAuthenticationError):
            sender.send_via_smtp(_smtp_config("ssl"), self.message)
        client.close.assert_called_once()
        client.send_message.assert_not_called()

    @mock.patch("smtplib.SMTP_SSL")
    def test_send_book_uses_username_as_from(self, smtp_ssl) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.epub"
            path.write_bytes(b"x")
            sender.send_book(_smtp_config("ssl"), " me@kindle.com ", "标题", path)
        msg = smtp_ssl.return_value.send_message.call_args[0][0]
        self.assertEqual(msg["From"], "me@example.com")
        self.assertEqual(msg["To"], "me@kindle.com")
        self.assertEqual(msg["Subject"], "标题")


if __name__ == "__main__":
    unittest.main()
