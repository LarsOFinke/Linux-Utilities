#!/usr/bin/env bash
# Redragon H848 / Weltrend-XiiSound 040b:0897 – Ubuntu PipeWire/WirePlumber fix
#
# Installiert benötigte Werkzeuge und richtet Folgendes ein:
#   - reine analoge Stereo-Ausgabe (kein automatisches Duplex-/Mono-Eingangsprofil)
#   - PipeWire-Softwarelautstärke statt des fehlerhaften USB-Hardwaremixers
#   - beide ALSA-Regler "PCM" und "PCM 1" dauerhaft auf 100 %
#   - automatische Wiederherstellung nach Anmeldung und USB-Neuverbindung
#
# Aufruf:
#   chmod +x install-h848-audio-fix.sh
#   ./install-h848-audio-fix.sh
#
# Entfernen:
#   ./install-h848-audio-fix.sh --uninstall

set -Eeuo pipefail

readonly USB_ID="040b:0897"
readonly SINK_PREFIX="alsa_output.usb-XiiSound_Technology_Corporation_H848_"

readonly BIN_DIR="${HOME}/.local/bin"
readonly USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
readonly WP05_DIR="${HOME}/.config/wireplumber/wireplumber.conf.d"
readonly WP04_DIR="${HOME}/.config/wireplumber/main.lua.d"

readonly GUARD="${BIN_DIR}/h848-audio-guard"
readonly SERVICE="${USER_SYSTEMD_DIR}/h848-audio-guard.service"
readonly WP05_CONFIG="${WP05_DIR}/51-h848-soft-mixer.conf"
readonly WP04_CONFIG="${WP04_DIR}/51-h848-soft-mixer.lua"
readonly ORIGINAL_DIR="${HOME}/.local/state/h848-audio-fix/original"

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck disable=SC1091
source "$script_dir/h848_audio_lifecycle.sh"

if [[ "${EUID}" -eq 0 ]]; then
    die "Bitte als normaler Benutzer starten, nicht mit sudo. Das Skript fragt sudo nur für APT ab."
fi

case "${1:-}" in
    --uninstall)
        uninstall_fix
        ;;
    ""|--install)
        ;;
    *)
        die "Unbekannte Option: ${1}. Erlaubt: --install oder --uninstall"
        ;;
esac

[[ -r /etc/os-release ]] || die "/etc/os-release wurde nicht gefunden."
# shellcheck disable=SC1091
source /etc/os-release

if [[ "${ID:-}" != "ubuntu" && "${ID_LIKE:-}" != *ubuntu* && "${ID_LIKE:-}" != *debian* ]]; then
    die "Dieses Skript ist für Ubuntu bzw. APT-basierte Ubuntu-Derivate gedacht."
fi

command -v sudo >/dev/null 2>&1 || die "sudo ist nicht installiert."

log "Installiere benötigte Pakete …"
sudo -v
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    alsa-utils \
    pulseaudio-utils \
    pipewire-pulse \
    wireplumber \
    pavucontrol \
    usbutils

command -v pactl >/dev/null 2>&1 || die "pactl fehlt trotz Paketinstallation."
command -v amixer >/dev/null 2>&1 || die "amixer fehlt trotz Paketinstallation."
command -v wireplumber >/dev/null 2>&1 || die "WirePlumber fehlt trotz Paketinstallation."

if ! systemctl --user is-active --quiet pipewire.service; then
    log "Aktiviere PipeWire für den aktuellen Benutzer …"
    systemctl --user enable --now pipewire.socket pipewire-pulse.socket 2>/dev/null || true
fi

# Vorhandene Softwarelautstärke nach Möglichkeit erhalten.
PREVIOUS_VOLUME="50%"
CURRENT_SINK="$(
    LC_ALL=C pactl list short sinks 2>/dev/null |
        awk '$2 ~ /^alsa_output\.usb-XiiSound_Technology_Corporation_H848_/ &&
             $2 ~ /\.analog-stereo$/ { print $2; exit }'
)"
if [[ -n "${CURRENT_SINK}" ]]; then
    DETECTED_VOLUME="$(
        LC_ALL=C pactl get-sink-volume "${CURRENT_SINK}" 2>/dev/null |
            sed -n 's/.*front-left: [^/]*\/ *\([0-9]\+%\).*/\1/p' |
            head -n 1
    )"
    [[ -n "${DETECTED_VOLUME}" ]] && PREVIOUS_VOLUME="${DETECTED_VOLUME}"
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${HOME}/.local/state/h848-audio-fix/backups/${TIMESTAMP}"
mkdir -p "${BACKUP_DIR}"

backup_if_present() {
    local path="$1"
    local basename=${path##*/}
    local -a legacy_backups=()
    mkdir -p "${ORIGINAL_DIR}"
    if [[ ! -f "${ORIGINAL_DIR}/${basename}.present" &&
          ! -f "${ORIGINAL_DIR}/${basename}.absent" ]]; then
        shopt -s nullglob
        legacy_backups=("${HOME}"/.local/state/h848-audio-fix/backups/*/"${basename}.bak")
        shopt -u nullglob
        if [[ ! -f "${ORIGINAL_DIR}/.state-v2" ]] && (( ${#legacy_backups[@]} > 0 )); then
            cp -a -- "${legacy_backups[0]}" "${ORIGINAL_DIR}/${basename}.bak"
            touch "${ORIGINAL_DIR}/${basename}.present"
        elif [[ -e "$path" ]]; then
            cp -a -- "$path" "${ORIGINAL_DIR}/${basename}.bak"
            touch "${ORIGINAL_DIR}/${basename}.present"
        else
            touch "${ORIGINAL_DIR}/${basename}.absent"
        fi
    fi
    if [[ -e "${path}" ]]; then
        cp -a -- "${path}" "${BACKUP_DIR}/$(basename "${path}").bak"
        log "Sicherung erstellt: ${BACKUP_DIR}/$(basename "${path}").bak"
    fi
}

backup_if_present "${WP05_CONFIG}"
backup_if_present "${WP04_CONFIG}"
backup_if_present "${GUARD}"
backup_if_present "${SERVICE}"
touch "${ORIGINAL_DIR}/.state-v2"

WP_VERSION="$(
    wireplumber --version 2>/dev/null |
        grep -Eo '[0-9]+\.[0-9]+(\.[0-9]+)?' |
        head -n 1
)"
[[ -n "${WP_VERSION}" ]] || die "WirePlumber-Version konnte nicht ermittelt werden."

version_at_least() {
    local current="$1"
    local required="$2"
    [[ "$(printf '%s\n%s\n' "${required}" "${current}" | sort -V | head -n 1)" == "${required}" ]]
}

log "Erkannte WirePlumber-Version: ${WP_VERSION}"

if version_at_least "${WP_VERSION}" "0.5"; then
    mkdir -p "${WP05_DIR}"

    cat >"${WP05_CONFIG}" <<'WIREPLUMBER_05'
# Redragon H848 / XiiSound-Weltrend 040b:0897
monitor.alsa.rules = [
  {
    matches = [
      {
        device.name = "~alsa_card.usb-XiiSound_Technology_Corporation_H848_.*"
      }
    ]
    actions = {
      update-props = {
        device.profile = "output:analog-stereo"
        api.alsa.soft-mixer = true
        api.alsa.ignore-dB = true
        api.alsa.split-enable = false
      }
    }
  }
  {
    matches = [
      {
        node.name = "~alsa_input.usb-XiiSound_Technology_Corporation_H848_.*"
      }
    ]
    actions = {
      update-props = {
        node.disabled = true
      }
    }
  }
]
WIREPLUMBER_05

    log "WirePlumber-0.5-Konfiguration geschrieben: ${WP05_CONFIG}"
else
    mkdir -p "${WP04_DIR}"

    cat >"${WP04_CONFIG}" <<'WIREPLUMBER_04'
-- Redragon H848 / XiiSound-Weltrend 040b:0897

local h848_device_rule = {
  matches = {
    {
      { "device.name", "matches",
        "alsa_card.usb-XiiSound_Technology_Corporation_H848_*" },
    },
  },
  apply_properties = {
    ["device.profile"] = "output:analog-stereo",
    ["api.alsa.soft-mixer"] = true,
    ["api.alsa.ignore-dB"] = true,
    ["api.alsa.split-enable"] = false,
  },
}

local h848_input_rule = {
  matches = {
    {
      { "node.name", "matches",
        "alsa_input.usb-XiiSound_Technology_Corporation_H848_*" },
    },
  },
  apply_properties = {
    ["node.disabled"] = true,
  },
}

table.insert(alsa_monitor.rules, h848_device_rule)
table.insert(alsa_monitor.rules, h848_input_rule)
WIREPLUMBER_04

    log "WirePlumber-0.4-Konfiguration geschrieben: ${WP04_CONFIG}"
fi

mkdir -p "${BIN_DIR}" "${USER_SYSTEMD_DIR}"

cp -- "$script_dir/h848_audio_guard.sh" "$GUARD"

chmod 0755 "${GUARD}"

cat >"${SERVICE}" <<'SYSTEMD_UNIT'
[Unit]
Description=Redragon H848 stereo audio guard
After=pipewire.service pipewire-pulse.service wireplumber.service
Wants=pipewire.service pipewire-pulse.service wireplumber.service

[Service]
Type=simple
ExecStart=%h/.local/bin/h848-audio-guard --watch
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
SYSTEMD_UNIT

if lsusb -d "${USB_ID}" >/dev/null 2>&1; then
    log "USB-Gerät ${USB_ID} wurde erkannt."
else
    log "Hinweis: USB-Gerät ${USB_ID} ist momentan nicht angeschlossen."
    log "Die Konfiguration wird trotzdem installiert und beim nächsten Anschließen angewendet."
fi

log "Starte PipeWire und WirePlumber neu …"
restart_audio || die "WirePlumber/PipeWire konnte nach der Konfigurationsänderung nicht sauber neu gestartet werden."

systemctl --user enable --now h848-audio-guard.service

# Einmal sofort anwenden und beide PipeWire-Kanäle auf denselben
# Software-Lautstärkewert setzen.
"${GUARD}" --once
sleep 0.5

NEW_SINK="$(
    LC_ALL=C pactl list short sinks 2>/dev/null |
        awk '$2 ~ /^alsa_output\.usb-XiiSound_Technology_Corporation_H848_/ &&
             $2 ~ /\.analog-stereo$/ { print $2; exit }'
)"

if [[ -n "${NEW_SINK}" ]]; then
    pactl set-sink-volume "${NEW_SINK}" "${PREVIOUS_VOLUME}"
    pactl set-sink-mute "${NEW_SINK}" 0
    log "Linker und rechter Softwarekanal wurden gemeinsam auf ${PREVIOUS_VOLUME} gesetzt."
else
    log "Das H848 ist nicht verbunden; die Lautstärke wird beim nächsten Anschließen geregelt."
fi

log "Installation abgeschlossen."
log "Stereotest:"
log "  PULSE_SINK=${SINK_PREFIX}<Gerätename>.analog-stereo speaker-test -D pulse -c 2 -t wav"
log "Status des Guards:"
log "  systemctl --user status h848-audio-guard.service"
log "Protokoll:"
log "  journalctl --user -u h848-audio-guard.service -b"
