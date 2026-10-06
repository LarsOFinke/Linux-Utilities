#!/usr/bin/env bash
set -Eeuo pipefail

repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
case "${1:-}" in
    "") dry_run=false ;;
    --dry-run) dry_run=true ;;
    -h|--help)
        echo 'Usage: scripts/clean-cache.sh [--dry-run]'
        echo 'Remove generated Python and test caches inside installer/, src/, and scripts/.'
        exit 0
        ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
esac
(( $# <= 1 )) || { echo 'Too many arguments' >&2; exit 2; }

mapfile -d '' -t caches < <(
    find "$repository/installer" "$repository/src" "$repository/scripts" \
        -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache \) \
        -prune -print0
)
for name in .pytest_cache .ruff_cache .mypy_cache; do
    [[ ! -d "$repository/$name" || -L "$repository/$name" ]] || caches+=("$repository/$name")
done

if (( ${#caches[@]} == 0 )); then
    echo 'No generated caches found.'
    exit 0
fi
for cache in "${caches[@]}"; do
    [[ -d "$cache" && ! -L "$cache" ]] || continue
    if [[ "$dry_run" == true ]]; then
        printf 'Would remove: %s\n' "$cache"
    else
        rm -r -- "$cache"
        printf 'Removed: %s\n' "$cache"
    fi
done
