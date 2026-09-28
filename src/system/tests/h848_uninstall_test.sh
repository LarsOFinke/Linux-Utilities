#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
export HOME="$test_dir/home"
mkdir -p "$HOME/.local/state/h848-audio-fix/original" "$test_dir/mock"

cat >"$test_dir/mock/systemctl" <<'MOCK_SYSTEMCTL'
#!/usr/bin/env bash
exit 0
MOCK_SYSTEMCTL
cat >"$test_dir/mock/pactl" <<'MOCK_PACTL'
#!/usr/bin/env bash
exit 0
MOCK_PACTL
chmod +x "$test_dir/mock/systemctl" "$test_dir/mock/pactl"
export PATH="$test_dir/mock:$PATH"

config="$HOME/.config/wireplumber/wireplumber.conf.d/51-h848-soft-mixer.conf"
guard="$HOME/.local/bin/h848-audio-guard"
mkdir -p "$(dirname "$config")" "$(dirname "$guard")"
printf 'installed\n' >"$config"
printf 'installed\n' >"$guard"
printf 'original\n' >"$HOME/.local/state/h848-audio-fix/original/51-h848-soft-mixer.conf.bak"
touch "$HOME/.local/state/h848-audio-fix/original/51-h848-soft-mixer.conf.present"
touch "$HOME/.local/state/h848-audio-fix/original/h848-audio-guard.absent"

"$project_root/src/system/scripts/install_h848_audio_fix.sh" --uninstall
[[ "$(cat "$config")" == original ]]
[[ ! -e "$guard" ]]
[[ ! -e "$HOME/.local/state/h848-audio-fix/original/51-h848-soft-mixer.conf.present" ]]

# Legacy backup files must not be mistaken for originals after a managed uninstall.
legacy_dir="$HOME/.local/state/h848-audio-fix/backups/20200101-000000"
lua_config="$HOME/.config/wireplumber/main.lua.d/51-h848-soft-mixer.lua"
mkdir -p "$legacy_dir" "$(dirname "$lua_config")"
printf 'old generated file\n' >"$legacy_dir/51-h848-soft-mixer.lua.bak"
printf 'installed\n' >"$lua_config"
"$project_root/src/system/scripts/install_h848_audio_fix.sh" --uninstall >/dev/null
[[ ! -e "$lua_config" ]]
printf 'H848 uninstall test passed\n'
