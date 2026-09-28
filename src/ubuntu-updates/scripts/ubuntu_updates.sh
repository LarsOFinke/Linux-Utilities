#!/usr/bin/env bash
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

cleanup_files() {
    local item
    for item in "${CLEANUP_FILES[@]}"; do
        [[ ! -e "$item" ]] || rm -f -- "$item"
    done
}
trap cleanup_files EXIT

fail() { printf 'ubuntu-updates: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }

require_ubuntu() {
    local os_release="$ROOT/etc/os-release"
    [[ -r "$os_release" ]] || fail "Cannot read $os_release"
    # shellcheck disable=SC1090
    source "$os_release"
    [[ "${ID:-}" == ubuntu ]] || fail "Ubuntu is required (found ${ID:-unknown})."
}

require_root() {
    [[ "$ROOT" != / || $EUID -eq 0 ]] && return 0
    command -v sudo >/dev/null || fail 'sudo is required for this action.'
    exec sudo -- "$SCRIPT_PATH" "$@"
}

ask_yes() {
    local answer
    read -r -p "$1 [y/N] " answer || return 1
    [[ "$answer" == [yY] || "$answer" == [yY][eE][sS] ]]
}

timer_state() {
    local value
    value=$(systemctl is-enabled "$1" 2>/dev/null) || true
    [[ "$value" == enabled || "$value" == disabled ]] || fail "Unsupported timer state for $1: ${value:-unknown}"
    printf '%s' "$value"
}

timer_active() {
    local value
    value=$(systemctl is-active "$1" 2>/dev/null) || true
    [[ "$value" == active || "$value" == inactive ]] || fail "Unsupported timer activity for $1: ${value:-unknown}"
    printf '%s' "$value"
}

set_timer_state() {
    local unit=$1 desired=$2 desired_active=$3 current
    current=$(timer_state "$unit") || return 1
    if [[ "$current" != "$desired" ]]; then
        if [[ "$desired" == enabled ]]; then
            systemctl enable "$unit" || return 1
        else
            systemctl disable "$unit" || return 1
        fi
    fi
    current=$(timer_active "$unit") || return 1
    if [[ "$current" != "$desired_active" ]]; then
        if [[ "$desired_active" == active ]]; then
            systemctl start "$unit" || return 1
        else
            systemctl stop "$unit" || return 1
        fi
    fi
}

read_state() {
    [[ -f "$STATE" && ! -L "$STATE" ]] || fail "Missing or unsafe state: $STATE"
    saved_hash='' baseline_daily='' baseline_upgrade=''
    baseline_daily_active='' baseline_upgrade_active=''
    local key value
    while IFS='=' read -r key value; do
        case "$key" in
            POLICY_SHA256) saved_hash=$value ;;
            BASELINE_DAILY) baseline_daily=$value ;;
            BASELINE_UPGRADE) baseline_upgrade=$value ;;
            BASELINE_DAILY_ACTIVE) baseline_daily_active=$value ;;
            BASELINE_UPGRADE_ACTIVE) baseline_upgrade_active=$value ;;
            *) fail "Unknown key in $STATE: $key" ;;
        esac
    done < "$STATE"
    [[ "$saved_hash" =~ ^[0-9a-f]{64}$ ]] || fail "Invalid policy hash in $STATE"
    [[ "$baseline_daily" == enabled || "$baseline_daily" == disabled ]] || fail "Invalid daily timer state in $STATE"
    [[ "$baseline_upgrade" == enabled || "$baseline_upgrade" == disabled ]] || fail "Invalid upgrade timer state in $STATE"
    [[ "$baseline_daily_active" == active || "$baseline_daily_active" == inactive ]] || fail "Invalid daily timer activity in $STATE"
    [[ "$baseline_upgrade_active" == active || "$baseline_upgrade_active" == inactive ]] || fail "Invalid upgrade timer activity in $STATE"
}

check_owned_policy() {
    [[ -f "$POLICY" && ! -L "$POLICY" ]] || fail "Managed policy is missing or unsafe: $POLICY"
    [[ "$(sha256sum "$POLICY" | cut -d' ' -f1)" == "$saved_hash" ]] || fail "Managed policy changed locally: $POLICY"
}

render_policy() {
    local updates=$1 reboot=$2
    cat <<'CONF'
// Managed by shell-scripts ubuntu-updates. Changes require ubuntu-updates configure.
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
#clear Unattended-Upgrade::Allowed-Origins;
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
CONF
    if [[ "$updates" == all ]]; then
        # APT expands these variables when it reads the policy.
        # shellcheck disable=SC2016
        printf '    "${distro_id}:${distro_codename}-updates";\n'
    fi
    if [[ "$reboot" == off ]]; then
        reboot=false
    else
        reboot=true
    fi
    cat <<CONF
};
Unattended-Upgrade::Remove-Unused-Dependencies "false";
Unattended-Upgrade::Automatic-Reboot "$reboot";
Unattended-Upgrade::Automatic-Reboot-WithUsers "false";
CONF
    if [[ "$reboot" == true ]]; then
        printf 'Unattended-Upgrade::Automatic-Reboot-Time "%s";\n' "$2"
    fi
}

ensure_package() {
    if dpkg-query -W -f='${Status}' unattended-upgrades 2>/dev/null | grep -qx 'install ok installed'; then
        return
    fi
    info 'Installing Ubuntu unattended-upgrades...'
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y unattended-upgrades
}

apply_policy() {
    local updates=$1 reboot=$2 had_state=false old_daily old_upgrade old_daily_active old_upgrade_active
    local policy_tmp previous_tmp state_tmp new_hash
    require_root configure --updates "$updates" --reboot "$reboot" --yes
    require_ubuntu
    command -v flock >/dev/null || fail 'flock is required.'
    [[ -d "$APT_DIR" && ! -L "$APT_DIR" ]] || fail "Missing or unsafe APT directory: $APT_DIR"
    [[ ! -L "$POLICY" && ! -L "$STATE_DIR" && ! -L "$STATE" ]] || fail 'Refusing symbolic-link policy or state.'
    [[ ! -e "$LEGACY_POLICY" && ! -L "$LEGACY_POLICY" ]] || fail "Legacy policy exists: $LEGACY_POLICY; restore it with the original tool first."
    install -d -m 0700 "$STATE_DIR"
    exec 9>"$STATE_DIR/lock"
    flock -n 9 || fail 'Another ubuntu-updates change is running.'

    old_daily=$(timer_state apt-daily.timer)
    old_upgrade=$(timer_state apt-daily-upgrade.timer)
    old_daily_active=$(timer_active apt-daily.timer)
    old_upgrade_active=$(timer_active apt-daily-upgrade.timer)
    if [[ -e "$STATE" ]]; then
        read_state
        check_owned_policy
        had_state=true
    else
        [[ ! -e "$POLICY" ]] || fail "Unmanaged policy already exists: $POLICY"
        baseline_daily=$old_daily
        baseline_upgrade=$old_upgrade
        baseline_daily_active=$old_daily_active
        baseline_upgrade_active=$old_upgrade_active
    fi

    ensure_package
    policy_tmp=$(mktemp "$APT_DIR/.shell-scripts-policy.XXXXXX")
    previous_tmp=$(mktemp "$STATE_DIR/.previous.XXXXXX")
    state_tmp=$(mktemp "$STATE_DIR/.state.XXXXXX")
    CLEANUP_FILES+=("$policy_tmp" "$previous_tmp" "$state_tmp")
    if [[ "$had_state" == true ]]; then
        cp -p -- "$POLICY" "$previous_tmp"
    fi
    render_policy "$updates" "$reboot" > "$policy_tmp"
    apt-config -c "$policy_tmp" dump >/dev/null || fail 'Generated APT policy is invalid.'
    chmod 0644 "$policy_tmp"
    mv -f -- "$policy_tmp" "$POLICY"

    if ! apt-config dump >/dev/null || ! systemctl enable --now apt-daily.timer apt-daily-upgrade.timer; then
        if [[ "$had_state" == true ]]; then
            cp -p -- "$previous_tmp" "$POLICY"
        else
            rm -f -- "$POLICY"
        fi
        set_timer_state apt-daily.timer "$old_daily" "$old_daily_active" || true
        set_timer_state apt-daily-upgrade.timer "$old_upgrade" "$old_upgrade_active" || true
        rm -f -- "$previous_tmp" "$state_tmp"
        fail 'Policy or timer activation failed; previous state restored.'
    fi

    new_hash=$(sha256sum "$POLICY" | cut -d' ' -f1)
    if ! {
        printf 'POLICY_SHA256=%s\nBASELINE_DAILY=%s\nBASELINE_UPGRADE=%s\nBASELINE_DAILY_ACTIVE=%s\nBASELINE_UPGRADE_ACTIVE=%s\n' \
            "$new_hash" "$baseline_daily" "$baseline_upgrade" "$baseline_daily_active" "$baseline_upgrade_active" > "$state_tmp" &&
        chmod 0600 "$state_tmp" &&
        mv -f -- "$state_tmp" "$STATE"
    }; then
        if [[ "$had_state" == true ]]; then
            cp -p -- "$previous_tmp" "$POLICY"
        else
            rm -f -- "$POLICY"
        fi
        set_timer_state apt-daily.timer "$old_daily" "$old_daily_active" || true
        set_timer_state apt-daily-upgrade.timer "$old_upgrade" "$old_upgrade_active" || true
        fail 'Could not save ownership state; previous policy and timers restored.'
    fi
    if [[ "$had_state" == true ]]; then
        local revision
        revision=$(mktemp "$STATE_DIR/revision.$(date -u +%Y%m%dT%H%M%S).XXXXXX.cfg")
        mv -f -- "$previous_tmp" "$revision"
    else
        rm -f -- "$previous_tmp"
    fi
    info "Configured $POLICY"
}

restore_policy() {
    local previous_tmp old_daily old_upgrade old_daily_active old_upgrade_active
    require_root restore --yes
    [[ ! -L "$STATE" ]] || fail "Unsafe state file: $STATE"
    [[ -e "$STATE" ]] || { info 'No owned policy to restore.'; return 0; }
    command -v flock >/dev/null || fail 'flock is required.'
    [[ ! -L "$STATE_DIR" ]] || fail "Unsafe state directory: $STATE_DIR"
    exec 9>"$STATE_DIR/lock"
    flock -n 9 || fail 'Another ubuntu-updates change is running.'
    read_state
    check_owned_policy
    old_daily=$(timer_state apt-daily.timer)
    old_upgrade=$(timer_state apt-daily-upgrade.timer)
    old_daily_active=$(timer_active apt-daily.timer)
    old_upgrade_active=$(timer_active apt-daily-upgrade.timer)
    previous_tmp=$(mktemp "$APT_DIR/.shell-scripts-restore.XXXXXX")
    CLEANUP_FILES+=("$previous_tmp")
    cp -p -- "$POLICY" "$previous_tmp"
    rm -- "$POLICY"
    if ! apt-config dump >/dev/null ||
        ! set_timer_state apt-daily.timer "$baseline_daily" "$baseline_daily_active" ||
        ! set_timer_state apt-daily-upgrade.timer "$baseline_upgrade" "$baseline_upgrade_active"; then
        mv -f -- "$previous_tmp" "$POLICY"
        set_timer_state apt-daily.timer "$old_daily" "$old_daily_active" || true
        set_timer_state apt-daily-upgrade.timer "$old_upgrade" "$old_upgrade_active" || true
        fail 'Restore failed; managed policy put back for retry.'
    fi
    rm -f -- "$previous_tmp" "$STATE"
    info 'Restored Ubuntu package policy and recorded timer state.'
}

show_status() {
    require_ubuntu
    if [[ -r "$STATE" ]]; then
        read_state
        if [[ -f "$POLICY" && ! -L "$POLICY" ]] && [[ "$(sha256sum "$POLICY" | cut -d' ' -f1)" == "$saved_hash" ]]; then
            info 'Managed policy: active and verified'
        else
            info 'Managed policy: changed or missing'
        fi
    elif [[ -f "$POLICY" && ! -L "$POLICY" ]]; then
        info 'Policy file: present; ownership verification requires root'
    else
        info 'Managed policy: absent'
    fi
    for unit in apt-daily.timer apt-daily-upgrade.timer; do
        info "$unit: $(systemctl is-enabled "$unit" 2>/dev/null || printf unknown)"
    done
    if [[ -e "$ROOT/var/run/reboot-required" ]]; then info 'Reboot required: yes'; fi
    apt-config dump 2>/dev/null | grep -E '^(APT::Periodic::(Update-Package-Lists|Unattended-Upgrade)|Unattended-Upgrade::Automatic-Reboot )' || true
}

show_logs() {
    local file
    for file in "$LOG_DIR/unattended-upgrades.log" "$LOG_DIR/unattended-upgrades-dpkg.log"; do
        if [[ -r "$file" ]]; then
            info "--- $file ---"
            tail -n 40 "$file"
        fi
    done
    journalctl -u apt-daily-upgrade.service -n 40 --no-pager 2>/dev/null || true
}

run_update() {
    local dry=$1
    require_ubuntu
    [[ "$(dpkg-query -W -f='${Status}' unattended-upgrades 2>/dev/null)" == 'install ok installed' ]] || fail 'unattended-upgrades is not installed.'
    if [[ "$dry" == true ]]; then
        require_root dry-run
        unattended-upgrade -v --dry-run
    else
        require_root run --yes
        apt-get update
        unattended-upgrade -v
    fi
}

configure_command() {
    local updates='' reboot='' confirmed=false
    while (( $# )); do
        case "$1" in
            --updates) (( $# >= 2 )) || fail 'Missing --updates value.'; updates=$2; shift 2 ;;
            --reboot) (( $# >= 2 )) || fail 'Missing --reboot value.'; reboot=$2; shift 2 ;;
            --yes) confirmed=true; shift ;;
            *) fail "Unknown configure option: $1" ;;
        esac
    done
    if [[ -z "$updates" || -z "$reboot" ]]; then
        [[ -t 0 ]] || fail 'Use --updates security|all and --reboot off|HH:MM.'
        if [[ -z "$updates" ]]; then
            if ask_yes 'Include regular Ubuntu updates?'; then updates=all; else updates=security; fi
        fi
        if [[ -z "$reboot" ]]; then
            if ask_yes 'Allow automatic reboot when no users are logged in?'; then
                read -r -p 'Reboot time [04:00]: ' reboot
                reboot=${reboot:-04:00}
            else reboot=off; fi
        fi
    fi
    [[ "$updates" == security || "$updates" == all ]] || fail 'Updates must be security or all.'
    [[ "$reboot" == off || "$reboot" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]] || fail 'Reboot must be off or HH:MM.'
    if [[ "$confirmed" != true ]]; then
        info "Updates: $updates; automatic reboot: $reboot"
        ask_yes 'Apply this Ubuntu update policy?' || { info 'Cancelled.'; return 0; }
    fi
    apply_policy "$updates" "$reboot"
}

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
