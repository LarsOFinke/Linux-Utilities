#!/usr/bin/env bash
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
else
    config_dir="$prefix/etc/privacy-cleanup"
    config_file="$config_dir/system.cfg"
    state_dir="$prefix/var/lib/privacy-cleanup"
    installed_script="$prefix/usr/local/bin/privacy-cleanup"
    cron_file="$prefix/etc/cron.d/privacy-cleanup"
    log_dir="$prefix/var/log"
fi

die() { printf 'privacy-cleanup: %s\n' "$*" >&2; exit 1; }
require_system_access() {
    [[ "$scope" != system || "$root" != / || "$EUID" -eq 0 ]] ||
        die 'Use sudo for --system operations.'
}
validate_days() {
    if [[ ! "$2" =~ ^[0-9]+$ ]] || (( 10#$2 > 3650 )); then
        die "$1 must be an integer from 0 to 3650."
    fi
}
validate_clock() {
    if [[ ! "$RUN_HOUR" =~ ^[0-9]{1,2}$ ]] || (( 10#$RUN_HOUR > 23 )); then
        die 'RUN_HOUR must be 0–23.'
    fi
    if [[ ! "$RUN_MINUTE" =~ ^[0-9]{1,2}$ ]] || (( 10#$RUN_MINUTE > 59 )); then
        die 'RUN_MINUTE must be 0–59.'
    fi
}
validate_config() {
    validate_clock
    if [[ "$scope" == user ]]; then
        validate_days HISTORY_DAYS "$HISTORY_DAYS"
        validate_days USER_LOG_DAYS "$USER_LOG_DAYS"
        HISTORY_DAYS=$((10#$HISTORY_DAYS))
        USER_LOG_DAYS=$((10#$USER_LOG_DAYS))
        [[ "$USER_LOG_DIR" == /* ]] || die 'USER_LOG_DIR must be absolute.'
        local canonical_home canonical_logs
        canonical_home=$(realpath -m -- "$HOME")
        canonical_logs=$(realpath -m -- "$USER_LOG_DIR")
        [[ "$canonical_logs/" == "$canonical_home/"* ]] ||
            die 'USER_LOG_DIR must be inside HOME.'
    else
        local key
        for key in JOURNAL_DAYS CRON_DAYS LOGIN_DAYS SYSTEM_DAYS; do
            validate_days "$key" "${!key}"
            printf -v "$key" '%s' "$((10#${!key}))"
        done
    fi
}
load_config() {
    [[ -f "$config_file" && ! -L "$config_file" ]] ||
        die "Configuration missing or unsafe: $config_file. Run configure first."
    HISTORY_DAYS='' USER_LOG_DAYS='' USER_LOG_DIR=''
    JOURNAL_DAYS='' CRON_DAYS='' LOGIN_DAYS='' SYSTEM_DAYS=''
    RUN_HOUR='' RUN_MINUTE=''
    local key value
    while IFS='=' read -r key value || [[ -n "$key" ]]; do
        [[ -z "$key" || "$key" == \#* ]] && continue
        case "$scope:$key" in
            user:HISTORY_DAYS|user:USER_LOG_DAYS|user:USER_LOG_DIR|\
            system:JOURNAL_DAYS|system:CRON_DAYS|system:LOGIN_DAYS|system:SYSTEM_DAYS|\
            *:RUN_HOUR|*:RUN_MINUTE)
                printf -v "$key" '%s' "$value" ;;
            *) die "Unknown configuration key: $key" ;;
        esac
    done <"$config_file"
    validate_config
}
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
    printf -v quoted_script '%q' "$installed_script"
    printf '%s %s * * * %s scheduled # privacy-cleanup user\n' \
        "$((10#$RUN_MINUTE))" "$((10#$RUN_HOUR))" "$quoted_script" >>"$temporary"
    crontab "$temporary"
    rm -f -- "$old_crontab" "$temporary"
}
install_system_schedule() {
    local temporary quoted_script
    mkdir -p -- "$(dirname "$cron_file")"
    [[ ! -L "$cron_file" ]] || die "Refusing symbolic link: $cron_file"
    temporary=$(mktemp "$(dirname "$cron_file")/.privacy-cron.XXXXXX")
    printf -v quoted_script '%q' "$installed_script"
    printf '# managed by shell-scripts privacy\nSHELL=/bin/bash\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n%s %s * * * root %s --system scheduled\n' \
        "$((10#$RUN_MINUTE))" "$((10#$RUN_HOUR))" "$quoted_script" >"$temporary"
    chmod 0644 -- "$temporary"
    mv -f -- "$temporary" "$cron_file"
}
configure() {
    require_system_access
    local stamp
    [[ -x "$installed_script" && ! -L "$installed_script" ]] ||
        die "Install the privacy module with setup.sh before configuring: $installed_script"
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
clean_history() {
    local force=$1 dry_run=$2 marker cutoff history
    (( HISTORY_DAYS > 0 )) || return 0
    marker="$state_dir/history-last-clean"
    cutoff=$(( $(date +%s) - HISTORY_DAYS * 86400 ))
    if (( ! force )) && [[ -f "$marker" ]] && (( $(stat -c %Y "$marker") > cutoff )); then
        return 0
    fi
    history="$HOME/.bash_history"
    [[ ! -L "$history" ]] || die "Refusing symbolic-link history file: $history"
    if [[ -f "$history" ]]; then
        if (( dry_run )); then
            printf 'Would clear Bash history: %s\n' "$history"
        else
            : >"$history"
            printf 'Cleared Bash history: %s\n' "$history"
        fi
    fi
    if (( ! dry_run )); then
        mkdir -p -- "$state_dir"
        touch "$marker"
    fi
}
prune_user_logs() {
    local dry_run=$1 directory minutes
    (( USER_LOG_DAYS > 0 )) || return 0
    directory=$(realpath -m -- "$USER_LOG_DIR")
    [[ -d "$directory" ]] || return 0
    minutes=$((USER_LOG_DAYS * 1440))
    if (( dry_run )); then
        find "$directory" -maxdepth 2 -type f \( -name '*.log' -o -name '*.log.*' \) \
            -mmin "+$minutes" -print
    else
        find "$directory" -maxdepth 2 -type f \( -name '*.log' -o -name '*.log.*' \) \
            -mmin "+$minutes" -print -delete
    fi
}
prune_system_logs() {
    local category=$1 days=$2 dry_run=$3 minutes
    local -a names=()
    (( days > 0 )) || return 0
    [[ -d "$log_dir" ]] || return 0
    minutes=$((days * 1440))
    case "$category" in
        cron) names=(-name 'cron.log.[0-9]*' -o -name 'cron.log-*' -o -name 'cron.[0-9]*') ;;
        login) names=(-name 'wtmp.[0-9]*' -o -name 'wtmp-*' -o -name 'btmp.[0-9]*' -o -name 'btmp-*') ;;
        system) names=(-name 'syslog.[0-9]*' -o -name 'auth.log.[0-9]*' -o
                      -name 'kern.log.[0-9]*' -o -name 'daemon.log.[0-9]*' -o
                      -name 'messages.[0-9]*') ;;
    esac
    if (( dry_run )); then
        find "$log_dir" -maxdepth 1 -type f \( "${names[@]}" \) -mmin "+$minutes" -print
    else
        find "$log_dir" -maxdepth 1 -type f \( "${names[@]}" \) -mmin "+$minutes" -print -delete
    fi
}
clean() {
    local force=$1 dry_run=$2
    local lock_fd
    require_system_access
    mkdir -p -- "$state_dir"
    chmod 0700 -- "$state_dir"
    exec {lock_fd}>"$state_dir/.cleanup.lock"
    flock -n "$lock_fd" || die 'Another cleanup round is already running.'
    load_config
    if [[ "$scope" == user ]]; then
        clean_history "$force" "$dry_run"
        prune_user_logs "$dry_run"
    else
        if (( JOURNAL_DAYS > 0 )); then
            if (( dry_run )); then
                printf 'Would run: %s --rotate --vacuum-time=%sd\n' "${PRIVACY_JOURNALCTL:-journalctl}" "$JOURNAL_DAYS"
            else
                "${PRIVACY_JOURNALCTL:-journalctl}" --rotate --vacuum-time="${JOURNAL_DAYS}d"
            fi
        fi
        prune_system_logs cron "$CRON_DAYS" "$dry_run"
        prune_system_logs login "$LOGIN_DAYS" "$dry_run"
        prune_system_logs system "$SYSTEM_DAYS" "$dry_run"
    fi
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
