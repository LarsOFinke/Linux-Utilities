#!/bin/sh
set -eu

[ "$#" -eq 3 ] || {
    printf 'usage: %s EVENT_PATH EVENT_MASK EVENT_PID\n' "$0" >&2
    exit 2
}

POST_URL=${FS_TRACKER_POST_URL:-}
[ -n "$POST_URL" ] || {
    printf 'error: FS_TRACKER_POST_URL is not set\n' >&2
    exit 2
}

command -v curl >/dev/null 2>&1 || {
    printf 'error: curl is not installed\n' >&2
    exit 2
}

curl --fail --silent --show-error --max-time "${FS_TRACKER_POST_TIMEOUT:-10}" \
    --request POST \
    --data-urlencode "event_path=$1" \
    --data-urlencode "event_mask=$2" \
    --data-urlencode "event_pid=$3" \
    "$POST_URL" >/dev/null
