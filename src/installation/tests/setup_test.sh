#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
export HOME="$test_dir/home"
export SHELL_SCRIPTS_INSTALL_ROOT="$test_dir/system-root"
export PRIVACY_ROOT="$SHELL_SCRIPTS_INSTALL_ROOT"
export MOCK_CRONTAB="$test_dir/crontab"
mkdir -p "$HOME" "$test_dir/bin" "$test_dir/homes/sampleuser"

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
chmod +x "$test_dir/bin/crontab"
export PATH="$test_dir/bin:$PATH"

"$project_root/setup.sh" --module backup --module privacy
registry="$HOME/.local/state/shell-scripts/registry.json"
[[ -x "$HOME/.local/bin/backup-home-cron" && -x "$HOME/.local/bin/privacy-cleanup" ]]
[[ -f "$HOME/.local/bin/backup_home_common.sh" ]]
rg -q 'shell-scripts setup' "$HOME/.profile"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert set(d["modules"]) == {"backup","privacy"}; assert d["modules"]["backup"]["commands"]["backup-home"]["source"].endswith("src/backup/scripts/backup_home.sh"); assert d["modules"]["privacy"]["setup_script"].endswith("src/privacy/setup.sh")' "$registry"

printf 'content\n' >"$test_dir/homes/sampleuser/data.txt"
BACKUP_SOURCE_ROOT="$test_dir/homes" BACKUP_ROOT="$test_dir/archives" \
    PATH="$HOME/.local/bin:$PATH" bash -c 'cd /tmp && backup-home-cron sampleuser'
[[ -L "$test_dir/archives/sampleuser/latest.tar.bz2" ]]

printf '0 1 * * * echo existing\n' >"$MOCK_CRONTAB"
printf '\n\n\n\n\n' | "$HOME/.local/bin/privacy-cleanup" configure
PATH="$HOME/.local/bin:$PATH" bash -c 'cd /tmp && privacy-cleanup status' >/dev/null
rg -q 'privacy-cleanup user' "$MOCK_CRONTAB"
"$project_root/src/privacy/uninstall.sh"
[[ ! -e "$HOME/.local/bin/privacy-cleanup" && -x "$HOME/.local/bin/backup-home" ]]
[[ -f "$HOME/.config/privacy-cleanup/user.cfg" ]]
rg -q 'echo existing' "$MOCK_CRONTAB"
if rg -q 'privacy-cleanup user' "$MOCK_CRONTAB"; then
    echo 'Expected privacy schedule to be removed' >&2
    exit 1
fi
"$project_root/uninstall.sh" --module backup
[[ ! -e "$HOME/.local/bin/backup-home" ]]
if rg -q 'shell-scripts setup' "$HOME/.profile"; then
    echo 'Expected setup PATH entry to be removed' >&2
    exit 1
fi

"$project_root/setup.sh" --system --module network
[[ -x "$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/capture-traffic" ]]
[[ -f "$SHELL_SCRIPTS_INSTALL_ROOT/etc/cron.d/capture-traffic" ]]
"$project_root/uninstall.sh" --system --module network
[[ ! -e "$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/capture-traffic" ]]
[[ ! -e "$SHELL_SCRIPTS_INSTALL_ROOT/etc/cron.d/capture-traffic" ]]
"$project_root/setup.sh" --system --module network >/dev/null
printf '# local cron edit\n' >>"$SHELL_SCRIPTS_INSTALL_ROOT/etc/cron.d/capture-traffic"
if "$project_root/uninstall.sh" --system --module network >/dev/null 2>&1; then
    echo 'Expected changed managed cron file to be preserved' >&2
    exit 1
fi
"$project_root/uninstall.sh" --system --module network --force >/dev/null
[[ ! -e "$SHELL_SCRIPTS_INSTALL_ROOT/etc/cron.d/capture-traffic" ]]

"$project_root/setup.sh" --system --module privacy
printf '\n\n\n\n\n\n' | "$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/privacy-cleanup" --system configure
PATH="$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin:$PATH" \
    bash -c 'cd /tmp && privacy-cleanup --system status' >/dev/null
[[ -f "$SHELL_SCRIPTS_INSTALL_ROOT/etc/cron.d/privacy-cleanup" ]]
"$project_root/uninstall.sh" --system --module privacy --purge-config
[[ ! -e "$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/privacy-cleanup" ]]
[[ ! -e "$SHELL_SCRIPTS_INSTALL_ROOT/etc/cron.d/privacy-cleanup" ]]
[[ ! -e "$SHELL_SCRIPTS_INSTALL_ROOT/etc/privacy-cleanup/system.cfg" ]]

"$project_root/setup.sh" --module backup >/dev/null
printf '# local edit\n' >>"$HOME/.local/bin/backup-home"
if "$project_root/uninstall.sh" --module backup >/dev/null 2>&1; then
    echo 'Expected changed installed command to be preserved' >&2
    exit 1
fi
[[ -f "$HOME/.local/bin/backup-home" ]]
"$project_root/uninstall.sh" --module backup --force >/dev/null
[[ ! -e "$HOME/.local/bin/backup-home" ]]
printf 'Installation tests passed\n'
