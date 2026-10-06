# User guide

`fs-tracker` monitors one existing file with fanotify and appends JSONL event records enriched with process and parent process metadata. It records events such as open, access, modify, execute-open, close, and queue overflow. See [event format](event-format.md) for fields and limits.

Install and configure a service from the Linux-Utilities repository root:

```bash
sudo ./main.sh setup --system --module canary
sudo install -d -m 0700 /srv/honey
sudo install -m 0600 /dev/null /srv/honey/decoy.txt
sudo canary-control configure decoy --path /srv/honey/decoy.txt --log /var/log/fs-tracker/decoy.jsonl
sudo canary-control status decoy
```

The `configure` command creates and starts `fs-file-monitor-decoy.service`. It does not fill the target with content. Read or modify your own decoy file to generate events, then inspect the JSONL log. The command supports an optional `--action /absolute/executable` hook. See [configuration](configuration.md) for file and environment settings.

Stop and restart the service with `sudo canary-control stop decoy` and `sudo canary-control start decoy`. Remove it with `sudo canary-control remove decoy --yes`. Root module uninstall removes all managed canary services and the installed commands. Watched files and event logs are retained for review.
