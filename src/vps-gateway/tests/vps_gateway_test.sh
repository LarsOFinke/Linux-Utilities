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
if [[ ${MOCK_FAIL_STAGED:-0} == 1 && -e "$SHELL_SCRIPTS_INSTALL_ROOT/etc/nginx/conf.d/vps-gateway.conf" ]]; then
    exit 1
fi
[[ "$*" == '-t' ]]
MOCK
cat > "$test_dir/bin/systemctl" <<'MOCK'
#!/usr/bin/env bash
printf 'systemctl %s\n' "$*" >> "$MOCK_CALLS"
if [[ "$1" == is-active ]]; then
    [[ ${MOCK_ACTIVE:-0} == 1 ]]
fi
MOCK
cat > "$test_dir/bin/certbot" <<'MOCK'
#!/usr/bin/env bash
printf 'certbot %s\n' "$*" >> "$MOCK_CALLS"
MOCK
chmod +x "$test_dir/bin/apt-get" "$test_dir/bin/nginx" "$test_dir/bin/systemctl" "$test_dir/bin/certbot"
export PATH="$test_dir/bin:$PATH"

"$repository/src/vps-gateway/setup.sh" --system
command="$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/vps-gateway"
site_command="$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/vps-gateway-site"
[[ -x "$command" ]]
[[ -x "$site_command" ]]
[[ ! -e "$MOCK_CALLS" ]]

"$site_command" render java-spring --host service.example.org --port 18443 --output "$test_dir/site.conf"
rg -q 'server_name service.example.org;' "$test_dir/site.conf"
rg -q 'proxy_pass http://127.0.0.1:18443;' "$test_dir/site.conf"
"$site_command" render static-html --host files.example.org --root /srv/www/public-files --output "$test_dir/static.conf"
rg -q 'root /srv/www/public-files;' "$test_dir/static.conf"
if "$site_command" render java-spring --host 'bad;host' --port 18443 >/dev/null 2>&1; then
    echo 'Invalid host should be rejected' >&2
    exit 1
fi
if "$site_command" render java-spring --host service.example.org --port 18443 --output "$test_dir/site.conf" >/dev/null 2>&1; then
    echo 'Existing site should not be overwritten' >&2
    exit 1
fi

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

gateway_root="$SHELL_SCRIPTS_INSTALL_ROOT/etc/nginx"
mkdir -p "$gateway_root/sites-available" "$gateway_root/sites-enabled" "$gateway_root/conf.d" "$gateway_root/snippets"
touch "$gateway_root/nginx.conf" "$gateway_root/sites-available/default"
ln -s ../sites-available/default "$gateway_root/sites-enabled/default"
printf '2\nservice.example.org\n18443\ny\ny\n' | "$site_command" init
[[ -f "$gateway_root/conf.d/vps-gateway.conf" ]]
[[ -f "$gateway_root/snippets/vps-gateway-proxy-headers.conf" ]]
[[ -L "$gateway_root/sites-enabled/vps-gateway-catch-all.conf" ]]
[[ -L "$gateway_root/sites-enabled/service.example.org.conf" ]]
[[ ! -e "$gateway_root/sites-enabled/default" ]]
rg -q 'proxy_pass http://127.0.0.1:18443;' "$gateway_root/sites-available/service.example.org.conf"
rg -q '^certbot --nginx -d service.example.org --redirect$' "$MOCK_CALLS"

rollback_root="$test_dir/rollback-root"
rollback_nginx="$rollback_root/etc/nginx"
mkdir -p "$rollback_nginx/sites-available" "$rollback_nginx/sites-enabled" "$rollback_nginx/conf.d" "$rollback_nginx/snippets"
touch "$rollback_nginx/nginx.conf" "$rollback_nginx/sites-available/default"
ln -s ../sites-available/default "$rollback_nginx/sites-enabled/default"
if printf '1\nrollback.example.org\n18081\nn\ny\n' | SHELL_SCRIPTS_INSTALL_ROOT="$rollback_root" MOCK_FAIL_STAGED=1 "$site_command" init >/dev/null 2>&1; then
    echo 'Invalid staged NGINX configuration should fail setup' >&2
    exit 1
fi
[[ -L "$rollback_nginx/sites-enabled/default" ]]
[[ ! -e "$rollback_nginx/conf.d/vps-gateway.conf" ]]
[[ ! -e "$rollback_nginx/sites-available/rollback.example.org.conf" ]]

printf '# local edit\n' >> "$command"
if "$repository/uninstall.sh" --system --module vps-gateway >/dev/null 2>&1; then
    echo 'Locally modified command should block uninstall' >&2
    exit 1
fi
sed -i '$d' "$command"
"$repository/uninstall.sh" --system --module vps-gateway
[[ ! -e "$command" ]]
[[ ! -e "$site_command" ]]
[[ -f "$gateway_root/sites-available/service.example.org.conf" ]]
printf 'VPS gateway test passed\n'
