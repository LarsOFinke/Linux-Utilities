#!/usr/bin/env bash
# Hält das H848 auf dem funktionierenden Ausgabeprofil und öffnet beide
# voneinander getrennten Hardwarekanäle vollständig.

set -u

log() {
    printf '[h848-audio-guard] %s\n' "$*"
}

wait_for_pactl() {
    local attempt
    for ((attempt = 0; attempt < 30; attempt++)); do
        pactl info >/dev/null 2>&1 && return 0
        sleep 0.2
    done
    return 1
}

find_pipewire_card() {
    LC_ALL=C pactl list short cards 2>/dev/null |
        awk '$2 ~ /^alsa_card\.usb-XiiSound_Technology_Corporation_H848_/ {
            print $2
            exit
        }'
}

find_pipewire_sink() {
    LC_ALL=C pactl list short sinks 2>/dev/null |
        awk '$2 ~ /^alsa_output\.usb-XiiSound_Technology_Corporation_H848_/ &&
             $2 ~ /\.analog-stereo$/ {
            print $2
            exit
        }'
}

find_alsa_card_index() {
    awk '
        /^[[:space:]]*[0-9]+[[:space:]]+\[/ && /H848/ {
            print $1
            exit
        }
    ' /proc/asound/cards 2>/dev/null
}

active_profile() {
    local card="$1"

    LC_ALL=C pactl list cards 2>/dev/null |
        awk -v target="${card}" '
            $1 == "Name:" {
                selected = ($2 == target)
            }
            selected && $1 == "Active" && $2 == "Profile:" {
                print $3
                exit
            }
        '
}

apply_h848_fix() {
    wait_for_pactl || return 0

    local card profile sink default_sink alsa_index
    card="$(find_pipewire_card)"
    [[ -n "${card}" ]] || return 0

    profile="$(active_profile "${card}")"
    if [[ "${profile}" != "output:analog-stereo" ]]; then
        log "Setze Profil auf output:analog-stereo (vorher: ${profile:-unbekannt})"
        pactl set-card-profile "${card}" output:analog-stereo >/dev/null 2>&1 || true
        sleep 0.4
    fi

    alsa_index="$(find_alsa_card_index)"
    if [[ -n "${alsa_index}" ]]; then
        # Der USB-Chip stellt die beiden Ohrkanäle als getrennte Controls bereit.
        amixer -q -c "${alsa_index}" sset 'PCM',0 100% unmute >/dev/null 2>&1 || true
        amixer -q -c "${alsa_index}" sset 'PCM',1 100% unmute >/dev/null 2>&1 || true
    fi

    sink="$(find_pipewire_sink)"
    if [[ -n "${sink}" ]]; then
        pactl set-sink-mute "${sink}" 0 >/dev/null 2>&1 || true

        default_sink="$(pactl get-default-sink 2>/dev/null || true)"
        if [[ "${default_sink}" != "${sink}" ]]; then
            log "Setze H848 als Standardausgabe."
            pactl set-default-sink "${sink}" >/dev/null 2>&1 || true
        fi
    fi
}

case "${1:---watch}" in
    --once)
        apply_h848_fix
        exit 0
        ;;
    --watch)
        ;;
    *)
        printf 'Aufruf: %s [--once|--watch]\n' "$0" >&2
        exit 2
        ;;
esac

apply_h848_fix

# Profiländerungen und USB-Neuverbindungen erzeugen Card-Events.
# Wenn PipeWire neu startet, endet pactl subscribe; systemd startet diesen
# Guard anschließend automatisch neu.
LC_ALL=C pactl subscribe 2>/dev/null |
    while IFS= read -r event; do
        case "${event}" in
            *"on card"*|*"on server"*)
                sleep 0.3
                apply_h848_fix
                ;;
        esac
    done
