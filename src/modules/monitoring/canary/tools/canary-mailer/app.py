#!/usr/bin/env python3
import os
import smtplib
import sys
from datetime import UTC, datetime
from email.message import EmailMessage


def env(name, default=None):
    value = os.environ.get(name)
    if value is not None and value != "":
        return value
    return default


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv

    if len(argv) != 4:
        print(f"usage: {os.path.basename(argv[0])} EVENT_PATH EVENT_MASK EVENT_PID", file=sys.stderr)
        return 2

    event_path, event_mask, event_pid = argv[1], argv[2], argv[3]

    mail_to = env("FS_TRACKER_MAIL_TO") or env("MAIL_TO")
    mail_from = env("FS_TRACKER_MAIL_FROM") or env("MAIL_FROM")
    subject = env("FS_TRACKER_MAIL_SUBJECT") or env("MAIL_SUBJECT") or "fs-tracker alert"
    smtp_host = env("FS_TRACKER_SMTP_HOST") or env("SMTP_HOST")
    smtp_port = env("FS_TRACKER_SMTP_PORT") or env("SMTP_PORT") or "587"
    smtp_user = env("FS_TRACKER_SMTP_USER") or env("SMTP_USER")
    smtp_password = env("FS_TRACKER_SMTP_PASSWORD") or env("SMTP_PASSWORD")
    use_tls = (env("FS_TRACKER_SMTP_TLS") or env("SMTP_TLS") or "true").lower() in {"1", "true", "yes", "on"}

    if not mail_to:
        print("error: MAIL_TO or FS_TRACKER_MAIL_TO is not set", file=sys.stderr)
        return 2
    if not smtp_host:
        print("error: SMTP_HOST or FS_TRACKER_SMTP_HOST is not set", file=sys.stderr)
        return 2
    if not mail_from:
        mail_from = f"fs-tracker@{os.uname().nodename}"

    msg = EmailMessage()
    msg["To"] = mail_to
    msg["From"] = mail_from
    msg["Subject"] = subject
    body = (
        f"Event path: {event_path}\n"
        f"Event mask: {event_mask}\n"
        f"Process PID: {event_pid}\n"
        f"Hostname: {os.uname().nodename}\n"
        f"Timestamp: {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
    )
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, int(smtp_port), timeout=10) as server:
            if use_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except Exception as exc:  # pragma: no cover - runtime operation only
        print(f"error: could not send mail: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
