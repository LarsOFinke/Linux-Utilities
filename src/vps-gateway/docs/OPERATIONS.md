# Operations

Use standard NGINX and Certbot commands:

```bash
sudo nginx -t
sudo systemctl reload nginx
systemctl status nginx
sudo certbot certificates
sudo certbot renew --dry-run
```

Project files live in `/etc/nginx/sites-available/` and their enabling symlinks
in `/etc/nginx/sites-enabled/`. The responsible application repository should
contain the source file.

- 502/504: check the project container and its `127.0.0.1` port.
- Wrong site: check `server_name`, DNS, and enabled symlinks.
- TLS failure: inspect the project site and `certbot certificates`.
- Reload failure: run `nginx -t`; the running workers retain the previous valid
  configuration until a successful reload.

Back up `/etc/nginx` and `/etc/letsencrypt`; the latter contains private keys.
