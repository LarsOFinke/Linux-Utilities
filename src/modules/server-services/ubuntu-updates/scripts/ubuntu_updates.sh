#!/usr/bin/env bash
# shellcheck disable=SC1091,SC2034
set -Eeuo pipefail
umask 077

SCRIPT_PATH=$(realpath -- "${BASH_SOURCE[0]}")
ROOT=$(realpath -m -- "${UU_ROOT:-/}")
APT_DIR="$ROOT/etc/apt/apt.conf.d"
POLICY="$APT_DIR/99-shell-scripts-unattended-upgrades"
LEGACY_POLICY="$APT_DIR/99-cybersec-auto-updates"
STATE_DIR="$ROOT/var/lib/shell-scripts/ubuntu-updates"
STATE="$STATE_DIR/state.cfg"
LOG_DIR="$ROOT/var/log/unattended-upgrades"
CLEANUP_FILES=()

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$script_dir/ubuntu_updates_state.sh"
source "$script_dir/ubuntu_updates_policy.sh"
source "$script_dir/ubuntu_updates_actions.sh"

menu() {
    local choice
    while true; do
        cat <<'MENU'
Ubuntu updates
  1) Configure unattended upgrades
  2) Status
  3) Dry-run
  4) Run updates now
  5) Recent logs
  6) Restore Ubuntu defaults
  0) Exit
MENU
        read -r -p 'Choose: ' choice || return 0
        case "$choice" in
            1) configure_command ;;
            2) show_status ;;
            3) run_update true ;;
            4) if ask_yes 'Install available updates now?'; then run_update false; fi ;;
            5) show_logs ;;
            6) if ask_yes 'Restore owned policy and recorded timer state?'; then restore_policy; fi ;;
            0) return 0 ;;
            *) info 'Choose a listed number.' ;;
        esac
    done
}

case "${1:-}" in
    '') (( $# == 0 )) || fail 'Unexpected arguments.'; menu ;;
    configure) shift; configure_command "$@" ;;
    status) (( $# == 1 )) || fail 'status takes no options.'; show_status ;;
    logs) (( $# == 1 )) || fail 'logs takes no options.'; show_logs ;;
    dry-run) (( $# == 1 )) || fail 'dry-run takes no options.'; run_update true ;;
    run)
        [[ $# == 1 || ( $# == 2 && "$2" == --yes ) ]] || fail 'Use run [--yes].'
        if [[ $# == 2 ]] || ask_yes 'Install available updates now?'; then run_update false; fi
        ;;
    restore)
        [[ $# == 1 || ( $# == 2 && "$2" == --yes ) ]] || fail 'Use restore [--yes].'
        if [[ $# == 2 ]] || ask_yes 'Restore owned policy and timer state?'; then restore_policy; fi
        ;;
    *) fail "Unknown command: $1" ;;
esac
