# shellcheck shell=bash disable=SC2034,SC2154
# Shared privacy policy parsing and validation.
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
