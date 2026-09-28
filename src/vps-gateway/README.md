# NGINX and Certbot setup

This system-only module installs distribution NGINX and Certbot packages on Debian/Ubuntu VPS hosts and provides a gateway core plus application site blueprints. The optional first-run wizard can activate the first site and a catch-all after showing the exact plan.

```bash
sudo ./setup.sh --system --module vps-gateway
sudo vps-gateway-site init      # run later if you skipped the setup prompt
sudo vps-gateway status
vps-gateway-site list
sudo ./uninstall.sh --system --module vps-gateway
```

For package-only setup, use `sudo vps-gateway configure`.

Setup registers `vps-gateway` and `vps-gateway-site` in `/usr/local/bin` through the shared installation registry. An interactive root setup offers the first-run wizard; noninteractive setup only installs commands. `vps-gateway-site init` can be run later. It prompts for blueprint, hostname, and loopback port or document root, previews the paths it will change, installs packages, enables the shared HTTP core and catch-all, and tests NGINX before reload. It only runs on a fresh distribution layout without other enabled sites or `conf.d` files. Certbot issuance is optional and requires DNS to point to the VPS. If config validation or reload fails, the wizard removes its staged files and restores the packaged default-site symlink.

`vps-gateway configure` remains the package-only command. It runs `apt-get update`, installs `nginx`, `certbot`, and `python3-certbot-nginx`, validates the existing NGINX configuration, and enables then starts or gracefully reloads the standard NGINX service. It preserves existing configuration and can be repeated after package or configuration updates.

When this directory is copied elsewhere, run `sudo ./setup.sh --system` and `sudo ./uninstall.sh --system` inside it. The copied module uses its own installation state and does not need the repository.

Uninstall removes the registered commands. It leaves distribution packages, NGINX service state, `/etc/nginx`, `/etc/letsencrypt`, and project site files untouched because other applications may depend on them. Package and site removal remains a deliberate operator task.

Each application publishes its web service on a unique `127.0.0.1` port and owns its NGINX site file under `/etc/nginx/sites-available/` and the enabling symlink under `/etc/nginx/sites-enabled/`. The wizard installs the [HTTP core](configuration/core/http.conf.example) and [shared proxy headers](configuration/core/proxy-headers.conf.example); the [main NGINX config](configuration/core/nginx.conf.example) is an optional tuning reference. Use `vps-gateway-site render` for later [workload blueprints](docs/ROUTE_INTEGRATION.md) for Java, Python, WebSocket, plain HTML, SPA, or generic HTTP. See [operations](docs/OPERATIONS.md) and [design notes](docs/DESIGN_NOTES.md) for deployment and source rationale.

The module needs `apt-get`, `nginx`, and `systemctl` on the host and root privileges for `configure`. The focused test `bash src/vps-gateway/tests/vps_gateway_test.sh` uses a temporary install root and mocked host commands.
