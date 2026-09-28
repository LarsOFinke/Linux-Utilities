# Project integration

Every project owns its NGINX file and the host port it targets.

## Compose

Publish only the web entry point and bind it to loopback:

```yaml
services:
  web:
    ports:
      - "127.0.0.1:18081:8080"
```

The container must listen on `0.0.0.0:8080`. Choose another high host port for
every other project. Never publish databases or internal APIs.

## NGINX

Start from [the example site](../configuration/project-site.conf.example), replace its hostname and loopback port,
and keep the resulting file in the application repository. During onboarding:

```bash
sudo install -m 0644 deploy/nginx/site.conf /etc/nginx/sites-available/app.conf
sudo ln -sfn /etc/nginx/sites-available/app.conf /etc/nginx/sites-enabled/app.conf
sudo nginx -t
sudo systemctl reload nginx
```

DNS must point to the VPS before running `sudo certbot --nginx`. Certbot can edit
the installed file to add HTTPS and renew the certificate automatically. If the
application later copies its source file again, its source must include the final
TLS configuration so it does not overwrite Certbot’s changes.

Application deployments that do not change the site file require no NGINX reload.
