#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=src/backup/scripts/backup_home_common.sh
source "${SCRIPT_DIR}/backup_home_common.sh"

backup_home_run "${1:-}"

# Keep the two newest archives even when the user requests old-month cleanup.
shopt -s nullglob
archives=("${BACKUP_DESTINATION}"/backup_home_"${BACKUP_NAME}"_*.tar.bz2)
if (( ${#archives[@]} <= 2 )); then
    exit 0
fi

current_month=$(date +%Y-%m)
old_archives=()
for ((index = 0; index < ${#archives[@]} - 2; index++)); do
    filename=${archives[index]##*/}
    [[ "$filename" == "backup_home_${BACKUP_NAME}_${current_month}"* ]] || old_archives+=("${archives[index]}")
done

if (( ${#old_archives[@]} > 0 )); then
    printf '%s\n' 'Older archives available for deletion:'
    printf '  %s\n' "${old_archives[@]}"
    read -r -n 1 -p 'Delete these archives? (y/N) ' choice || exit 0
    printf '\n'
    if [[ "$choice" == [yY] ]]; then
        rm -- "${old_archives[@]}"
    fi
fi
