#!/usr/bin/env bash
set -Eeuo pipefail
module_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -f "$module_dir/../installation/manage.py" ]]; then
    exec "$module_dir/../../uninstall.sh" --module ubuntu-updates "$@"
fi
exec python3 "$module_dir/portable_module.py" uninstall "$@"
