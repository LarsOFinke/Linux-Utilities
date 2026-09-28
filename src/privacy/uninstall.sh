#!/usr/bin/env bash
set -Eeuo pipefail
module_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -f "$module_dir/../installation/manage.py" ]]; then
    exec python3 "$module_dir/../installation/manage.py" uninstall --module privacy "$@"
fi
exec python3 "$module_dir/portable_module.py" uninstall "$@"
