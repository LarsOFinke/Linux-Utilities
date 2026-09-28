# shellcheck shell=bash disable=SC2034,SC2154
# Policy rendering, apply, and restore workflows.
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
