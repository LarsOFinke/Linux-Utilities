# shellcheck shell=bash disable=SC2034,SC2154
# Shared H848 logging, audio restart, and original-file restoration.
log() {
    printf '[H848-Fix] %s\n' "$*"
}

die() {
    printf '[H848-Fix] FEHLER: %s\n' "$*" >&2
    exit 1
}

restart_audio() {
    systemctl --user daemon-reload

    # PipeWire ist teilweise socket-aktiviert; ein fehlgeschlagener expliziter
    # Neustart dieser beiden Units ist daher nicht automatisch kritisch.
    systemctl --user restart \
        pipewire.service \
        pipewire-pulse.service 2>/dev/null || true

    # WirePlumber muss die neue Regel erfolgreich laden können.
    systemctl --user restart wireplumber.service || return 1

    for _ in {1..30}; do
        pactl info >/dev/null 2>&1 && return 0
        sleep 0.2
    done

    return 1
}

restore_original() {
    local path="$1"
    local basename=${path##*/}
    local -a legacy_backups=()
    shopt -s nullglob
    legacy_backups=("${HOME}"/.local/state/h848-audio-fix/backups/*/"${basename}.bak")
    shopt -u nullglob

    if [[ -f "${ORIGINAL_DIR}/${basename}.present" ]]; then
        mkdir -p -- "$(dirname "$path")"
        cp -a -- "${ORIGINAL_DIR}/${basename}.bak" "$path"
    elif [[ -f "${ORIGINAL_DIR}/${basename}.absent" ]]; then
        rm -f -- "$path"
    elif [[ ! -f "${ORIGINAL_DIR}/.state-v2" ]] && (( ${#legacy_backups[@]} > 0 )); then
        mkdir -p -- "$(dirname "$path")"
        cp -a -- "${legacy_backups[0]}" "$path"
    else
        rm -f -- "$path"
    fi
    rm -f -- "${ORIGINAL_DIR}/${basename}.present" "${ORIGINAL_DIR}/${basename}.absent"
}

uninstall_fix() {
    log "Entferne die H848-Konfiguration …"

    systemctl --user disable --now h848-audio-guard.service 2>/dev/null || true
    restore_original "${SERVICE}"
    restore_original "${GUARD}"
    restore_original "${WP05_CONFIG}"
    restore_original "${WP04_CONFIG}"
    mkdir -p -- "${ORIGINAL_DIR}"
    touch "${ORIGINAL_DIR}/.state-v2"
    systemctl --user daemon-reload
    restart_audio || true

    log "Fix entfernt. Installierte APT-Pakete wurden bewusst nicht deinstalliert."
    exit 0
}
