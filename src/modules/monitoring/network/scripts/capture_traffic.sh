#!/usr/bin/env bash
set -Eeuo pipefail

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
umask 077

home_directory=$(getent passwd "$(id -u)" | cut -d: -f6)
[[ -n "$home_directory" ]] || { echo 'Could not determine home directory' >&2; exit 1; }

capture_file=${TCPDUMP_FILE:-$home_directory/tcpdump.pcap}
backup_dir=${TCPDUMP_BACKUP_DIR:-$(dirname "$home_directory")/backups/tcpdumps}
interface=${TCPDUMP_INTERFACE:-}
tcpdump_command=${TCPDUMP_COMMAND:-tcpdump}
pid_file=${TCPDUMP_PID_FILE:-${capture_file}.pid}
log_file="$(dirname "$capture_file")/tcpdump.log"

[[ "${tcpdump_command##*/}" == tcpdump ]] || {
    echo 'TCPDUMP_COMMAND must name a tcpdump executable' >&2
    exit 1
}
for command_name in tar bzip2 "$tcpdump_command" ip nohup flock realpath mktemp; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'Required command not found: %s\n' "$command_name" >&2
        exit 1
    }
done

[[ -n "$interface" ]] || interface=$(ip route show default | awk 'NR == 1 { print $5; exit }')
[[ -n "$interface" ]] || { echo 'Set TCPDUMP_INTERFACE; no default route was found' >&2; exit 1; }
[[ -d "$(dirname "$capture_file")" ]] || { echo 'Capture directory does not exist' >&2; exit 1; }

capture_file=$(realpath -m -- "$capture_file")
pid_file=$(realpath -m -- "$pid_file")
backup_dir=$(realpath -m -- "$backup_dir")
[[ "$pid_file" != "$capture_file" ]] || { echo 'PID file must differ from capture file' >&2; exit 1; }
mkdir -p -- "$backup_dir"
chmod 0700 -- "$backup_dir"

exec {lock_fd}>"${pid_file}.lock"
flock -n "$lock_fd" || { echo 'Capture rotation is already running' >&2; exit 1; }

managed_tcpdump() {
    local pid=$1
    local -a argv=()
    local index
    [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/cmdline" ]] || return 1
    mapfile -d '' -t argv <"/proc/$pid/cmdline"
    [[ "${argv[0]##*/}" == tcpdump ]] || return 1
    for ((index = 1; index < ${#argv[@]} - 1; index++)); do
        [[ "${argv[index]}" == -w && "${argv[index + 1]}" == "$capture_file" ]] && return 0
    done
    return 1
}

if [[ -f "$pid_file" ]]; then
    read -r old_pid <"$pid_file" || true
    if managed_tcpdump "${old_pid:-}"; then
        kill "$old_pid"
        for ((attempt = 0; attempt < 30; attempt++)); do
            managed_tcpdump "$old_pid" || break
            sleep 1
        done
        managed_tcpdump "$old_pid" && { echo 'Managed tcpdump did not stop' >&2; exit 1; }
    elif [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" 2>/dev/null; then
        echo 'PID file names an unrelated live process; refusing to rotate' >&2
        exit 1
    fi
    rm -f -- "$pid_file"
fi

if [[ -f "$capture_file" ]]; then
    stamp=$(date +%Y-%m-%dT%H%M%S.%N)
    archive="$backup_dir/tcpdump_${stamp}_$BASHPID.pcap.tar.bz2"
    temp_archive=$(mktemp "$backup_dir/.tcpdump.XXXXXXXX.tar.bz2")
    if ! tar -cjf "$temp_archive" -C "$(dirname "$capture_file")" "$(basename "$capture_file")" ||
       ! tar -tjf "$temp_archive" >/dev/null; then
        rm -f -- "$temp_archive"
        echo 'Capture archive failed; original pcap remains available' >&2
        exit 1
    fi
    mv -- "$temp_archive" "$archive"
    rm -- "$capture_file"
fi

nohup "$tcpdump_command" -i "$interface" -w "$capture_file" 'port 22 or port 80 or port 443' \
    {lock_fd}>&- >>"$log_file" 2>&1 </dev/null &
new_pid=$!
sleep 0.3
if ! managed_tcpdump "$new_pid"; then
    echo "tcpdump failed to start; inspect $log_file" >&2
    exit 1
fi
printf '%s\n' "$new_pid" >"$pid_file"
printf 'Started tcpdump (PID %s) on %s; writing %s\n' "$new_pid" "$interface" "$capture_file"
