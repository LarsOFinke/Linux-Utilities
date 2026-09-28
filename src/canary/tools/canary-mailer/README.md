# Canary mailer

This small Python app is intended to be bundled with PyInstaller and used as the
`TRACK_ACTION` executable for a canary.

It accepts the same three positional arguments as the shell action scripts:

- event path
- raw fanotify mask
- originating PID

It reads mail configuration from environment variables:

- `FS_TRACKER_MAIL_TO` or `MAIL_TO`
- `FS_TRACKER_MAIL_FROM` or `MAIL_FROM`
- `FS_TRACKER_MAIL_SUBJECT` or `MAIL_SUBJECT`
- `FS_TRACKER_SMTP_HOST` or `SMTP_HOST`
- `FS_TRACKER_SMTP_PORT` or `SMTP_PORT` (default: 587)
- `FS_TRACKER_SMTP_USER` or `SMTP_USER`
- `FS_TRACKER_SMTP_PASSWORD` or `SMTP_PASSWORD`
- `FS_TRACKER_SMTP_TLS` or `SMTP_TLS` (default: true)

Example build:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pyinstaller --onefile app.py
```

The resulting executable can be used as the action for `fs-tracker`.
