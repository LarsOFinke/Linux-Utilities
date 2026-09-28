# Event format

The output is newline-delimited JSON: one JSON object per event. The log is
opened in append mode, so existing records are retained across restarts.

## Record fields

| Field | Type | Description |
| --- | --- | --- |
| `ts` | string | UTC timestamp with nanosecond precision when available |
| `path` | string | Path associated with the event |
| `mask` | number | Raw Linux fanotify event mask |
| `events` | array | Stable names decoded from `mask` |
| `process` | object | Best-effort metadata for the event PID |
| `parent` | object | Best-effort metadata for the immediate parent PID |

Process objects contain `pid`, `ppid`, `uid`, `euid`, `gid`, `egid`, `session_id`,
`tty_nr`, `start_time`, `exe`, `comm`, `cmdline`, `cwd`, and `root`. These
fields reflect the local Linux process context visible under `/proc` at the time
of the event. The process and parent objects may be absent or contain empty
strings if the process exits before `/proc` can be read. Treat these fields as
best-effort evidence, not as a trusted identity.

This project does not have access to remote socket peer IPs or client addresses
for a file event. `fanotify` reports filesystem access by local process, not the
network origin of a connection. A real `origin_ip` field would require a higher
layer such as application logging, eBPF socket tracing, or packet capture.

## Event names

The sensor can emit:

- `open`
- `access`
- `modify`
- `open_exec` when supported by the running kernel and headers
- `close_write`
- `close_nowrite`
- `queue_overflow`

`access` represents a fanotify filesystem event, not every individual
`read(2)` call. fanotify may merge notifications.

## Example

```json
{"ts":"2026-08-28T10:21:43.918223411Z","path":"/srv/honey/.ssh/id_ed25519","mask":32,"events":["open"],"process":{"pid":18442,"ppid":17201,"uid":1000,"exe":"/usr/bin/cat","cmdline":"cat /srv/honey/.ssh/id_ed25519"},"parent":{"pid":17201,"ppid":17198,"uid":1000,"exe":"/usr/bin/bash","cmdline":"bash"}}
```

Consumers should tolerate additional fields and event names in future
versions, and should parse each line independently so one malformed or partial
record does not require discarding the entire file.

## Executable action

When `TRACK_ACTION` is configured, the tracker executes that file after the
JSONL record is written. It passes three positional arguments: the event path,
the raw fanotify mask, and the originating PID (or `0` when unavailable).

The action must be executable and should finish promptly because the listener
waits for it before processing the next event. A non-zero exit status is
reported to stderr but does not stop event monitoring. The action is executed
directly, without a shell.

## Basic HTTP action

The repository includes `tools/canary-curl-post.sh`. It posts the three action
arguments as URL-encoded form fields named `event_path`, `event_mask`, and
`event_pid`. Configure it by setting `FS_TRACKER_POST_URL` in the service
environment, then choose the tool's absolute path at installation time.

For a generated canary unit, add an environment override and restart that
canary:

```bash
sudo systemctl edit fs-file-monitor-finance.service
```

```ini
[Service]
Environment="FS_TRACKER_POST_URL=https://collector.example/events"
Environment="FS_TRACKER_POST_TIMEOUT=10"
```

The action requires `curl`. The default timeout is 10 seconds; a failed POST
is reported by `fs-tracker` and does not stop event monitoring.

## Mail action

The repository also includes `tools/canary-mail-send.sh`. It sends the event as
an email notification using the local mail transport. Configure it by setting
`FS_TRACKER_MAIL_TO` or `MAIL_TO` in the service environment, and optionally
`FS_TRACKER_MAIL_FROM`, `FS_TRACKER_MAIL_SUBJECT`, `MAIL_FROM`, or
`MAIL_SUBJECT`.

For a generated canary unit, add an environment override and restart that
canary:

```bash
sudo systemctl edit fs-file-monitor-finance.service
```

```ini
[Service]
Environment="FS_TRACKER_MAIL_TO=ops@example.com"
Environment="FS_TRACKER_MAIL_FROM=fs-tracker@host.example"
Environment="FS_TRACKER_MAIL_SUBJECT=fs-tracker alert"
```

The script prefers `sendmail` when available and falls back to `mail` if it is
not installed. It reads from the process environment, so systemd service
configuration is the intended setup path.