#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)
test_dir=$(mktemp -d)
managed_pid=
other_pid=
unrelated_pid=
cleanup() {
    [[ -z "$managed_pid" ]] || kill "$managed_pid" 2>/dev/null || true
    [[ -z "$other_pid" ]] || kill "$other_pid" 2>/dev/null || true
    [[ -z "$unrelated_pid" ]] || kill "$unrelated_pid" 2>/dev/null || true
    rm -rf -- "$test_dir"
}
trap cleanup EXIT

mkdir -p "$test_dir/bin" "$test_dir/archives"
cat >"$test_dir/bin/tcpdump" <<'MOCK_TCPDUMP'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$MOCK_TCPDUMP_ARGS"
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
export MOCK_TCPDUMP_ARGS="$test_dir/tcpdump.args"
export TCPDUMP_REGISTRY="$test_dir/network-capture.json"
script="$project_root/src/monitoring/network/scripts/capture_traffic.sh"

"$script"
first_pid=$(cat "$TCPDUMP_PID_FILE")
[[ "$(cat "$TCPDUMP_FILE")" == 'mock packets' ]]
if "$script" --port 70000 >/dev/null 2>&1; then
    echo 'Expected invalid port rejection' >&2
    exit 1
fi
[[ "$(cat "$TCPDUMP_PID_FILE")" == "$first_pid" ]]
if "$script" --subnet 999.0.0.0/24 >/dev/null 2>&1; then
    echo 'Expected invalid subnet rejection' >&2
    exit 1
fi
[[ "$(cat "$TCPDUMP_PID_FILE")" == "$first_pid" ]]
"$script" --port 53 --port 443 --subnet 10.0.0.0/8
printf '%s\n' -i mock0 -w "$TCPDUMP_FILE" '(' port 53 or port 443 ')' and '(' net 10.0.0.0/8 ')' >"$test_dir/expected.args"
cmp "$test_dir/expected.args" "$MOCK_TCPDUMP_ARGS"
"$script" --list >"$test_dir/listing"
rg -q 'default \[active\].*ports=53,443.*subnets=10.0.0.0/8' "$test_dir/listing"
TCPDUMP_FILE="$test_dir/other.pcap" TCPDUMP_PID_FILE="$test_dir/other.pid" \
    "$script" --name other --all-ports --subnet 192.168.0.0/16
other_pid=$(cat "$test_dir/other.pid")
"$script" --list >"$test_dir/listing"
rg -q 'other \[active\].*ports=all.*subnets=192.168.0.0/16' "$test_dir/listing"
"$script" --name other --stop
[[ ! -e "$test_dir/other.pid" ]]
wait "$other_pid" 2>/dev/null || true
other_pid=
"$script" --list >"$test_dir/listing"
rg -q 'other \[inactive\]' "$test_dir/listing"
if "$script" --name collision >/dev/null 2>&1; then
    echo 'Expected capture file ownership conflict' >&2
    exit 1
fi
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
# Concurrent profiles must retain both records, and detached captures must not
# inherit the registry lock (otherwise the second invocation never completes).
printf '%s\n' "$managed_pid" >"$TCPDUMP_PID_FILE"
"$script" --stop
managed_pid=
TCPDUMP_FILE="$test_dir/parallel-a.pcap" TCPDUMP_PID_FILE="$test_dir/parallel-a.pid" \
    timeout 15 "$script" --name parallel-a &
rotation_a=$!
TCPDUMP_FILE="$test_dir/parallel-b.pcap" TCPDUMP_PID_FILE="$test_dir/parallel-b.pid" \
    timeout 15 "$script" --name parallel-b &
rotation_b=$!
wait "$rotation_a"
managed_pid=$(cat "$test_dir/parallel-a.pid")
wait "$rotation_b"
other_pid=$(cat "$test_dir/parallel-b.pid")
"$script" --list >"$test_dir/listing"
rg -q 'parallel-a \[active\]' "$test_dir/listing"
rg -q 'parallel-b \[active\]' "$test_dir/listing"
"$script" --name parallel-a --stop
"$script" --name parallel-b --stop
managed_pid=
other_pid=
printf 'Capture tests passed\n'
