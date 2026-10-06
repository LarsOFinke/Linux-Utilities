#!/usr/bin/env bash
set -Eeuo pipefail

if (( $# != 0 )); then
    printf 'Usage: update-system\n' >&2
    exit 2
fi

if ! command -v apt >/dev/null 2>&1; then
    printf 'update-system: apt is required\n' >&2
    exit 1
fi

apt_command=(apt)
if (( EUID != 0 )); then
    if ! command -v sudo >/dev/null 2>&1; then
        printf 'update-system: sudo is required when running as a non-root user\n' >&2
        exit 1
    fi
    apt_command=(sudo apt)
fi

if ! "${apt_command[@]}" update; then
    printf 'update-system: apt update failed; upgrade was skipped\n' >&2
    exit 1
fi

if ! "${apt_command[@]}" upgrade -y; then
    printf 'update-system: apt upgrade failed\n' >&2
    exit 1
fi
