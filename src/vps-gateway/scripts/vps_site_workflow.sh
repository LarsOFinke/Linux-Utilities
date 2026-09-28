#!/usr/bin/env bash
set -Eeuo pipefail

workflow=${0##*/}
case "$workflow" in
    vps-gateway-init) action=init ;;
    vps-gateway-add) action=add ;;
    vps-gateway-site-list) action=list ;;
    vps-gateway-site-render) action=render ;;
    *) printf 'Unknown VPS site workflow: %s\n' "$workflow" >&2; exit 2 ;;
esac
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "$script_dir/vps-gateway-site" "$action" "$@"
