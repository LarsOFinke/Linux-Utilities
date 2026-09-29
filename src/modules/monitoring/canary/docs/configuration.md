# Configuration reference

Each named canary watches one existing file and appends JSONL events to one log. Install the system module first, then create a service with `sudo canary-control configure NAME --path /absolute/file --log /absolute/events.jsonl`. Add `--action /absolute/executable` to run an action after each event. The action receives the event path, raw fanotify mask, and PID as positional arguments.

`canary-control` writes `/etc/fs-tracker/NAME.conf` and `/etc/systemd/system/fs-file-monitor-NAME.service`. Its private ownership state is `/var/lib/shell-scripts/canary/NAME.json`. The generated config contains `TRACK_PATH`, `TRACK_LOG`, and optionally `TRACK_ACTION`. The unit runs the installed `/usr/local/bin/fs-tracker`, with a private umask. It creates a missing log directory with mode 0700. The watched file must already exist; the command never creates lure content.

For manual runs, `fs-tracker --config FILE` loads a simple `KEY=VALUE` file. Blank lines and `#` comments are ignored. Values are literal and are not shell expanded. The precedence is built-in defaults, config file, environment variables, then CLI overrides. The CLI supports `--config`, `--path`, `--log`, `--action`, and `--help`. See [the module guide](../README.md) for setup and removal.
