#!/usr/bin/env bash
set -Eeuo pipefail

repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../../.." && pwd)
test_root=$(mktemp -d)
trap 'rm -rf -- "$test_root"' EXIT
export SHELL_SCRIPTS_INSTALL_ROOT="$test_root/root"
mkdir -p "$SHELL_SCRIPTS_INSTALL_ROOT/srv/honey" "$SHELL_SCRIPTS_INSTALL_ROOT/var/log/fs-tracker"
target="$SHELL_SCRIPTS_INSTALL_ROOT/srv/honey/decoy.txt"
log="$SHELL_SCRIPTS_INSTALL_ROOT/var/log/fs-tracker/events.jsonl"
printf 'decoy\n' > "$target"
printf '{"old":true}\n' > "$log"

"$repository/setup.sh" --system --module canary
"$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/fs-tracker" --help >/dev/null
"$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/canary-configure" demo --path "$target" --log "$log"
"$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/canary-status" demo >/dev/null
"$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/canary-stop" demo
"$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/canary-start" demo
config="$SHELL_SCRIPTS_INSTALL_ROOT/etc/fs-tracker/demo.conf"
unit="$SHELL_SCRIPTS_INSTALL_ROOT/etc/systemd/system/fs-file-monitor-demo.service"
[[ -f "$config" && -f "$unit" ]]
printf '# local edit\n' >> "$config"
if "$repository/uninstall.sh" --system --module canary >/dev/null 2>&1; then
    echo 'Expected locally edited canary config to block uninstall' >&2
    exit 1
fi
sed -i '$d' "$config"
"$repository/uninstall.sh" --system --module canary
[[ ! -e "$config" && ! -e "$unit" ]]
[[ ! -e "$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/fs-tracker" ]]
[[ -f "$target" && -f "$log" ]]
printf 'Canary integration test passed\n'
