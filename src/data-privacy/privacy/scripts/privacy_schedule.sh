# shellcheck shell=bash disable=SC2034,SC2154
# Privacy configuration and schedule lifecycle.
ask() {
    local label=$1 default=$2 answer
    read -r -p "$label [$default]: " answer ||
        die 'Input ended before configuration was complete.'
    printf '%s' "${answer:-$default}"
}
save_existing() {
    local path=$1 stamp=$2
    [[ ! -L "$path" ]] || die "Refusing symbolic link: $path"
    [[ ! -f "$path" ]] || cp -a -- "$path" "${path}.backup.$stamp"
}
write_config() {
    local temporary
    temporary=$(mktemp "$config_dir/.privacy.cfg.XXXXXX")
    if [[ "$scope" == user ]]; then
        printf 'HISTORY_DAYS=%s\nUSER_LOG_DAYS=%s\nUSER_LOG_DIR=%s\nRUN_HOUR=%s\nRUN_MINUTE=%s\n' \
            "$HISTORY_DAYS" "$USER_LOG_DAYS" "$USER_LOG_DIR" "$RUN_HOUR" "$RUN_MINUTE" >"$temporary"
    else
        printf 'JOURNAL_DAYS=%s\nCRON_DAYS=%s\nLOGIN_DAYS=%s\nSYSTEM_DAYS=%s\nRUN_HOUR=%s\nRUN_MINUTE=%s\n' \
            "$JOURNAL_DAYS" "$CRON_DAYS" "$LOGIN_DAYS" "$SYSTEM_DAYS" "$RUN_HOUR" "$RUN_MINUTE" >"$temporary"
    fi
    chmod 0600 -- "$temporary"
    mv -f -- "$temporary" "$config_file"
}
install_user_schedule() {
    command -v crontab >/dev/null 2>&1 || die 'crontab is required for the user schedule.'
    local old_crontab temporary quoted_script
    old_crontab=$(mktemp "$state_dir/.crontab-old.XXXXXX")
    temporary=$(mktemp "$state_dir/.crontab-new.XXXXXX")
    crontab -l >"$old_crontab" 2>/dev/null || true
    cp -- "$old_crontab" "$state_dir/crontab.backup.$(date +%Y%m%d-%H%M%S)"
    sed '/# privacy-cleanup user$/d' "$old_crontab" >"$temporary"
    printf -v quoted_script '%q' "$scheduled_script"
    printf '%s %s * * * %s # privacy-cleanup user\n' \
        "$((10#$RUN_MINUTE))" "$((10#$RUN_HOUR))" "$quoted_script" >>"$temporary"
    crontab "$temporary"
    rm -f -- "$old_crontab" "$temporary"
}
install_system_schedule() {
    local temporary quoted_script
    mkdir -p -- "$(dirname "$cron_file")"
    [[ ! -L "$cron_file" ]] || die "Refusing symbolic link: $cron_file"
    temporary=$(mktemp "$(dirname "$cron_file")/.privacy-cron.XXXXXX")
    printf -v quoted_script '%q' "$scheduled_script"
    printf '# managed by shell-scripts privacy\nSHELL=/bin/bash\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n%s %s * * * root %s --system\n' \
        "$((10#$RUN_MINUTE))" "$((10#$RUN_HOUR))" "$quoted_script" >"$temporary"
    chmod 0644 -- "$temporary"
    mv -f -- "$temporary" "$cron_file"
}
configure() {
    require_system_access
    local stamp
    [[ -x "$installed_script" && ! -L "$installed_script" ]] ||
        die "Install the privacy module with setup.sh before configuring: $installed_script"
    [[ -x "$scheduled_script" && ! -L "$scheduled_script" ]] ||
        die "Install the privacy module with setup.sh before configuring: $scheduled_script"
    if [[ "$scope" == user ]]; then
        command -v crontab >/dev/null 2>&1 ||
            die 'crontab is required for the user schedule.'
    fi
    RUN_HOUR=3 RUN_MINUTE=17
    if [[ "$scope" == user ]]; then
        HISTORY_DAYS=30 USER_LOG_DAYS=30 USER_LOG_DIR="$HOME/.local/state"
    else
        JOURNAL_DAYS=14 CRON_DAYS=30 LOGIN_DAYS=90 SYSTEM_DAYS=30
    fi
    [[ ! -f "$config_file" ]] || load_config
    printf '%s\n' 'Enter retention in days; 0 disables a category.'
    if [[ "$scope" == user ]]; then
        HISTORY_DAYS=$(ask 'Clear your entire Bash history every N days' "$HISTORY_DAYS")
        USER_LOG_DAYS=$(ask 'Old user log retention' "$USER_LOG_DAYS")
        USER_LOG_DIR=$(ask 'User log directory (inside HOME)' "$USER_LOG_DIR")
    else
        JOURNAL_DAYS=$(ask 'Journal retention' "$JOURNAL_DAYS")
        CRON_DAYS=$(ask 'Rotated cron log retention' "$CRON_DAYS")
        LOGIN_DAYS=$(ask 'Rotated wtmp/btmp retention (last/lastb)' "$LOGIN_DAYS")
        SYSTEM_DAYS=$(ask 'Other rotated system log retention' "$SYSTEM_DAYS")
    fi
    RUN_HOUR=$(ask 'Daily cleanup hour (local time, 0–23)' "$RUN_HOUR")
    RUN_MINUTE=$(ask 'Daily cleanup minute (0–59)' "$RUN_MINUTE")
    validate_config
    mkdir -p -- "$config_dir" "$state_dir"
    chmod 0700 -- "$config_dir" "$state_dir"
    stamp=$(date +%Y%m%d-%H%M%S)
    save_existing "$config_file" "$stamp"
    [[ "$scope" != system ]] || save_existing "$cron_file" "$stamp"
    write_config
    if [[ "$scope" == user ]]; then
        install_user_schedule
        [[ -e "$state_dir/history-last-clean" ]] || touch "$state_dir/history-last-clean"
    else
        install_system_schedule
    fi
    printf 'Configured %s cleanup for %02d:%02d daily.\n' \
        "$scope" "$((10#$RUN_HOUR))" "$((10#$RUN_MINUTE))"
}
uninstall_schedule() {
    require_system_access
    local old_crontab retained backup
    if [[ "$scope" == user ]]; then
        if command -v crontab >/dev/null 2>&1; then
            old_crontab=$(mktemp)
            retained=$(mktemp)
            if crontab -l >"$old_crontab" 2>/dev/null; then
                sed '/# privacy-cleanup user$/d' "$old_crontab" >"$retained"
                if ! cmp -s "$old_crontab" "$retained"; then
                    mkdir -p -- "$state_dir"
                    chmod 0700 -- "$state_dir"
                    backup="$state_dir/crontab.backup.$(date +%Y%m%d-%H%M%S)"
                    cp -- "$old_crontab" "$backup"
                    crontab "$retained"
                fi
            fi
            rm -f -- "$old_crontab" "$retained"
        fi
    elif [[ -f "$cron_file" && ! -L "$cron_file" ]] &&
         grep -q '^# managed by shell-scripts privacy$' "$cron_file"; then
        rm -- "$cron_file"
    fi
    if [[ "$option" == --purge-config ]]; then
        [[ ! -L "$config_file" ]] || die "Refusing symbolic-link configuration: $config_file"
        [[ ! -f "$config_file" ]] || rm -- "$config_file"
    fi
}
