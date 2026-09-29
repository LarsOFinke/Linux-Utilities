# Canary file monitoring

This system-only module integrates the `Linux-Canary-File-Tracker` fanotify sensor. It records file events and process metadata in JSONL. A systemd unit is created only when you explicitly configure a named canary. The tracker needs Linux fanotify support, a C compiler at setup time, Python 3.9+, systemd for live services, and root privileges for the listener.

```bash
sudo ./setup.sh --system --module canary
sudo install -d -m 0700 /srv/honey
sudo install -m 0600 /dev/null /srv/honey/decoy.txt
sudo canary-configure decoy --path /srv/honey/decoy.txt --log /var/log/fs-tracker/decoy.jsonl
sudo canary-status decoy
sudo canary-stop decoy
sudo canary-start decoy
sudo canary-remove decoy --yes
sudo ./uninstall.sh --system --module canary
```

`canary-control` keeps its original subcommands. `canary-remove-all` is available for intentional removal of every managed service.

Setup compiles `fs-tracker` into a temporary directory before the shared installer changes installed files. It installs `fs-tracker` and `canary-control` in `/usr/local/bin` and records their hashes in the shared registry. It does not start a service or create a lure. `canary-control configure` requires an existing target file and writes `/etc/fs-tracker/<name>.conf`, `/etc/systemd/system/fs-file-monitor-<name>.service`, and private ownership state under `/var/lib/shell-scripts/canary/`. It enables and starts only that named service. Names contain letters, digits, underscores, or hyphens. `--action /absolute/executable` optionally invokes an executable after each event.

When this directory is copied elsewhere, run `sudo ./setup.sh --system` and `sudo ./uninstall.sh --system` inside it. The module-local build script and portable installer provide the same commands without the repository.

`remove` and root module uninstall stop and disable managed services, check generated file hashes, and remove their units, configs, and ownership state. They preserve watched files and JSONL logs. Locally edited or missing managed files block removal for review. Generated canary web projects and mail actions are independent tools; their data is not removed by module uninstall.

The upstream source and reference material are under `tracker/`, `docs/`, and `tools/`. Run the passive project generator from this checkout with `PYTHONPATH=src/modules/monitoring/canary python3 -m tools.canary_project --project-name demo --output-dir /tmp --mode standard`. The mailer source is under `tools/canary-mailer/`; its optional dependencies are documented there. The action examples under `scripts/` and `tools/` can be passed as `--action` after installation to an appropriate system path.

The sensor marks the current inode. Replacing the watched file requires a service restart to mark the new inode. Fanotify reports filesystem events, which may merge; process details from `/proc` are best effort. See [event format](docs/event-format.md), [configuration](docs/configuration.md), and [operations](docs/operations.md) for the sensor's data format and limitations. The upstream documentation's standalone installer commands have been superseded by the commands above.

For isolated lifecycle tests, set `SHELL_SCRIPTS_INSTALL_ROOT` to a temporary directory. No systemd command is run for a temporary root. Run `bash src/modules/monitoring/canary/tests/integration_test.sh` from this repository root.
The C and Python tests are `bash src/modules/monitoring/canary/tests/c_unit_test.sh` and `PYTHONPATH=src/modules/monitoring/canary python3 -m unittest discover -s src/modules/monitoring/canary/tests -p 'test_*.py'`.
