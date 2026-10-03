# Packet capture

Install system-wide from the repository root with `sudo src/modules/monitoring/network/setup.sh --system` or `sudo ./setup.sh --system --module network`, then run `sudo capture-traffic`. A copied module directory has its own `./setup.sh --system` and `./uninstall.sh --system`. The command manages a rolling capture of SSH, HTTP, and HTTPS packets.

It stops only the `tcpdump` process recorded in its PID file after checking the command line, verifies and archives the previous pcap under a unique name, and starts a new capture. It refuses a PID file naming an unrelated live process. Stop a capture launched by an older version manually before first use of the managed version.

Use `capture-traffic --name office --port 53 --subnet 10.0.0.0/8` to keep a named capture separate from the default one. Each name gets its own pcap, PID file, and log unless paths are explicitly overridden. `capture-traffic --list` reads the capture registry at `~/.local/state/shell-scripts/network-capture.json` (or `TCPDUMP_REGISTRY`) and checks each recorded PID before showing it as active. `capture-traffic --name office --stop` stops only that recorded capture. The registry keeps inactive configurations for reference. A capture file already assigned to another name is refused.

The default filter captures ports 22, 80, and 443. Choose ports and IPv4 subnets with `capture-traffic --port 53 --port 443 --subnet 10.0.0.0/8`; repeated ports are combined with OR, repeated subnets with OR, and the two groups with AND. Use `--all-ports` with a subnet to capture every port in that subnet. `TCPDUMP_PORTS` and `TCPDUMP_SUBNETS` accept comma-separated defaults for scheduled runs. Invalid filters are rejected before the existing capture is rotated.

The default interface comes from the system default route. Override it with `sudo env TCPDUMP_INTERFACE=ens6 capture-traffic`. Other settings are `TCPDUMP_FILE`, `TCPDUMP_PID_FILE`, `TCPDUMP_COMMAND`, and `TCPDUMP_BACKUP_DIR`; see `configuration/capture.env.example`. The log is `tcpdump.log` beside the pcap. The command needs `tcpdump`, `tar`, `bzip2`, `ip`, `nohup`, `flock`, GNU coreutils, and capture privileges. Set `TCPDUMP_BACKUP_DIR` explicitly if you previously used the shared `BACKUP_ROOT` setting for captures.

System-wide setup installs the inactive template at `/etc/cron.d/capture-traffic`; edit it to enable a schedule. Stop active named captures with `--name NAME --stop` before uninstalling the module. Uninstall tracks the cron file and requires `--force` if it has been edited. The command detaches from cron. Run `bash src/modules/monitoring/network/tests/capture_traffic_test.sh` for a mocked rotation and process-scope check.

Capture operations serialize across all profiles using a private lock beside the registry. Rotation holds it through ownership checks, process changes, and registry publication; listing and stopping use the same lock. Detached captures release it.
