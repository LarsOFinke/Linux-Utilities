# Operations

`vps-gateway configure` installs distribution NGINX and Certbot packages and starts or reloads NGINX. It preserves the live NGINX configuration. `vps-gateway-site init` is the interactive first-run path. Root interactive setup offers to launch it after installing the commands; scripted setup leaves the host untouched.

## First-run wizard

For a fresh server where projects will register themselves, run `sudo vps-gateway-init --empty`. This noninteractive command installs the packages, HTTP core, proxy headers, and catch-all, disables the packaged default site, validates NGINX, and reloads it. It creates no project site and needs no hostname or working backend. The interactive wizard offers the equivalent `core-only` choice. A failed validation or reload restores the packaged default-site link and removes staged Gateway files. The same fresh-layout checks described below apply.

For a proxy blueprint, the wizard suggests a free loopback port and waits for you to acknowledge the assigned port after configuring the application. An already running app's port can be entered explicitly.

Run `sudo vps-gateway-site init` on a fresh Debian/Ubuntu NGINX layout. Select a blueprint and enter a DNS hostname plus a loopback host port or absolute document root. Alternatively, select `import-existing` and enter the hostname and absolute path to a project NGINX site config. The import copies the file unchanged, so review any referenced snippets, certificate paths, listeners, and upstreams first. The wizard previews the target paths and asks before changing the host. It installs the packages, checks that `nginx.conf` includes both `conf.d/*.conf` and `sites-enabled/*`, adds `/etc/nginx/conf.d/vps-gateway.conf` and the proxy header snippet, disables only the standard packaged `sites-enabled/default` symlink, and enables the first site and catch-all. It runs `nginx -t` before reload. Existing custom sites or `conf.d` files cause it to stop; use the manual integration path below for an established host. A failed config test or reload removes the staged files and restores the default symlink. Package installation remains in place.

Unknown HTTP hosts receive NGINX's closed-connection status 444. On NGINX 1.19.4+, unknown TLS SNI is rejected during the handshake. The wizard's `nginx -t` rejects the catch-all on older versions. The new site stays HTTP-only unless you select the Certbot step and DNS already points to the VPS. Keep the installed site file, including any Certbot edits, in the application's repository. Uninstalling the module removes commands and preserves active host configuration.

## Existing host or manual setup

After the first-run wizard, run `sudo vps-gateway-add` to add another site interactively. For proxy blueprints it suggests the next unused loopback port after existing gateway ports and skips locally bound ports. You can enter a different port if an app is already running on it. Configure the project to publish on the displayed `127.0.0.1:PORT`, then type that port to acknowledge it before activation. Select `import-existing` to copy an already prepared project site config instead; enter its hostname and absolute path. The wizard checks for an existing hostname, previews the paths, and creates and enables the site after confirmation. It runs `nginx -t` before reload and removes its new files if either step fails. It requires the gateway core and catch-all installed by the first-run wizard. TLS is optional and requires DNS to point to this VPS.

For project installers, use `sudo vps-gateway-site-import --host NAME --file /absolute/path/site.conf` or `sudo vps-gateway-site import` with the same options. `--file -` reads standard input, so an SSH command can stream the project config without staging it on disk. A matching installed file is a no-op; changed content requires `--replace`. Replacement saves the prior config in a private backup under `/var/lib/shell-scripts/vps-gateway/backups/`, and failure restores it. The import command does not run Certbot or prompt. It requires the initialized gateway and root privileges. Use `sudo -n` only when the deployment account has suitable noninteractive sudo access.

From this checkout on the VPS, after `sudo vps-gateway configure`, review existing NGINX includes and install the additive HTTP core and shared headers:

```bash
sudo install -m 0644 src/server-services/vps-gateway/configuration/core/http.conf.example /etc/nginx/conf.d/vps-gateway.conf
sudo install -m 0644 src/server-services/vps-gateway/configuration/core/proxy-headers.conf.example /etc/nginx/snippets/vps-gateway-proxy-headers.conf
sudo nginx -t
sudo systemctl reload nginx
```

Do not overwrite existing files at those paths. The distribution's `nginx.conf` must include `conf.d/*.conf` from its `http` block. [Connect each project](ROUTE_INTEGRATION.md) after the core is active. If desired, compare the optional [full main config example](../configuration/core/nginx.conf.example) with the host file for worker sizing, logging, and TLS tuning; preserve existing site and module includes when adapting it. It is not required by the wizard or blueprints.

The optional main config example uses `worker_processes auto` and 2048 worker connections. Connections to upstreams also count, and the process file-descriptor limit can be lower than this number. Adjust systemd `LimitNOFILE` and worker capacity together only after measuring real concurrency. The installed HTTP core bounds upstream connect time and defines request-rate and connection zones; participating sites apply those zones. Proxy buffering remains enabled for regular HTTP; the WebSocket and event-stream locations disable it. A 429 indicates a configured site limit; review NGINX logs before raising limits.

The generated sites and catch-all use the `vps_gateway` access-log format, which omits query strings and Referer headers. Imported sites keep their own logging directives; add `access_log /var/log/nginx/access.log vps_gateway;` in each imported server block if the same policy is desired. Application logs can still contain sensitive data. Keep `/etc/letsencrypt` private and back it up with `/etc/nginx`. Never put private keys in a project repository.

For manual setup, review the distribution's enabled default site. To reject unknown hostnames instead of serving a project, disable any existing default servers on ports 80 and 443 and install the [catch-all](../configuration/core/catch-all.conf.example) as `/etc/nginx/sites-available/vps-gateway-catch-all.conf`, with a symlink in `sites-enabled`. Its HTTPS block requires NGINX 1.19.4 or newer. Test with `nginx -t` before reloading. Keep this fallback separate from project sites so their Certbot edits cannot change it.

## Routine checks

```bash
sudo nginx -t
sudo systemctl reload nginx
systemctl status nginx
sudo certbot certificates
sudo certbot renew --dry-run
```

For a 502/504, check the app process, loopback port, and `proxy_read_timeout`. For a wrong site, check DNS, `server_name`, and enabled symlinks. For a 429, inspect the per-IP limits and whether a reverse proxy or CDN sits in front of NGINX. If there is a trusted upstream proxy, configure NGINX's real-IP module for only that proxy's actual address ranges before relying on IP limits; never trust arbitrary client forwarding headers. A failed reload leaves the running configuration in place; fix the file and rerun `nginx -t`.

TLS is issued per host after DNS is in place. The core allows TLS 1.2 and 1.3. Add HSTS only after verifying HTTPS works for the site and any intended subdomains. Certificate renewals remain Certbot's responsibility. Project deployments that do not change the site file require no NGINX reload.
