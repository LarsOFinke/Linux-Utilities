#!/usr/bin/env bash
set -Eeuo pipefail

[[ $# -eq 0 ]] || { printf 'Usage: uninstall-h848-audio-fix\n' >&2; exit 2; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "$script_dir/install-h848-audio-fix" --uninstall
