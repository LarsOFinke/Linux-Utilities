#!/usr/bin/env bash
set -Eeuo pipefail

entry=${BASH_SOURCE[0]}
module_dir=$(cd -- "$(dirname -- "$entry")" && pwd)
module=${module_dir##*/}
action=${entry##*/}
action=${action%.sh}
repository=$(cd -- "$module_dir/../../.." && pwd)

[[ "$action" == setup || "$action" == uninstall ]] || {
    echo "Unsupported module action: $action" >&2
    exit 2
}
[[ -f "$repository/installer/main.py" ]] || {
    echo "Module setup and removal require the repository installer. Use main.sh from the repository root." >&2
    exit 2
}

if [[ "$module" == system ]]; then
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
        exec "$repository/scripts/$action.sh" "${args[@]}"
    fi
    exec "$repository/scripts/$action.sh" --module system "${args[@]}"
fi

exec "$repository/scripts/$action.sh" --module "$module" "$@"
