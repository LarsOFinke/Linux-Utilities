# NGINX and Certbot setup

This system-only module brings the former `VPS-Gateway` bootstrap workflow into Linux-Utilities. It installs the distribution-provided NGINX and Certbot packages on Debian/Ubuntu VPS hosts. It does not manage application routes, project site files, containers, certificates, or a custom gateway runtime.

```bash
sudo ./setup.sh --system --module vps-gateway
sudo vps-gateway configure
sudo vps-gateway status
sudo ./uninstall.sh --system --module vps-gateway
```

Setup registers the `vps-gateway` command in `/usr/local/bin` through the shared installation registry. It does not install packages or change NGINX until `configure` is called. `configure` runs `apt-get update`, installs `nginx`, `certbot`, and `python3-certbot-nginx`, validates the existing NGINX configuration, and enables then starts or gracefully reloads the standard NGINX service. It preserves existing configuration. The command is safe to repeat after package or configuration updates.

When this directory is copied elsewhere, run `sudo ./setup.sh --system` and `sudo ./uninstall.sh --system` inside it. The copied module uses its own installation state and does not need the repository.

Uninstall removes the registered command. It leaves distribution packages, NGINX service state, `/etc/nginx`, `/etc/letsencrypt`, and project site files untouched because other applications may depend on them. Package and site removal remains a deliberate operator task.

Each application publishes its web service on a unique `127.0.0.1` port and owns its NGINX site file under `/etc/nginx/sites-available/` and the enabling symlink under `/etc/nginx/sites-enabled/`. See [route integration](docs/ROUTE_INTEGRATION.md), [architecture](docs/ARCHITECTURE.md), and [operations](docs/OPERATIONS.md). The [example site](configuration/project-site.conf.example) contains placeholder host and port values; do not deploy it unchanged.

The module needs `apt-get`, `nginx`, and `systemctl` on the host and root privileges for `configure`. The focused test `bash src/vps-gateway/tests/vps_gateway_test.sh` uses a temporary install root and mocked host commands.
