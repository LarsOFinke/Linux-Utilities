# Architecture

The VPS uses its distribution-provided NGINX installation as the only public
listener on ports 80 and 443. Multiple DNS A/AAAA records may point to the same
address; NGINX separates them by TLS SNI and HTTP `Host`.

Each application remains an independent Compose project. Its web service exposes
one unique high port on `127.0.0.1`, while databases and internal services stay
on project-private networks.

```text
Internet -> host NGINX -> 127.0.0.1:<project port> -> project web container
```

There is no gateway runtime or central route state. Each project owns its site
file under the standard NGINX `sites-available`/`sites-enabled` layout. Adding or
changing a file requires `nginx -t` followed by a graceful reload, not an NGINX
redeployment.
