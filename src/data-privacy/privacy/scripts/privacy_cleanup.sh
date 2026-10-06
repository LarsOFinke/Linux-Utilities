#!/usr/bin/env bash
# shellcheck disable=SC1091,SC2034
set -Eeuo pipefail
umask 077

scope=user
if [[ "${1:-}" == --system ]]; then
    scope=system
    shift
fi
action=${1:-}
option=${2:-}
[[ $# -le 2 ]] || { echo 'Too many arguments' >&2; exit 2; }

root=$(realpath -m -- "${PRIVACY_ROOT:-/}")
prefix=${root%/}
if [[ "$scope" == user ]]; then
    [[ "$HOME" == /* && "$HOME" != / ]] || { echo 'HOME must be an absolute home directory' >&2; exit 1; }
    config_dir="$HOME/.config/privacy-cleanup"
    config_file="$config_dir/user.cfg"
    state_dir="$HOME/.local/state/privacy-cleanup"
    installed_script="$HOME/.local/bin/privacy-cleanup"
    scheduled_script="$HOME/.local/bin/privacy-scheduled"
else
    config_dir="$prefix/etc/privacy-cleanup"
    config_file="$config_dir/system.cfg"
    state_dir="$prefix/var/lib/privacy-cleanup"
    installed_script="$prefix/usr/local/bin/privacy-cleanup"
    scheduled_script="$prefix/usr/local/bin/privacy-scheduled"
    cron_file="$prefix/etc/cron.d/privacy-cleanup"
    log_dir="$prefix/var/log"
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=src/data-privacy/privacy/scripts/privacy_policy.sh
source "$script_dir/privacy_policy.sh"
# shellcheck source=src/data-privacy/privacy/scripts/privacy_schedule.sh
source "$script_dir/privacy_schedule.sh"
# shellcheck source=src/data-privacy/privacy/scripts/privacy_clean.sh
source "$script_dir/privacy_clean.sh"

usage() {
    printf 'Usage: %s [--system] configure | status | run [--dry-run|--yes] | scheduled [--dry-run] | uninstall-schedule [--purge-config]\n' "$0"
}
case "$action" in
    configure) [[ -z "$option" ]] || die 'configure takes no option'; configure ;;
    status) [[ -z "$option" ]] || die 'status takes no option'; load_config; cat "$config_file" ;;
    run)
        case "$option" in
            --dry-run) clean 1 1 ;;
            --yes) clean 1 0 ;;
            '')
                [[ -t 0 ]] || die 'Use --yes for non-interactive manual cleanup.'
                printf 'Apply all configured %s cleanup policies now? Type CLEAN to continue: ' "$scope"
                read -r answer
                [[ "$answer" == CLEAN ]] || die 'Cancelled.'
                clean 1 0 ;;
            *) usage; exit 2 ;;
        esac ;;
    scheduled)
        case "$option" in
            --dry-run) clean 0 1 ;;
            '') clean 0 0 ;;
            *) usage; exit 2 ;;
        esac ;;
    uninstall-schedule)
        [[ -z "$option" || "$option" == --purge-config ]] || { usage; exit 2; }
        uninstall_schedule ;;
    *) usage; exit 2 ;;
esac
