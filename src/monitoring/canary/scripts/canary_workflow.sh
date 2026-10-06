#!/usr/bin/env bash
set -Eeuo pipefail

workflow=${0##*/}
action=${workflow#canary-}
case "$action" in
    configure|status|start|stop|remove|remove-all) ;;
    *) printf 'Unknown Canary workflow: %s\n' "$workflow" >&2; exit 2 ;;
esac
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "$script_dir/canary-control" "$action" "$@"
