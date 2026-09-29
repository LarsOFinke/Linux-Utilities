#!/usr/bin/env bash
set -Eeuo pipefail
module_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -f "$module_dir/../../../installation/setup_module.sh" ]]; then
    exec "$module_dir/../../../installation/setup_module.sh" privacy "$@"
fi
exec python3 "$module_dir/portable_module.py" install "$@"
