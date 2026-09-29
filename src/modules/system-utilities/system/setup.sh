#!/usr/bin/env bash
set -Eeuo pipefail
module_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -f "$module_dir/../../../installation/setup_module.sh" ]]; then
    args=()
    component_selected=false
    while (( $# )); do
        if [[ "$1" == --component ]]; then
            (( $# >= 2 )) || { echo 'Missing component name' >&2; exit 2; }
            args+=(--component "system:$2")
            component_selected=true
            shift 2
        else
            args+=("$1")
            shift
        fi
    done
    if [[ "$component_selected" == true ]]; then
        repository=$(cd -- "$module_dir/../../../.." && pwd)
        exec "$repository/setup.sh" "${args[@]}"
    fi
    exec "$module_dir/../../../installation/setup_module.sh" system "${args[@]}"
fi
exec python3 "$module_dir/portable_module.py" install "$@"
