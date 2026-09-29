# Connect a project

The [HTTP core](../configuration/core/http.conf.example) and [proxy header snippet](../configuration/core/proxy-headers.conf.example) are prerequisites for these blueprints. The first-run wizard installs them; [operations](OPERATIONS.md) covers manual setup. Each project keeps its edited site file in its own repository. The installed `vps-gateway-site` command renders any blueprint without needing the source checkout.

If a project already has a complete NGINX site config, select `import-existing` in `sudo vps-gateway-init` or `sudo vps-gateway-add`. Enter its public hostname and absolute file path. The wizard copies the file unchanged to `sites-available`, creates the enabling symlink, tests NGINX, and reloads it. It refuses to overwrite a site and removes the new copy and symlink if validation or reload fails. The file must declare the selected hostname as an exact `server_name`; review referenced snippets, certificates, upstreams, listeners, and `access_log` policy before importing it.

| Workload | Blueprint | Notes |
| --- | --- | --- |
| Any HTTP app | [`http-app`](../configuration/blueprints/http-app.conf.example) | Simple reverse proxy. |
| Java / Spring Boot | [`java-spring`](../configuration/blueprints/java-spring.conf.example) | Configure the application to accept forwarded headers only from the gateway. Do not expose management endpoints unless intended. |
| Python / ASGI | [`python-asgi`](../configuration/blueprints/python-asgi.conf.example) | Includes an optional `/events/` server-sent events location. Remove it if unused. |
| WebSocket + HTTP | [`websocket`](../configuration/blueprints/websocket.conf.example) | Change `/ws/` to the app's actual upgrade path. The app should send ping frames more often than the one-hour read timeout. |
| Plain HTML | [`static-html`](../configuration/blueprints/static-html.conf.example) | Returns 404 for missing files. |
| Single-page app | [`spa`](../configuration/blueprints/spa.conf.example) | Falls back to `index.html` for client routes, but missing assets return 404. |

For an app in Compose, bind only its web port to host loopback. The container itself must listen on `0.0.0.0`:

```yaml
services:
  web:
    ports:
      - "127.0.0.1:18083:8080"
```

Choose an unused host port per project. `sudo vps-gateway-add` suggests the next available port, shows the endpoint to configure, and waits for you to acknowledge it before activating the site. Keep databases and administrative services on private networks. For a host process, bind it to `127.0.0.1` directly. A local `curl -I http://127.0.0.1:18083/` should reach the app before adding NGINX.

1. In the project repository, render a site. The command refuses to overwrite an existing file:

   ```bash
   mkdir -p deploy/nginx
   vps-gateway-site list
   vps-gateway-site render java-spring --host app.example.org --port 18083 --output deploy/nginx/site.conf
   # For files on disk instead: vps-gateway-site render static-html --host static.example.org --root /srv/www/static.example.org --output deploy/nginx/site.conf
   ```

2. Review the generated site, especially the WebSocket or event path. For static sites, the `--root` directory must be readable by `www-data`. Remove optional locations the app does not use. Without `--output`, the command prints the config to stdout.
3. Check the app's trusted-proxy setting. NGINX overwrites incoming `X-Forwarded-*` values; the app should trust only its loopback gateway and use forwarded scheme/host when generating redirects or secure cookies.
4. Install the reviewed file and enable it:

```bash
sudo install -m 0644 deploy/nginx/site.conf /etc/nginx/sites-available/my-project.conf
sudo ln -s /etc/nginx/sites-available/my-project.conf /etc/nginx/sites-enabled/my-project.conf
sudo nginx -t
sudo systemctl reload nginx
```

If a symlink already exists, inspect it before replacing it. Do not enable multiple sites with the same `server_name`. Confirm DNS A/AAAA records point to the VPS, then issue HTTPS with `sudo certbot --nginx -d app.example.org --redirect`. Certbot edits the installed file; copy the resulting TLS site back into the project repository before the next deployment. Use `sudo certbot renew --dry-run` to check renewal.

Rate and connection limits are per client IP and shared across the blueprints. Proxy sites also smooth aggregate requests per server name; excess requests wait within the configured burst and then receive 429. These limits can affect users behind a NAT and HTTP/2 parallel requests. Raise or remove a site's `limit_req` / `limit_conn` directives based on traffic and log observations. The WebSocket blueprint allows more concurrent connections per IP. For uploads, set a suitable `client_max_body_size` on the individual site. For long-running requests, change `proxy_read_timeout` on the relevant location only. A separate upstream pool and capacity plan are needed to balance multiple app instances; these templates target one local backend per project.
