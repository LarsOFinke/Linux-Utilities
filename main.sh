#!/usr/bin/env bash
set -Eeuo pipefail

repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
choice=''
if (( $# )); then
    choice=$1
    shift
fi

while true; do
    if [[ -z $choice ]]; then
        [[ -t 0 ]] || { echo 'Choose setup, update, or uninstall (or run with a terminal).' >&2; exit 2; }
        printf 'Linux-Utilities\n  1. Setup\n  2. Update\n  3. Uninstall\n'
        read -r -p 'Choose an action [1-3, q]: ' choice || exit 0
    fi
    case "$choice" in
        1|setup) action=setup ;;
        2|update) action=update ;;
        3|uninstall) action=uninstall ;;
        q|quit) exit 0 ;;
        -h|--help)
            echo 'Usage: ./main.sh [setup|update|uninstall] [options]'
            exit 0
            ;;
        *) echo "Unknown action: $choice" >&2; exit 2 ;;
    esac
    if "$repository/scripts/$action.sh" "$@"; then
        exit 0
    else
        status=$?
        if (( status != 3 )) || [[ ! -t 0 ]]; then
            exit "$status"
        fi
        set --
        choice=''
    fi
done
