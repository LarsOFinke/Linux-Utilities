# NGINX and Certbot setup

This system-only module installs distribution NGINX and Certbot packages on Debian/Ubuntu VPS hosts and provides a gateway core plus application site blueprints. Initialization can install the core and catch-all without an application site, so project deployers can register their own routes later.

```bash
sudo ./setup.sh --system --module vps-gateway
sudo vps-gateway-init --empty   # noninteractive core and catch-all; no project site
sudo vps-gateway-init           # interactive alternative, with optional first site
sudo vps-gateway-add            # interactively add another site
sudo vps-gateway-site-import --host app.example.org --file /absolute/path/site.conf
sudo vps-gateway-status
vps-gateway-site-list
sudo ./uninstall.sh --system --module vps-gateway
```

The HTTP catch-all returns a generic 404 error page for unregistered hostnames
and bare IP requests. Unknown TLS names are rejected during the handshake.
Keep application routes bound to their hostnames rather than the bare server IP.

For unattended host preparation, run `sudo vps-gateway-init --empty` after installing the module. It installs NGINX, Certbot, the HTTP core, proxy headers, and catch-all without a project site or input prompts. The interactive initializer also offers `core-only`. Portfolio and WoSB can then register their own routes during deployment.

For package-only setup, use `sudo vps-gateway-configure`. After initialization, `sudo vps-gateway-add` offers a blueprint or `import-existing` for a project site config that is already written. For blueprints it asks for a hostname and port or document root. For import, enter the public hostname and an absolute path to a regular NGINX site config file; it must declare that exact `server_name`. The wizard previews the source and destination, copies the file unchanged without overwriting an existing site, runs `nginx -t`, and reloads NGINX. It leaves the project source file untouched and removes the new copy and symlink if validation or reload fails. Imported configs can reference their own snippets and certificates, which must already exist for `nginx -t` to pass. Review their listeners, upstreams, and logging policy before activation. TLS issuance is optional and requires working DNS. `vps-gateway-site-render` remains available for manual site generation. The original `vps-gateway` and `vps-gateway-site` subcommands remain available.

For an unattended project deployment, initialize the gateway once, then run `sudo vps-gateway-site-import --host app.example.org --file /absolute/path/site.conf`. The equivalent subcommand is `sudo vps-gateway-site import ...`. The file must be an absolute regular file on the VPS; use `--file -` to read the config from standard input and transfer it directly over SSH. Repeating an import with identical bytes succeeds without reloading. A changed active site requires `--replace`; the old config is saved privately under `/var/lib/shell-scripts/vps-gateway/backups/` before replacement. NGINX validation or reload failure restores the previous file. The command does not issue certificates or prompt for input. It requires root privileges and a gateway initialized by `vps-gateway-init`.

```bash
# Run from the project checkout; the local config streams over SSH.
ssh vps 'sudo -n vps-gateway-site-import --host app.example.org --file -' < deploy/nginx/site.conf
# On later deployments, add --replace after reviewing the changed config.
ssh vps 'sudo -n vps-gateway-site-import --host app.example.org --file - --replace' < deploy/nginx/site.conf
```

The SSH user needs permission to run this command with `sudo -n` for unattended deployments. You can also transfer the file with `scp` and pass its absolute VPS path to `--file`. Referenced snippets, upstreams, and certificate files must exist on the VPS before import. Keep the project copy current with any Certbot edits.

Setup registers `vps-gateway` and `vps-gateway-site` in `/usr/local/bin` through the shared installation registry. An interactive root setup offers the first-run wizard; noninteractive setup only installs commands. `vps-gateway-site init` can be run later. It offers a blueprint or an existing project site config, previews the paths it will change, installs packages, enables the shared HTTP core and catch-all, and tests NGINX before reload. It requires a fresh distribution layout with no other enabled sites or `conf.d` files, and checks that `nginx.conf` includes both directories. Certbot issuance is optional and requires DNS to point to the VPS. If config validation or reload fails, the wizard removes its staged files and restores the packaged default-site symlink.

`vps-gateway configure` remains the package-only command. It runs `apt-get update`, installs `nginx`, `certbot`, and `python3-certbot-nginx`, validates the existing NGINX configuration, and enables then starts or gracefully reloads the standard NGINX service. It preserves existing configuration and can be repeated after package or configuration updates.

When this directory is copied elsewhere, run `sudo ./setup.sh --system` and `sudo ./uninstall.sh --system` inside it. The copied module uses its own installation state and does not need the repository.

Uninstall removes the registered commands. It leaves distribution packages, NGINX service state, `/etc/nginx`, `/etc/letsencrypt`, project site files, and saved site backups untouched because other applications or rollback plans may depend on them. Package and site removal remains a deliberate operator task.

Each application publishes its web service on a unique `127.0.0.1` port and owns its NGINX site file under `/etc/nginx/sites-available/` and the enabling symlink under `/etc/nginx/sites-enabled/`. The wizard installs the [HTTP core](configuration/core/http.conf.example) and [shared proxy headers](configuration/core/proxy-headers.conf.example); the [main NGINX config](configuration/core/nginx.conf.example) is an optional tuning reference. Use `vps-gateway-site render` for later [workload blueprints](docs/ROUTE_INTEGRATION.md) for Java, Python, WebSocket, plain HTML, SPA, or generic HTTP. See [operations](docs/OPERATIONS.md) and [design notes](docs/DESIGN_NOTES.md) for deployment and source rationale.

Version hiding is set inside generated server blocks and the catch-all, so the
shared HTTP core does not duplicate Debian/Ubuntu `server_tokens` settings.
Imported project configurations own their server-level version policy.

The module needs `apt-get`, `nginx`, and `systemctl` on the host and root privileges for `configure`. The focused test `bash src/modules/server-services/vps-gateway/tests/vps_gateway_test.sh` uses a temporary install root and mocked host commands.
