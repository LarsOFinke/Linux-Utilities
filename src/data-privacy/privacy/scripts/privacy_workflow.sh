#!/usr/bin/env bash
set -Eeuo pipefail

workflow=${0##*/}
action=${workflow#privacy-}
case "$action" in
    configure|status|run|scheduled|uninstall-schedule) ;;
    *) printf 'Unknown privacy workflow: %s\n' "$workflow" >&2; exit 2 ;;
esac
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ ${1:-} == --system ]]; then
    shift
    exec "$script_dir/privacy-cleanup" --system "$action" "$@"
fi
exec "$script_dir/privacy-cleanup" "$action" "$@"
