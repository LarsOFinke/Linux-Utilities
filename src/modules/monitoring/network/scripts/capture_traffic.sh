#!/usr/bin/env bash
set -Eeuo pipefail

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
umask 077

home_directory=$(getent passwd "$(id -u)" | cut -d: -f6)
[[ -n "$home_directory" ]] || { echo 'Could not determine home directory' >&2; exit 1; }

backup_dir=${TCPDUMP_BACKUP_DIR:-$(dirname "$home_directory")/backups/tcpdumps}
interface=${TCPDUMP_INTERFACE:-}
tcpdump_command=${TCPDUMP_COMMAND:-tcpdump}
registry_command="$(dirname "${BASH_SOURCE[0]}")/capture_registry.py"
profile=default
list_profiles=0
stop_profile=0

ports=()
subnets=()
if [[ -n ${TCPDUMP_PORTS:-} ]]; then
    IFS=, read -r -a ports <<<"$TCPDUMP_PORTS"
else
    ports=(22 80 443)
fi
if [[ -n ${TCPDUMP_SUBNETS:-} ]]; then
    IFS=, read -r -a subnets <<<"$TCPDUMP_SUBNETS"
fi
explicit_ports=0
while (( $# )); do
    case $1 in
        --port)
            (( $# >= 2 )) || { echo '--port needs a number' >&2; exit 2; }
            if (( explicit_ports == 0 )); then ports=(); explicit_ports=1; fi
            ports+=("$2"); shift 2 ;;
        --subnet)
            (( $# >= 2 )) || { echo '--subnet needs an IPv4 CIDR' >&2; exit 2; }
            subnets+=("$2"); shift 2 ;;
        --all-ports)
            ports=(); explicit_ports=1; shift ;;
        --name)
            (( $# >= 2 )) || { echo '--name needs a profile name' >&2; exit 2; }
            profile=$2; shift 2 ;;
        --list)
            list_profiles=1; shift ;;
        --stop)
            stop_profile=1; shift ;;
        --help)
            echo 'Usage: capture-traffic [--name NAME] [--port 1-65535]... [--subnet IPv4/CIDR]... [--all-ports] [--list|--stop]'
            exit 0 ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
    esac
done
[[ $profile =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]] || { echo 'Invalid capture profile name' >&2; exit 2; }
# All profiles share one registry. Hold its lock through ownership checks,
# process changes, and publication; stop/list use the same lock as rotation.
registry_lock=$(python3 "$registry_command" lock-path)
[[ ! -L "$registry_lock" && -f "$registry_lock" ]] || { echo 'Unsafe capture registry lock' >&2; exit 1; }
exec {registry_fd}<>"$registry_lock"
flock -x "$registry_fd"
if (( list_profiles )); then
    exec python3 "$registry_command" list
fi
if (( stop_profile )); then
    exec python3 "$registry_command" stop "$profile"
fi
suffix=
[[ $profile == default ]] || suffix="-$profile"
capture_file=${TCPDUMP_FILE:-$home_directory/tcpdump${suffix}.pcap}
pid_file=${TCPDUMP_PID_FILE:-${capture_file}.pid}
log_file="$(dirname "$capture_file")/tcpdump${suffix}.log"

filter=()
for port in "${ports[@]}"; do
    if [[ ! $port =~ ^[0-9]+$ ]] || (( 10#$port < 1 || 10#$port > 65535 )); then
        printf 'Invalid port: %s\n' "$port" >&2; exit 2;
    fi
done
for subnet in "${subnets[@]}"; do
    [[ $subnet =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/([0-9]|[12][0-9]|3[0-2])$ ]] || {
        printf 'Invalid IPv4 CIDR: %s\n' "$subnet" >&2; exit 2;
    }
    IFS=./ read -r octet1 octet2 octet3 octet4 prefix <<<"$subnet"
    [[ -n $prefix ]] || { printf 'Invalid IPv4 CIDR: %s\n' "$subnet" >&2; exit 2; }
    for octet in "$octet1" "$octet2" "$octet3" "$octet4"; do
        (( 10#$octet <= 255 )) || { printf 'Invalid IPv4 CIDR: %s\n' "$subnet" >&2; exit 2; }
    done
done
if (( ${#ports[@]} )); then
    filter+=( '(' )
    for port in "${ports[@]}"; do
        (( ${#filter[@]} == 1 )) || filter+=( or )
        filter+=( port "$port" )
    done
    filter+=( ')' )
fi
if (( ${#subnets[@]} )); then
    (( ${#filter[@]} == 0 )) || filter+=( and )
    filter+=( '(' )
    for subnet in "${subnets[@]}"; do
        [[ ${filter[-1]} == '(' ]] || filter+=( or )
        filter+=( net "$subnet" )
    done
    filter+=( ')' )
fi

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
python3 "$registry_command" check "$profile" "$capture_file" "$pid_file"
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

nohup "$tcpdump_command" -i "$interface" -w "$capture_file" "${filter[@]}" \
    {lock_fd}>&- {registry_fd}>&- >>"$log_file" 2>&1 </dev/null &
new_pid=$!
sleep 0.3
if ! managed_tcpdump "$new_pid"; then
    echo "tcpdump failed to start; inspect $log_file" >&2
    exit 1
fi
printf '%s\n' "$new_pid" >"$pid_file"
if ! python3 "$registry_command" record "$profile" "$new_pid" "$capture_file" "$pid_file" "$interface" \
    "${ports[*]}" "${subnets[*]}"; then
    kill "$new_pid" 2>/dev/null || true
    rm -f -- "$pid_file"
    exit 1
fi
printf 'Started tcpdump (PID %s) on %s; writing %s\n' "$new_pid" "$interface" "$capture_file"
