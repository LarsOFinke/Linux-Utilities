#!/usr/bin/env bash
set -Eeuo pipefail

workflow=${0##*/}
action=${workflow#vps-gateway-}
case "$action" in
    configure|status) ;;
    *) printf 'Unknown VPS gateway workflow: %s\n' "$workflow" >&2; exit 2 ;;
esac
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "$script_dir/vps-gateway" "$action" "$@"
