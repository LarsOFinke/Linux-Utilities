#!/usr/bin/env bash
set -Eeuo pipefail

repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
export SHELL_SCRIPTS_INSTALL_ROOT="$test_dir/root"
export MOCK_CALLS="$test_dir/calls"
mkdir -p "$test_dir/bin" "$SHELL_SCRIPTS_INSTALL_ROOT"
cat > "$test_dir/bin/apt-get" <<'MOCK'
#!/usr/bin/env bash
printf 'apt-get %s\n' "$*" >> "$MOCK_CALLS"
[[ ${MOCK_FAIL_APT:-0} != 1 ]]
MOCK
cat > "$test_dir/bin/nginx" <<'MOCK'
#!/usr/bin/env bash
printf 'nginx %s\n' "$*" >> "$MOCK_CALLS"
[[ "$*" == '-t' ]]
MOCK
cat > "$test_dir/bin/systemctl" <<'MOCK'
#!/usr/bin/env bash
printf 'systemctl %s\n' "$*" >> "$MOCK_CALLS"
if [[ "$1" == is-active ]]; then
    [[ ${MOCK_ACTIVE:-0} == 1 ]]
fi
MOCK
chmod +x "$test_dir/bin/apt-get" "$test_dir/bin/nginx" "$test_dir/bin/systemctl"
export PATH="$test_dir/bin:$PATH"

"$repository/src/vps-gateway/setup.sh" --system
command="$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/vps-gateway"
[[ -x "$command" ]]
[[ ! -e "$MOCK_CALLS" ]]

"$command" configure
expected=$'apt-get update\napt-get install -y nginx certbot python3-certbot-nginx\nnginx -t\nsystemctl enable nginx\nsystemctl is-active --quiet nginx\nsystemctl start nginx'
[[ $(cat "$MOCK_CALLS") == "$expected" ]]

: > "$MOCK_CALLS"
MOCK_ACTIVE=1 "$command" configure
rg -q '^systemctl reload nginx$' "$MOCK_CALLS"
if rg -q '^systemctl start nginx$' "$MOCK_CALLS"; then
    echo 'Active NGINX should reload, not start' >&2
    exit 1
fi

: > "$MOCK_CALLS"
if MOCK_FAIL_APT=1 "$command" configure >/dev/null 2>&1; then
    echo 'Failed package update must stop configuration' >&2
    exit 1
fi
[[ $(cat "$MOCK_CALLS") == 'apt-get update' ]]

printf '# local edit\n' >> "$command"
if "$repository/uninstall.sh" --system --module vps-gateway >/dev/null 2>&1; then
    echo 'Locally modified command should block uninstall' >&2
    exit 1
fi
sed -i '$d' "$command"
"$repository/uninstall.sh" --system --module vps-gateway
[[ ! -e "$command" ]]
[[ ! -e "$SHELL_SCRIPTS_INSTALL_ROOT/etc/nginx" ]]
printf 'VPS gateway test passed\n'
