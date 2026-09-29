#!/bin/sh
set -eu

EVENT_PATH=$1
EVENT_MASK=$2
EVENT_PID=$3
MARKER_FILE=${FS_TRACKER_MARKER:-/run/fs-tracker/event-triggered}

mkdir -p -- "$(dirname -- "$MARKER_FILE")"
printf '%s\t%s\t%s\n' "$EVENT_PATH" "$EVENT_MASK" "$EVENT_PID" >> "$MARKER_FILE"
