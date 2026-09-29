#!/bin/sh
set -eu

[ "$#" -eq 3 ] || {
    printf 'usage: %s EVENT_PATH EVENT_MASK EVENT_PID\n' "$0" >&2
    exit 2
}

EVENT_PATH=$1
EVENT_MASK=$2
EVENT_PID=$3

MAIL_TO=${FS_TRACKER_MAIL_TO:-${MAIL_TO:-}}
MAIL_FROM=${FS_TRACKER_MAIL_FROM:-${MAIL_FROM:-}}
MAIL_SUBJECT=${FS_TRACKER_MAIL_SUBJECT:-${MAIL_SUBJECT:-fs-tracker event}}

if [ -z "$MAIL_TO" ]; then
    printf 'error: MAIL_TO or FS_TRACKER_MAIL_TO is not set\n' >&2
    exit 2
fi

if [ -z "$MAIL_FROM" ]; then
    HOST_NAME=$(hostname 2>/dev/null || printf 'localhost')
    MAIL_FROM="fs-tracker@${HOST_NAME}"
fi

BODY=$(cat <<EOF
Event path: $EVENT_PATH
Event mask: $EVENT_MASK
Process PID: $EVENT_PID
Host: $(hostname 2>/dev/null || printf 'unknown')
Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF
)

if command -v sendmail >/dev/null 2>&1; then
    {
        printf 'To: %s\n' "$MAIL_TO"
        printf 'From: %s\n' "$MAIL_FROM"
        printf 'Subject: %s\n' "$MAIL_SUBJECT"
        printf 'MIME-Version: 1.0\n'
        printf 'Content-Type: text/plain; charset=UTF-8\n'
        printf '\n'
        printf '%s\n' "$BODY"
    } | sendmail -t
    exit 0
fi

if command -v mail >/dev/null 2>&1; then
    printf '%s\n' "$BODY" | mail -s "$MAIL_SUBJECT" "$MAIL_TO"
    exit 0
fi

printf 'error: no mail transport available (mail/sendmail not installed)\n' >&2
exit 2
