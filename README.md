# Send to Kindle

[English](README.md) | [简体中文](README.zh-CN.md)

A lightweight Windows tool that sends your local ebooks straight to your Kindle library — no USB cable, no Calibre, no manual email composing.

## What problem does it solve

Getting books onto a Kindle is usually a chore: convert the format somewhere, dig up your `@kindle.com` address, open a mail client, attach the file, remember the rules — for every single book.

With this tool it takes three steps: **pick files → hit send**. Everything else is handled for you:

- Unrecognized formats (AZW, MOBI, DOCX, Markdown, PDF, TXT, HTML...) are converted to EPUB automatically
- Files that are already EPUB are sent as-is, no double conversion
- One email per book, file attached, book title as the subject
- Your mailbox settings are saved locally, so you only configure them once

## Quick start

### 1. Install and run

Requires Python 3.11+:

```bash
pip install -r requirements.txt
python main.py
```

### 2. Get an email authorization code

Most email providers **do not allow sending with your login password** — you need to generate a dedicated *authorization code* first. The steps are similar everywhere:

1. Log in to your mailbox on the web
2. Open **Settings** and look for the **Account** or **POP3 / IMAP / SMTP** section
3. Turn **SMTP service** on (an SMS check may be required)
4. **Generate the authorization code** — some providers call it "client password" or "app password"
5. Copy it into the **Password** field of this tool (it is *not* your login password)

Quick reference for common providers:

| Provider | SMTP server | Port / encryption | Where to get the code |
|---|---|---|---|
| QQ Mail | `smtp.qq.com` | 465 / SSL | Settings → Account → enable SMTP → generate code |
| 163 / 126 / yeah | `smtp.163.com` (`smtp.yeah.net` for yeah) | 465 / SSL | Settings → POP3/SMTP → enable → client authorization password |
| Gmail | `smtp.gmail.com` | 465 / SSL | Turn on 2-Step Verification, then create an "App Password" |
| Outlook / Hotmail | `smtp.office365.com` | 587 / STARTTLS | Microsoft account → Security → App password |

### 3. Fill in the settings

Click **Settings** on the main window, enter the server, port, encryption mode, account, and authorization code from the table above. Then fill in the **target email** — your Kindle address, which looks like `xxx@kindle.com`. Save, and the configuration is reused the next time you launch.

> Where do I find my Kindle address? On Amazon: **Manage Your Content and Devices → Settings → Personal Document Settings** — your Kindle email addresses are listed there.

### 4. Add files and send

- Click **Add files** — you can select many books at once
- Select unwanted entries and click **Remove**
- Click **Convert & Send** — the status bar shows live progress, and a summary dialog reports how many books went out and why any failed

## Supported formats

`epub` (sent directly), `azw`, `azw3`, `mobi`, `prc`, `docx`, `html`, `txt`, `markdown`, `pdf`, `odt`, `fb2`, `rtf`

## How it works

```
pick files → check format → convert to EPUB → send from your mailbox → Kindle stores it
             already EPUB   built-in tools    one email per book
             → skip
```

The poppler tools required for PDF conversion are bundled in this repository — **no extra setup needed**.

## Good to know

- **Keep your authorization code private**: settings are stored in a local `config.json` (already git-ignored) for personal use on your own machine — don't share that file
- **Watch the attachment size**: most providers cap attachments at 25–50 MB; oversized PDFs may fail
- **One failure doesn't stop the batch**: if a book fails to convert or send, the rest keep going, and all failures are reported at the end

## License

Free to use and modify for personal projects.
