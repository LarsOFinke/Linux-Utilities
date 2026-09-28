# shellcheck shell=bash disable=SC2034,SC2154
# Host state, ownership checks, and timer operations.
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
