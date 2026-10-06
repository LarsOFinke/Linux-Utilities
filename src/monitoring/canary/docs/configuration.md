# Configuration reference

Each named canary watches one existing file and appends JSONL events to one log. Install the system module first, then create a service with `sudo canary-control configure NAME --path /absolute/file --log /absolute/events.jsonl`. Add `--action /absolute/executable` to run an action after each event. The action receives the event path, raw fanotify mask, and PID as positional arguments.

`canary-control` writes `/etc/fs-tracker/NAME.conf` and `/etc/systemd/system/fs-file-monitor-NAME.service`. Its private ownership state is `/var/lib/shell-scripts/canary/NAME.json`. The generated config contains `TRACK_PATH`, `TRACK_LOG`, and optionally `TRACK_ACTION`. The unit runs the installed `/usr/local/bin/fs-tracker`, with a private umask. It creates a missing log directory with mode 0700. The watched file must already exist; the command never creates lure content.

For manual runs, `fs-tracker --config FILE` loads a simple `KEY=VALUE` file. Blank lines and `#` comments are ignored. Values are literal and are not shell expanded. The precedence is built-in defaults, config file, environment variables, then CLI overrides. The CLI supports `--config`, `--path`, `--log`, `--action`, and `--help`. See [the module guide](../README.md) for setup and removal.

## SSH watch

`canary-ssh setup` creates `/etc/fs-tracker/ssh-watch.json`, `/etc/systemd/system/fs-ssh-watch.service`, and a private ownership record under `/var/lib/shell-scripts/canary/ssh/`. An interactive root setup offers to run it. `canary-ssh update` changes the selected events, account scope, log, or action, and restarts the service. An interactive root module update offers to run it. Use `--no-configure` on root setup or update to skip these prompts.

Choose a comma-separated subset of `attempt`, `success`, `failure`, `invalid-user`, `disconnect`, `session-open`, and `session-close` with `--events`. `--user LOGIN` limits events to messages that identify that account; `--system` includes all accounts and events without an account name. A user filter cannot attribute a bare connection line to a login account, so those `attempt` events are omitted in user mode. The watcher reads new journal entries only. It does not change SSH server settings or replay old logs.

```bash
sudo canary-ssh setup --events success,failure --user alice --log /var/log/fs-tracker/ssh.jsonl
sudo canary-ssh update --events attempt,success,failure --system
sudo canary-ssh status
```

For noninteractive commands, provide `--events`, `--user` or `--system`, and `--log` during initial setup. An update retains omitted settings. The optional `--action /absolute/executable` receives each selected JSON object on standard input and is run directly without a shell. The SSH action interface differs from the file tracker's three positional arguments.
Use `--no-action` during an update to remove an existing action.
