#!/usr/bin/env bash
# shellcheck shell=bash disable=SC2034

backup_home_prepare() {
    local name=${1:-} allow_missing=${2:-false}
    local source_root source_dir backup_root destination
    [[ "$name" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]] || {
        printf 'Provide one valid home directory name.\n' >&2
        return 2
    }
    source_root=$(realpath -e -- "${BACKUP_SOURCE_ROOT:-/home}") || return 1
    if [[ "$allow_missing" == true ]]; then
        source_dir=$(realpath -m -- "${source_root}/${name}") || return 1
    else
        source_dir=$(realpath -e -- "${source_root}/${name}") || return 1
    fi
    [[ "$source_dir" == "${source_root}/${name}" && ( "$allow_missing" == true || -d "$source_dir" ) ]] || {
        printf 'Home directory is missing or resolves outside the source root: %s\n' "$name" >&2
        return 1
    }

    backup_root=$(realpath -m -- "${BACKUP_ROOT:-${source_root}/backups}") || return 1
    destination=$(realpath -m -- "${backup_root}/${name}") || return 1
    if [[ "$destination" != "${backup_root}/${name}" || "$destination/" == "$source_dir/"* || "$source_dir/" == "$destination/"* ]]; then
        printf 'Backup destination must be outside the source home.\n' >&2
        return 1
    fi

    BACKUP_NAME=$name
    BACKUP_SOURCE_DIR=$source_dir
    BACKUP_DESTINATION=$destination
}

backup_home_run() {
    local name=${1:-}
    local destination timestamp archive temp_archive temp_link lock_fd
    umask 077
    backup_home_prepare "$name" || return $?
    destination=$BACKUP_DESTINATION
    mkdir -p -- "$destination" || return 1
    chmod 0700 -- "$destination" || return 1
    exec {lock_fd}>"${destination}/.backup.lock"
    flock -n "$lock_fd" || {
        printf 'Another backup is already running for %s.\n' "$name" >&2
        return 1
    }

    timestamp=$(date +%Y-%m-%dT%H%M%S.%N)
    archive="${destination}/backup_home_${name}_${timestamp}_$BASHPID.tar.bz2"
    temp_archive=$(mktemp "${destination}/.backup.XXXXXXXX.tar.bz2") || return 1
    temp_link="${destination}/.latest.$BASHPID"

    if ! tar -cjf "$temp_archive" -C "$BACKUP_SOURCE_DIR" . ||
       ! tar -tjf "$temp_archive" >/dev/null; then
        rm -f -- "$temp_archive"
        printf 'Backup creation or verification failed; previous archives remain available.\n' >&2
        return 1
    fi

    if ! mv -- "$temp_archive" "$archive"; then
        rm -f -- "$temp_archive"
        return 1
    fi

    if ! ln -s -- "${archive##*/}" "$temp_link" ||
       ! mv -Tf -- "$temp_link" "${destination}/latest.tar.bz2"; then
        rm -f -- "$temp_link"
        printf 'Archive created, but latest pointer could not be updated: %s\n' "$archive" >&2
        return 1
    fi

    printf 'Verified backup: %s\n' "$archive"
}
