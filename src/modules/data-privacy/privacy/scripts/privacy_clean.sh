# shellcheck shell=bash disable=SC2034,SC2154
# Privacy cleanup actions.
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
