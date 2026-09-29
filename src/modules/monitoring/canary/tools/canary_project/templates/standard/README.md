# {project_name}

This project is a deliberately noisy canary deployment used to observe common reconnaissance activity.
It exposes a handful of realistic misconfigurations and scan targets that attackers frequently probe.

## Scan targets

- `/api/.env`
- `/api/health`
- `/config/app.env`
- `/public/index.php`
- `/admin/.env`
- `/wp-config.php`
- `/phpmyadmin/index.php`
- `/server.py`

## Logging behaviour

This canary is designed to capture metadata automatically when a scanner hits one of the exposed endpoints.
The service records request method, timestamp, client IP, user-agent, host header, and target path in a local access log,
without any interactive confirmation or extra user action.

## Legal notice

The deployment is intentionally misleading and should be treated as a monitoring environment for defensive research only.
Any access is logged and retains request metadata for triage and operational review.
