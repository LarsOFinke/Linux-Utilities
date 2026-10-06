# Canary file and SSH monitoring

This system-only module provides named fanotify file sensors and one SSH journal watcher. Both record JSONL. Services are created only when you choose to configure them. File monitoring needs Linux fanotify support and root privileges; setup needs a C compiler and Python 3.9+. Live services need systemd, and SSH watching needs `journalctl` plus OpenSSH server logs.

```bash
sudo ./main.sh setup --system --module canary
sudo install -d -m 0700 /srv/honey
sudo install -m 0600 /dev/null /srv/honey/decoy.txt
sudo canary-configure decoy --path /srv/honey/decoy.txt --log /var/log/fs-tracker/decoy.jsonl
sudo canary-status decoy
sudo canary-stop decoy
sudo canary-start decoy
sudo canary-remove decoy --yes
sudo ./main.sh uninstall --system --module canary
```

On an interactive root setup, choose the optional SSH watcher prompt to select events and either one login account or all accounts. Interactive `./main.sh update --system --module canary` offers to review those choices after refreshing the installed commands. Both prompts are skipped for scripted runs and with `--no-configure`. You can configure the watcher directly:

```bash
sudo canary-ssh setup --events attempt,success,failure,invalid-user,disconnect --system --log /var/log/fs-tracker/ssh.jsonl
sudo canary-ssh update --events success,failure --user alice
sudo canary-ssh status
sudo canary-ssh remove --yes
```

`canary-ssh update` also starts a watcher if one has not yet been configured. `--action /absolute/executable` runs an optional command for each selected event, passing one JSON object on standard input. See [SSH watch configuration](docs/configuration.md) and [SSH event format](docs/event-format.md) before choosing an action.

`canary-control` keeps its original subcommands. `canary-remove-all` is available for intentional removal of every managed service.

Setup compiles `fs-tracker` into a temporary directory before the shared installer changes installed files. It installs the tracker, Canary controls, SSH watcher, and their helpers in `/usr/local/bin`, recording their hashes in the shared registry. The install transaction does not start a service or create a lure. `canary-control configure` requires an existing target file and writes `/etc/fs-tracker/<name>.conf`, `/etc/systemd/system/fs-file-monitor-<name>.service`, and private ownership state under `/var/lib/shell-scripts/canary/`. It enables and starts only that named service. Names contain letters, digits, underscores, or hyphens. `--action /absolute/executable` optionally invokes an executable after each file event.

For remote deployment, run `./main.sh setup --ssh TARGET --system --module canary` from the repository root. The SSH archive includes the module-local build script and the canonical portable helper. Remote setup and update do not run configuration prompts; run `sudo canary-ssh setup` or `sudo canary-ssh update` on the target with the desired options.

`remove`, `canary-ssh remove`, and root module uninstall stop and disable managed services, check generated file hashes, and remove their units, configs, and ownership state. They preserve watched files and JSONL logs. Locally edited or missing managed files block removal for review. Generated canary web projects and mail actions are independent tools; their data is not removed by module uninstall.

The upstream source and reference material are under `tracker/`, `docs/`, and `tools/`. Run the passive project generator from this checkout with `PYTHONPATH=src/monitoring/canary python3 -m tools.canary_project --project-name demo --output-dir /tmp --mode standard`. The mailer source is under `tools/canary-mailer/`; its optional dependencies are documented there. The action examples under `scripts/` and `tools/` can be passed as `--action` after installation to an appropriate system path.

The sensor marks the current inode. Replacing the watched file requires a service restart to mark the new inode. Fanotify reports filesystem events, which may merge; process details from `/proc` are best effort. See [event format](docs/event-format.md), [configuration](docs/configuration.md), and [operations](docs/operations.md) for the sensor's data format and limitations. The upstream documentation's standalone installer commands have been superseded by the commands above.

For isolated lifecycle tests, set `SHELL_SCRIPTS_INSTALL_ROOT` to a temporary directory. No systemd command is run for a temporary root. Run `bash src/monitoring/canary/tests/lifecycle/integration_test.sh` from this repository root.
Run the C and Python checks from the repository root:

```bash
bash src/monitoring/canary/tests/tracker/c_unit_test.sh
PYTHONPATH=src/monitoring/canary python3 -m unittest discover -s src/monitoring/canary/tests/lifecycle -p '*Test*.py'
PYTHONPATH=src/monitoring/canary python3 -m unittest discover -s src/monitoring/canary/tests/ssh -p '*Test*.py'
PYTHONPATH=src/monitoring/canary python3 -m unittest discover -s src/monitoring/canary/tests/tools -p '*Test*.py'
```

Failed or interrupted service configuration removes the new unit, configuration,
and ownership record so configuration can be retried; watched files and existing
logs are preserved. `tests/lifecycle/CanaryLifecycleTest.py` injects service failures and
Ctrl+C with mocked systemd operations to verify this recovery.
