#!/usr/bin/env bash
set -Eeuo pipefail

workflow=${0##*/}
action=${workflow#ubuntu-updates-}
case "$action" in
    configure|status|logs|dry-run|run|restore) ;;
    *) printf 'Unknown Ubuntu updates workflow: %s\n' "$workflow" >&2; exit 2 ;;
esac
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "$script_dir/ubuntu-updates" "$action" "$@"
