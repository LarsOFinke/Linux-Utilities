#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

: "${REMOTE_BACKUP_SOURCE:?Set REMOTE_BACKUP_SOURCE to an scp remote source}"
: "${REMOTE_BACKUP_DESTINATION:?Set REMOTE_BACKUP_DESTINATION to a local directory}"

destination=$(realpath -m -- "$REMOTE_BACKUP_DESTINATION")
[[ "$destination" != / ]] || { echo 'Refusing to replace /' >&2; exit 2; }
parent=$(dirname -- "$destination")
mkdir -p -- "$parent"

staging=$(mktemp -d "$parent/.remote-fetch.XXXXXXXX")
rollback=
cleanup() {
    if [[ -n "$rollback" && -e "$rollback" && ! -e "$destination" ]]; then
        mv -- "$rollback" "$destination" || true
    fi
    rm -rf -- "$staging"
}
trap cleanup EXIT

scp -r -- "$REMOTE_BACKUP_SOURCE" "$staging/data"
[[ -d "$staging/data" ]] || { echo 'Remote copy did not create a directory' >&2; exit 1; }

if [[ -e "$destination" ]]; then
    rollback="${destination}.rollback.$(date +%Y-%m-%dT%H%M%S.%N).$BASHPID"
    mv -- "$destination" "$rollback"
fi
mv -- "$staging/data" "$destination"
printf 'Remote backup available: %s\n' "$destination"
if [[ -n "$rollback" ]]; then
    printf 'Previous copy retained for rollback: %s\n' "$rollback"
fi
