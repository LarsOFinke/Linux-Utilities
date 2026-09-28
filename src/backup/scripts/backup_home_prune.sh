#!/usr/bin/env bash
set -Eeuo pipefail

[[ $# -ge 1 && $# -le 2 && ( $# -eq 1 || $2 == --yes ) ]] || {
    printf 'Usage: backup-home-prune NAME [--yes]\n' >&2
    exit 2
}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=src/backup/scripts/backup_home_common.sh
source "$script_dir/backup_home_common.sh"
backup_home_prepare "$1" true
destination=$BACKUP_DESTINATION
[[ -d "$destination" && ! -L "$destination" ]] || {
    printf 'Backup directory is missing or unsafe: %s\n' "$destination" >&2
    exit 1
}
exec {lock_fd}>"$destination/.backup.lock"
flock -n "$lock_fd" || { printf 'Another backup is running for %s.\n' "$BACKUP_NAME" >&2; exit 1; }

# Keep the two newest snapshots and every snapshot from the current month.
shopt -s nullglob
archives=("$destination"/backup_home_"$BACKUP_NAME"_*.tar.bz2)
(( ${#archives[@]} > 2 )) || exit 0
current_month=$(date +%Y-%m)
old_archives=()
for ((index = 0; index < ${#archives[@]} - 2; index++)); do
    filename=${archives[index]##*/}
    [[ "$filename" == "backup_home_${BACKUP_NAME}_${current_month}"* ]] || old_archives+=("${archives[index]}")
done
(( ${#old_archives[@]} > 0 )) || exit 0
printf '%s\n' 'Older archives available for deletion:'
printf '  %s\n' "${old_archives[@]}"
if [[ ${2:-} != --yes ]]; then
    read -r -n 1 -p 'Delete these archives? (y/N) ' choice || exit 0
    printf '\n'
    [[ "$choice" == [yY] ]] || exit 0
fi
rm -- "${old_archives[@]}"
