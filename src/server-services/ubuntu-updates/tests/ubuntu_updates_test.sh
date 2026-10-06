#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
export HOME="$test_dir/home"
export SHELL_SCRIPTS_INSTALL_ROOT="$test_dir/root"
export UU_ROOT="$SHELL_SCRIPTS_INSTALL_ROOT"
export MOCK_TIMER_DIR="$test_dir/timers"
export MOCK_CALLS="$test_dir/calls"
REAL_APT_CONFIG=$(command -v apt-config)
export REAL_APT_CONFIG
mkdir -p "$HOME" "$UU_ROOT/etc/apt/apt.conf.d" "$UU_ROOT/etc" "$test_dir/bin" "$MOCK_TIMER_DIR"
printf 'ID=ubuntu\n' > "$UU_ROOT/etc/os-release"
printf 'disabled\n' > "$MOCK_TIMER_DIR/apt-daily.timer"
printf 'disabled\n' > "$MOCK_TIMER_DIR/apt-daily-upgrade.timer"
printf 'inactive\n' > "$MOCK_TIMER_DIR/apt-daily.timer.active"
printf 'inactive\n' > "$MOCK_TIMER_DIR/apt-daily-upgrade.timer.active"

cat > "$test_dir/bin/systemctl" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
action=$1
shift
case "$action" in
    is-enabled) cat "$MOCK_TIMER_DIR/$1" ;;
    is-active) cat "$MOCK_TIMER_DIR/$1.active" ;;
    enable)
        [[ "${MOCK_FAIL_ENABLE:-0}" != 1 ]] || exit 1
        now=false
        if [[ "$1" == --now ]]; then now=true; shift; fi
        for unit in "$@"; do printf 'enabled\n' > "$MOCK_TIMER_DIR/$unit"; done
        if [[ "$now" == true ]]; then
            for unit in "$@"; do printf 'active\n' > "$MOCK_TIMER_DIR/$unit.active"; done
        fi
        ;;
    disable)
        [[ "${MOCK_FAIL_DISABLE:-0}" != 1 ]] || exit 1
        now=false
        if [[ "$1" == --now ]]; then now=true; shift; fi
        for unit in "$@"; do printf 'disabled\n' > "$MOCK_TIMER_DIR/$unit"; done
        if [[ "$now" == true ]]; then
            for unit in "$@"; do printf 'inactive\n' > "$MOCK_TIMER_DIR/$unit.active"; done
        fi
        ;;
    start) printf 'active\n' > "$MOCK_TIMER_DIR/$1.active" ;;
    stop) printf 'inactive\n' > "$MOCK_TIMER_DIR/$1.active" ;;
    *) exit 2 ;;
esac
MOCK
cat > "$test_dir/bin/apt-config" <<'MOCK'
#!/usr/bin/env bash
[[ "${MOCK_FAIL_CONFIG:-0}" != 1 ]] || exit 1
if [[ "${1:-}" == -c ]]; then
    [[ -s "$2" ]] || exit 1
fi
"$REAL_APT_CONFIG" "$@" >/dev/null
MOCK
cat > "$test_dir/bin/dpkg-query" <<'MOCK'
#!/usr/bin/env bash
printf 'install ok installed\n'
MOCK
cat > "$test_dir/bin/apt-get" <<'MOCK'
#!/usr/bin/env bash
printf 'apt-get %s\n' "$*" >> "$MOCK_CALLS"
MOCK
cat > "$test_dir/bin/unattended-upgrade" <<'MOCK'
#!/usr/bin/env bash
printf 'unattended-upgrade %s\n' "$*" >> "$MOCK_CALLS"
MOCK
cat > "$test_dir/bin/journalctl" <<'MOCK'
#!/usr/bin/env bash
exit 0
MOCK
cat > "$test_dir/bin/sudo" <<'MOCK'
#!/usr/bin/env bash
echo 'Unexpected sudo' >&2
exit 1
MOCK
chmod +x "$test_dir/bin"/*
export PATH="$test_dir/bin:$PATH"

if python3 "$project_root/installer/main.py" install --module ubuntu-updates >/dev/null 2>&1; then
    echo 'Expected user-scope installation to be refused' >&2
    exit 1
fi
"$project_root/scripts/setup.sh" --module ubuntu-updates
command="$UU_ROOT/usr/local/bin/ubuntu-updates"
policy="$UU_ROOT/etc/apt/apt.conf.d/99-shell-scripts-unattended-upgrades"
state="$UU_ROOT/var/lib/shell-scripts/ubuntu-updates/state.cfg"
[[ -x "$command" && ! -e "$policy" ]]
cd /tmp
"$UU_ROOT/usr/local/bin/ubuntu-updates-status" >/dev/null

MOCK_FAIL_ENABLE=1 "$command" configure --updates security --reboot off --yes >/dev/null 2>&1 && {
    echo 'Expected failed timer activation' >&2
    exit 1
}
[[ ! -e "$policy" && ! -e "$state" ]]
[[ $(cat "$MOCK_TIMER_DIR/apt-daily.timer") == disabled ]]
[[ $(cat "$MOCK_TIMER_DIR/apt-daily.timer.active") == inactive ]]

"$UU_ROOT/usr/local/bin/ubuntu-updates-configure" --updates security --reboot off --yes
[[ -f "$policy" && -f "$state" ]]
[[ $(stat -c %a "$state") == 600 ]]
[[ $(cat "$MOCK_TIMER_DIR/apt-daily.timer") == enabled ]]
[[ $(cat "$MOCK_TIMER_DIR/apt-daily.timer.active") == active ]]
if rg -q '\$\{distro_codename\}-updates' "$policy"; then
    echo 'Security policy unexpectedly includes regular updates' >&2
    exit 1
fi

cp -- "$policy" "$test_dir/first-policy"
MOCK_FAIL_ENABLE=1 "$command" configure --updates all --reboot off --yes >/dev/null 2>&1 && {
    echo 'Expected failed reconfiguration to roll back' >&2
    exit 1
}
cmp -- "$test_dir/first-policy" "$policy"
status_output=$("$UU_ROOT/usr/local/bin/ubuntu-updates-status")
[[ "$status_output" == *'active and verified'* ]]

"$command" configure --updates all --reboot 03:30 --yes
rg -q 'Automatic-Reboot-Time "03:30"' "$policy"
rg -q '\$\{distro_codename\}-updates' "$policy"
[[ $(find "$UU_ROOT/var/lib/shell-scripts/ubuntu-updates" -name 'revision.*.cfg' | wc -l) -ge 1 ]]

cp -- "$policy" "$test_dir/saved-policy"
printf '// local edit\n' >> "$policy"
if "$command" restore --yes >/dev/null 2>&1; then
    echo 'Expected changed policy to be preserved' >&2
    exit 1
fi
if "$project_root/scripts/uninstall.sh" --system --module ubuntu-updates >/dev/null 2>&1; then
    echo 'Expected uninstall to refuse changed policy' >&2
    exit 1
fi
cp -- "$test_dir/saved-policy" "$policy"
if MOCK_FAIL_DISABLE=1 "$command" restore --yes >/dev/null 2>&1; then
    echo 'Expected failed timer restore to preserve the policy' >&2
    exit 1
fi
cmp -- "$test_dir/saved-policy" "$policy"
[[ -f "$state" && $(cat "$MOCK_TIMER_DIR/apt-daily.timer") == enabled ]]
"$command" dry-run
"$command" run --yes
rg -q 'unattended-upgrade -v --dry-run' "$MOCK_CALLS"
rg -q 'apt-get update' "$MOCK_CALLS"

"$project_root/scripts/uninstall.sh" --system --module ubuntu-updates
[[ ! -e "$command" && ! -e "$policy" && ! -e "$state" ]]
[[ $(cat "$MOCK_TIMER_DIR/apt-daily.timer") == disabled ]]
[[ $(cat "$MOCK_TIMER_DIR/apt-daily-upgrade.timer") == disabled ]]
[[ $(cat "$MOCK_TIMER_DIR/apt-daily.timer.active") == inactive ]]
[[ $(cat "$MOCK_TIMER_DIR/apt-daily-upgrade.timer.active") == inactive ]]

printf 'unmanaged\n' > "$policy"
"$project_root/scripts/setup.sh" --system --module ubuntu-updates >/dev/null
if "$command" configure --updates security --reboot off --yes >/dev/null 2>&1; then
    echo 'Expected unmanaged policy to be preserved' >&2
    exit 1
fi
[[ $(cat "$policy") == unmanaged ]]
"$project_root/scripts/uninstall.sh" --system --module ubuntu-updates >/dev/null
[[ $(cat "$policy") == unmanaged ]]

rm -- "$policy"
legacy="$UU_ROOT/etc/apt/apt.conf.d/99-cybersec-auto-updates"
printf 'legacy\n' > "$legacy"
"$project_root/scripts/setup.sh" --module ubuntu-updates >/dev/null
if "$command" configure --updates security --reboot off --yes >/dev/null 2>&1; then
    echo 'Expected legacy policy migration to require explicit action' >&2
    exit 1
fi
[[ $(cat "$legacy") == legacy && ! -e "$state" ]]
"$project_root/scripts/uninstall.sh" --system --module ubuntu-updates >/dev/null
printf 'Ubuntu updates tests passed\n'
