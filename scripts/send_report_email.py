#!/usr/bin/env python3
import argparse
import mimetypes
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Optional


DEFAULT_TO = "240575148@qq.com"
DEFAULT_HOST = "smtp.gmail.com"
DEFAULT_PORT = 465
DEFAULT_PORTS = (465, 587)
BLOCKED_HTML_MARKERS = ("<style", "<script", "<head", "</head", "<!doctype")


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def read_optional_file(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")


def validate_email_html(html_text: str) -> None:
    lowered = html_text.lower()
    blocked = [marker for marker in BLOCKED_HTML_MARKERS if marker in lowered]
    if blocked:
        markers = ", ".join(blocked)
        raise SystemExit(
            "HTML email body contains webpage-only markup: "
            f"{markers}. Generate an email-safe inline HTML body instead."
        )


def parse_smtp_ports() -> list[int]:
    raw = os.environ.get("SMTP_PORTS")
    if raw:
        return [int(item.strip()) for item in raw.split(",") if item.strip()]
    if os.environ.get("SMTP_PORT"):
        return [int(os.environ["SMTP_PORT"])]
    return list(DEFAULT_PORTS)


def attach_file(message: EmailMessage, path: str) -> None:
    file_path = Path(path)
    content_type, _ = mimetypes.guess_type(file_path.name)
    if content_type:
        maintype, subtype = content_type.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"

    message.add_attachment(
        file_path.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=file_path.name,
    )


def build_message(args: argparse.Namespace) -> EmailMessage:
    sender = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or require_env("GMAIL_SMTP_USER")
    recipient = args.to or os.environ.get("A_SHARE_REPORT_TO") or DEFAULT_TO

    plain_text = read_optional_file(args.text_file) or args.text or "A股盘后验证雷达报告见邮件正文或附件。"
    html_text = read_optional_file(args.html_file)
    if html_text:
        validate_email_html(html_text)

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = args.subject
    message.set_content(plain_text)

    if html_text:
        message.add_alternative(html_text, subtype="html")

    for attachment in args.attach:
        attach_file(message, attachment)

    return message


def send_message(message: EmailMessage) -> None:
    host = os.environ.get("SMTP_HOST") or DEFAULT_HOST
    ports = parse_smtp_ports()
    user = os.environ.get("SMTP_USER") or os.environ.get("GMAIL_SMTP_USER") or require_env("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD") or require_env("SMTP_PASSWORD")

    context = ssl.create_default_context()
    errors: list[str] = []
    for port in ports:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
        try:
            server.ehlo()
            if port != 465:
                server.starttls(context=context)
                server.ehlo()
            server.login(user, password, initial_response_ok=False)
            server.send_message(message)
            return
        except smtplib.SMTPAuthenticationError as exc:
            errors.append(f"{port}: authentication failed {exc.smtp_code} {exc.smtp_error!r}")
        except smtplib.SMTPException as exc:
            errors.append(f"{port}: send failed {exc}")
        except OSError as exc:
            errors.append(f"{port}: network failed {exc}")
        finally:
            try:
                server.quit()
            except smtplib.SMTPException:
                pass

    raise SystemExit(
        "SMTP发送失败。已尝试端口 "
        + ", ".join(str(port) for port in ports)
        + "；错误："
        + " | ".join(errors)
        + "。如果使用 Gmail，请确认开启两步验证并使用 App Password，不要使用 Gmail 登录密码。"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send the A-share report by email.")
    parser.add_argument("--subject", required=True, help="Email subject.")
    parser.add_argument("--to", help="Recipient email address. Defaults to A_SHARE_REPORT_TO or 240575148@qq.com.")
    parser.add_argument("--text", help="Plain text email body.")
    parser.add_argument("--text-file", help="Path to a plain text email body.")
    parser.add_argument("--html-file", help="Path to an HTML email body.")
    parser.add_argument("--attach", action="append", default=[], help="File to attach. Can be repeated.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    message = build_message(args)
    send_message(message)
    print(f"Email sent to {message['To']}")


if __name__ == "__main__":
    main()
