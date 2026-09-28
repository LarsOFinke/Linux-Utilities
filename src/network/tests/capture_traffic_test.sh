#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
test_dir=$(mktemp -d)
managed_pid=
unrelated_pid=
cleanup() {
    [[ -z "$managed_pid" ]] || kill "$managed_pid" 2>/dev/null || true
    [[ -z "$unrelated_pid" ]] || kill "$unrelated_pid" 2>/dev/null || true
    rm -rf -- "$test_dir"
}
trap cleanup EXIT

mkdir -p "$test_dir/bin" "$test_dir/archives"
cat >"$test_dir/bin/tcpdump" <<'MOCK_TCPDUMP'
#!/usr/bin/env bash
output=
while (( $# > 0 )); do
    if [[ "$1" == -w ]]; then
        output=$2
        break
    fi
    shift
done
[[ -n "$output" ]] || exit 2
exec -a tcpdump bash -c '
    printf "mock packets\n" >"$2"
    trap "exit 0" TERM
    while :; do sleep 0.1; done
' -- -w "$output"
MOCK_TCPDUMP
chmod +x "$test_dir/bin/tcpdump"

export TCPDUMP_COMMAND="$test_dir/bin/tcpdump"
export TCPDUMP_INTERFACE=mock0
export TCPDUMP_FILE="$test_dir/traffic.pcap"
export TCPDUMP_PID_FILE="$test_dir/traffic.pid"
export TCPDUMP_BACKUP_DIR="$test_dir/archives"
script="$project_root/src/network/scripts/capture_traffic.sh"

"$script"
first_pid=$(cat "$TCPDUMP_PID_FILE")
[[ "$(cat "$TCPDUMP_FILE")" == 'mock packets' ]]
"$script"
managed_pid=$(cat "$TCPDUMP_PID_FILE")
[[ "$first_pid" != "$managed_pid" ]]
shopt -s nullglob
archives=("$TCPDUMP_BACKUP_DIR"/tcpdump_*.pcap.tar.bz2)
[[ ${#archives[@]} -eq 1 ]]
[[ "$(tar -xOjf "${archives[0]}" traffic.pcap)" == 'mock packets' ]]

sleep 30 &
unrelated_pid=$!
printf '%s\n' "$unrelated_pid" >"$TCPDUMP_PID_FILE"
if "$script" >/dev/null 2>&1; then
    echo 'Expected refusal to stop an unrelated process' >&2
    exit 1
fi
kill -0 "$unrelated_pid"
kill -0 "$managed_pid"
printf 'Capture tests passed\n'
