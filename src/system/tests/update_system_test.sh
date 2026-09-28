#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

export HOME="$test_dir/home"
export SHELL_SCRIPTS_INSTALL_ROOT="$test_dir/system-root"
export APT_TEST_LOG="$test_dir/apt.log"
export PATH="$test_dir/bin:$PATH"
mkdir -p "$HOME" "$test_dir/bin"

cat >"$test_dir/bin/apt" <<'MOCK_APT'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$APT_TEST_LOG"
if [[ "${APT_TEST_FAIL:-}" == "$1" ]]; then
    exit 42
fi
MOCK_APT
cat >"$test_dir/bin/sudo" <<'MOCK_SUDO'
#!/usr/bin/env bash
exec "$@"
MOCK_SUDO
chmod +x "$test_dir/bin/apt" "$test_dir/bin/sudo"

"$project_root/src/system/setup.sh" >/dev/null
command_path="$HOME/.local/bin/update-system"
[[ -x "$command_path" ]]

(cd /tmp && "$command_path")
printf 'update\nupgrade -y\n' >"$test_dir/expected.log"
cmp "$test_dir/expected.log" "$APT_TEST_LOG"

: >"$APT_TEST_LOG"
if APT_TEST_FAIL=update "$command_path" >"$test_dir/output" 2>&1; then
    printf 'Expected update failure\n' >&2
    exit 1
fi
printf 'update\n' >"$test_dir/expected.log"
cmp "$test_dir/expected.log" "$APT_TEST_LOG"
rg -q 'upgrade was skipped' "$test_dir/output"

: >"$APT_TEST_LOG"
if APT_TEST_FAIL=upgrade "$command_path" >"$test_dir/output" 2>&1; then
    printf 'Expected upgrade failure\n' >&2
    exit 1
fi
printf 'update\nupgrade -y\n' >"$test_dir/expected.log"
cmp "$test_dir/expected.log" "$APT_TEST_LOG"
rg -q 'apt upgrade failed' "$test_dir/output"

: >"$APT_TEST_LOG"
if "$command_path" unexpected >"$test_dir/output" 2>&1; then
    printf 'Expected argument rejection\n' >&2
    exit 1
fi
[[ ! -s "$APT_TEST_LOG" ]]

"$project_root/src/system/uninstall.sh" >/dev/null
[[ ! -e "$command_path" ]]

"$project_root/src/system/setup.sh" --system >/dev/null
system_command="$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/update-system"
[[ -x "$system_command" ]]
: >"$APT_TEST_LOG"
(cd /tmp && "$system_command")
printf 'update\nupgrade -y\n' >"$test_dir/expected.log"
cmp "$test_dir/expected.log" "$APT_TEST_LOG"
"$project_root/src/system/uninstall.sh" --system >/dev/null
[[ ! -e "$system_command" ]]

printf 'System update tests passed\n'
