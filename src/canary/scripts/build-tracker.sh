#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# -eq 1 ]] || { echo 'Usage: build-tracker.sh OUTPUT' >&2; exit 2; }
module_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
includes=()
for directory in actions config events monitoring output process; do
    includes+=("-I$module_dir/tracker/$directory")
done
sources=(
    "$module_dir/tracker/app/main.c"
    "$module_dir/tracker/actions/action.c"
    "$module_dir/tracker/config/config.c"
    "$module_dir/tracker/events/event_names.c"
    "$module_dir/tracker/monitoring/fanotify_source.c"
    "$module_dir/tracker/output/jsonl_sink.c"
    "$module_dir/tracker/process/proc_info.c"
)
"${CC:-cc}" -std=gnu11 -O2 -Wall -Wextra -Wpedantic "${includes[@]}" "${sources[@]}" -o "$1"
