#!/usr/bin/env bash
set -Eeuo pipefail

repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../../.." && pwd)
PYTHONPATH="$repository/src/modules/server-services/vps-gateway/scripts" python3 - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from vps_site_ports import ask_backend_port, configured_ports, next_port, port_is_listening

with TemporaryDirectory() as temporary:
    sites = Path(temporary)
    (sites / "active.conf").write_text("proxy_pass http://127.0.0.1:18081;\n", encoding="utf-8")
    (sites / "disabled.conf").write_text("proxy_pass http://127.0.0.1:18083;\n", encoding="utf-8")
    used = configured_ports(sites)
    assert used == {18081, 18083}
    with patch("vps_site_ports.port_is_listening", side_effect=lambda value: value == 18084):
        assert next_port(used) == 18085
        assert next_port({65535}) == 18081
        with patch("builtins.input", return_value=""):
            assert ask_backend_port(sites) == 18085
    listener = f"sl local_address rem_address st\n0: 0100007F:{18084:04X} 00000000:0000 0A\n"
    with patch.object(Path, "read_text", side_effect=[listener]):
        assert port_is_listening(18084)
PY
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

"$repository/src/modules/server-services/vps-gateway/setup.sh" --system
command="$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/vps-gateway"
site_command="$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin/vps-gateway-site"
bin_dir="$SHELL_SCRIPTS_INSTALL_ROOT/usr/local/bin"
[[ -x "$command" ]]
[[ -x "$site_command" ]]
[[ ! -e "$MOCK_CALLS" ]]

PYTHONPATH="$repository/src/modules/server-services/vps-gateway/scripts" python3 - <<'PY'
from pathlib import Path
from vps_site_model import BLUEPRINTS

module = Path('src/modules/server-services/vps-gateway')
core = (module / 'configuration/core/http.conf.example').read_text()
assert 'log_format vps_gateway' in core
assert '$request_uri' not in core and '$http_referer' not in core
for blueprint in BLUEPRINTS:
    site = (module / f'configuration/blueprints/{blueprint}.conf.example').read_text()
    assert 'access_log /var/log/nginx/access.log vps_gateway;' in site
spa = (module / 'configuration/blueprints/spa.conf.example').read_text()
assert spa.index('location ~ /\\.') < spa.index('location ~* \\.')
PY

"$bin_dir/vps-gateway-site-list" | rg -q '^java-spring$'
"$bin_dir/vps-gateway-site-render" java-spring --host service.example.org --port 18443 --output "$test_dir/site.conf"
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

"$bin_dir/vps-gateway-configure"
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
cat > "$gateway_root/nginx.conf" <<'NGINX'
http {
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
NGINX
touch "$gateway_root/sites-available/default"
ln -s ../sites-available/default "$gateway_root/sites-enabled/default"
printf '2\nservice.example.org\n18443\n18443\ny\ny\n' | "$bin_dir/vps-gateway-init"
[[ -f "$gateway_root/conf.d/vps-gateway.conf" ]]
[[ -f "$gateway_root/snippets/vps-gateway-proxy-headers.conf" ]]
[[ -L "$gateway_root/sites-enabled/vps-gateway-catch-all.conf" ]]
[[ -L "$gateway_root/sites-enabled/service.example.org.conf" ]]
[[ ! -e "$gateway_root/sites-enabled/default" ]]
rg -q 'proxy_pass http://127.0.0.1:18443;' "$gateway_root/sites-available/service.example.org.conf"
rg -q '^certbot --nginx -d service.example.org --redirect$' "$MOCK_CALLS"

printf '5\nfiles.example.org\n/srv/www/files\nn\ny\n' | "$bin_dir/vps-gateway-add"
[[ -L "$gateway_root/sites-enabled/files.example.org.conf" ]]
rg -q 'root /srv/www/files;' "$gateway_root/sites-available/files.example.org.conf"
printf '1\nnext.example.org\n18443\n18444\n18444\nn\ny\n' | "$bin_dir/vps-gateway-add"
rg -q 'proxy_pass http://127.0.0.1:18444;' "$gateway_root/sites-available/next.example.org.conf"
printf '1\ncancelled.example.org\n\ncancel\n' | "$bin_dir/vps-gateway-add"
[[ ! -e "$gateway_root/sites-available/cancelled.example.org.conf" ]]
if printf '5\nfiles.example.org\n/srv/www/files\n' | "$bin_dir/vps-gateway-add" >/dev/null 2>&1; then
    echo 'Duplicate hostname should be rejected' >&2
    exit 1
fi
if printf '1\nbroken.example.org\n18081\n18081\nn\ny\n' | MOCK_FAIL_STAGED=1 "$bin_dir/vps-gateway-add" >/dev/null 2>&1; then
    echo 'Invalid added site should fail' >&2
    exit 1
fi
[[ ! -e "$gateway_root/sites-available/broken.example.org.conf" ]]
[[ ! -e "$gateway_root/sites-enabled/broken.example.org.conf" ]]

project_site="$test_dir/project-site.conf"
cat > "$project_site" <<'NGINX'
# Keep this project-specific setting unchanged.
server {
    listen 80;
    server_name imported.example.org;
    location / { return 204; }
}
NGINX
printf '7\nimported.example.org\n%s\nn\ny\n' "$project_site" | "$bin_dir/vps-gateway-add"
cmp "$project_site" "$gateway_root/sites-available/imported.example.org.conf"
[[ -L "$gateway_root/sites-enabled/imported.example.org.conf" ]]

if printf '7\nwrong.example.org\n%s\n' "$project_site" | "$bin_dir/vps-gateway-add" >/dev/null 2>&1; then
    echo 'Imported config with a different hostname should be rejected' >&2
    exit 1
fi
[[ ! -e "$gateway_root/sites-available/wrong.example.org.conf" ]]

sed 's/imported.example.org/failed.example.org/' "$project_site" > "$test_dir/failed-site.conf"
if printf '7\nfailed.example.org\n%s\nn\ny\n' "$test_dir/failed-site.conf" | MOCK_FAIL_STAGED=1 "$bin_dir/vps-gateway-add" >/dev/null 2>&1; then
    echo 'Failed imported config validation should roll back' >&2
    exit 1
fi
[[ ! -e "$gateway_root/sites-available/failed.example.org.conf" ]]
[[ ! -e "$gateway_root/sites-enabled/failed.example.org.conf" ]]

rollback_root="$test_dir/rollback-root"
rollback_nginx="$rollback_root/etc/nginx"
mkdir -p "$rollback_nginx/sites-available" "$rollback_nginx/sites-enabled" "$rollback_nginx/conf.d" "$rollback_nginx/snippets"
cp "$gateway_root/nginx.conf" "$rollback_nginx/nginx.conf"
touch "$rollback_nginx/sites-available/default"
ln -s ../sites-available/default "$rollback_nginx/sites-enabled/default"
if printf '1\nrollback.example.org\n18081\n18081\nn\ny\n' | SHELL_SCRIPTS_INSTALL_ROOT="$rollback_root" MOCK_FAIL_STAGED=1 "$site_command" init >/dev/null 2>&1; then
    echo 'Invalid staged NGINX configuration should fail setup' >&2
    exit 1
fi
[[ -L "$rollback_nginx/sites-enabled/default" ]]
[[ ! -e "$rollback_nginx/conf.d/vps-gateway.conf" ]]
[[ ! -e "$rollback_nginx/sites-available/rollback.example.org.conf" ]]

first_root="$test_dir/first-root"
first_nginx="$first_root/etc/nginx"
mkdir -p "$first_nginx/sites-available" "$first_nginx/sites-enabled" "$first_nginx/conf.d" "$first_nginx/snippets"
cp "$gateway_root/nginx.conf" "$first_nginx/nginx.conf"
touch "$first_nginx/sites-available/default"
ln -s ../sites-available/default "$first_nginx/sites-enabled/default"
sed 's/imported.example.org/first.example.org/' "$project_site" > "$test_dir/first-site.conf"
printf '7\nfirst.example.org\n%s\nn\ny\n' "$test_dir/first-site.conf" | SHELL_SCRIPTS_INSTALL_ROOT="$first_root" "$bin_dir/vps-gateway-init"
cmp "$test_dir/first-site.conf" "$first_nginx/sites-available/first.example.org.conf"

missing_includes="$test_dir/missing-includes"
missing_nginx="$missing_includes/etc/nginx"
mkdir -p "$missing_nginx/sites-available" "$missing_nginx/sites-enabled" "$missing_nginx/conf.d" "$missing_nginx/snippets"
touch "$missing_nginx/nginx.conf" "$missing_nginx/sites-available/default"
ln -s ../sites-available/default "$missing_nginx/sites-enabled/default"
if printf '5\nnoinclude.example.org\n/srv/www/noinclude\nn\ny\n' | SHELL_SCRIPTS_INSTALL_ROOT="$missing_includes" "$bin_dir/vps-gateway-init" >/dev/null 2>&1; then
    echo 'Missing NGINX includes should stop first-run setup' >&2
    exit 1
fi
[[ ! -e "$missing_nginx/conf.d/vps-gateway.conf" ]]

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
