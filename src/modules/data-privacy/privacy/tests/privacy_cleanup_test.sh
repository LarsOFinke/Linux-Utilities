#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../../.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
export HOME="$test_dir/home"
export MOCK_CRONTAB="$test_dir/crontab"
export PRIVACY_ROOT="$test_dir/system-root"
export PRIVACY_JOURNALCTL="$test_dir/bin/journalctl"
mkdir -p "$HOME/.local/state" "$HOME/.local/bin" "$test_dir/bin" \
    "$PRIVACY_ROOT/var/log" "$PRIVACY_ROOT/usr/local/bin"
script="$project_root/src/modules/data-privacy/privacy/scripts/privacy_cleanup.sh"
install -m 0755 "$script" "$HOME/.local/bin/privacy-cleanup"
install -m 0755 "$script" "$PRIVACY_ROOT/usr/local/bin/privacy-cleanup"
for helper in privacy_policy.sh privacy_schedule.sh privacy_clean.sh; do
    install -m 0644 "$project_root/src/modules/data-privacy/privacy/scripts/$helper" "$HOME/.local/bin/$helper"
    install -m 0644 "$project_root/src/modules/data-privacy/privacy/scripts/$helper" "$PRIVACY_ROOT/usr/local/bin/$helper"
done
for action in configure status run scheduled uninstall-schedule; do
    install -m 0755 "$project_root/src/modules/data-privacy/privacy/scripts/privacy_workflow.sh" "$HOME/.local/bin/privacy-$action"
    install -m 0755 "$project_root/src/modules/data-privacy/privacy/scripts/privacy_workflow.sh" "$PRIVACY_ROOT/usr/local/bin/privacy-$action"
done

cat >"$test_dir/bin/crontab" <<'MOCK_CRONTAB'
#!/usr/bin/env bash
if [[ "$1" == -l ]]; then
    [[ -f "$MOCK_CRONTAB" ]] || exit 1
    cat "$MOCK_CRONTAB"
elif [[ "$1" == - ]]; then
    cat >"$MOCK_CRONTAB"
else
    cp -- "$1" "$MOCK_CRONTAB"
fi
MOCK_CRONTAB
cat >"$test_dir/bin/journalctl" <<'MOCK_JOURNALCTL'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$PRIVACY_ROOT/journal-calls"
MOCK_JOURNALCTL
chmod +x "$test_dir/bin/crontab" "$test_dir/bin/journalctl"
export PATH="$test_dir/bin:$PATH"

printf '0 1 * * * echo existing\n' >"$MOCK_CRONTAB"
printf '\n\n\n\n\n' | "$HOME/.local/bin/privacy-configure"
[[ -f "$HOME/.config/privacy-cleanup/user.cfg" ]]
[[ -f "$HOME/.local/bin/privacy-cleanup" ]]
[[ "$(rg -c 'privacy-cleanup user' "$MOCK_CRONTAB")" == 1 ]]
rg -q 'echo existing' "$MOCK_CRONTAB"

printf 'private command\n' >"$HOME/.bash_history"
printf 'old log\n' >"$HOME/.local/state/app.log"
touch -d '40 days ago' "$HOME/.local/state/app.log"
"$HOME/.local/bin/privacy-run" --dry-run >"$test_dir/dry-run.txt"
[[ -s "$HOME/.bash_history" && -f "$HOME/.local/state/app.log" ]]
"$HOME/.local/bin/privacy-scheduled"
[[ -s "$HOME/.bash_history" && ! -e "$HOME/.local/state/app.log" ]]
"$HOME/.local/bin/privacy-run" --yes
[[ ! -s "$HOME/.bash_history" ]]

printf '\n\n\n\n\n\n' | "$PRIVACY_ROOT/usr/local/bin/privacy-configure" --system
[[ -f "$PRIVACY_ROOT/etc/privacy-cleanup/system.cfg" ]]
rg -q 'managed by shell-scripts privacy' "$PRIVACY_ROOT/etc/cron.d/privacy-cleanup"
printf 'old\n' >"$PRIVACY_ROOT/var/log/syslog.1"
printf 'old\n' >"$PRIVACY_ROOT/var/log/cron.log.1"
printf 'old\n' >"$PRIVACY_ROOT/var/log/wtmp.1"
printf 'active\n' >"$PRIVACY_ROOT/var/log/syslog"
touch -d '100 days ago' "$PRIVACY_ROOT/var/log/syslog.1" \
    "$PRIVACY_ROOT/var/log/cron.log.1" "$PRIVACY_ROOT/var/log/wtmp.1"
"$PRIVACY_ROOT/usr/local/bin/privacy-run" --system --dry-run >"$test_dir/system-dry-run.txt"
[[ -f "$PRIVACY_ROOT/var/log/syslog.1" ]]
"$PRIVACY_ROOT/usr/local/bin/privacy-run" --system --yes
[[ ! -e "$PRIVACY_ROOT/var/log/syslog.1" ]]
[[ ! -e "$PRIVACY_ROOT/var/log/cron.log.1" ]]
[[ ! -e "$PRIVACY_ROOT/var/log/wtmp.1" ]]
[[ -f "$PRIVACY_ROOT/var/log/syslog" ]]
rg -q -- '--rotate --vacuum-time=14d' "$PRIVACY_ROOT/journal-calls"

printf 'Privacy tests passed\n'
