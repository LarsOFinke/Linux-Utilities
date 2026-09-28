# Operations and troubleshooting

From the repository root, run `bash src/canary/tests/c_unit_test.sh` for the C tests and `bash src/canary/tests/integration_test.sh` for an isolated install and service lifecycle test. The root setup compiles the sensor in a temporary directory and installs the executable through the shared registry. No service is started during setup.

For a live service, create a decoy target yourself, then run `sudo canary-control configure NAME --path /absolute/target --log /absolute/events.jsonl`. Inspect it with `sudo canary-control status NAME` or `journalctl -u fs-file-monitor-NAME.service -f`. Use `sudo canary-control stop NAME` and `sudo canary-control start NAME` to disable or enable it. `sudo canary-control remove NAME --yes` removes its generated service and config. `sudo ./uninstall.sh --system --module canary` removes all owned services and the installed commands. Both removal paths preserve watched files, logs, and generated web projects.

The listener needs fanotify permissions, normally root. It attaches to the current inode: restart its service after replacing the watched file. Kernel events can merge, and process metadata can disappear if a process exits before `/proc` is read. The sensor is local observability, not a security boundary. See [event format](event-format.md) for output details.
