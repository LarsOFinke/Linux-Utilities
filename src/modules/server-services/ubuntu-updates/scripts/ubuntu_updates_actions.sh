# shellcheck shell=bash disable=SC2034,SC2154
# Read-only status/logs and manual update execution.
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
