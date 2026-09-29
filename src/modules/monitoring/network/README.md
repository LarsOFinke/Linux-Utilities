# Packet capture

Install system-wide from the repository root with `sudo src/modules/monitoring/network/setup.sh --system` or `sudo ./setup.sh --system --module network`, then run `sudo capture-traffic`. A copied module directory has its own `./setup.sh --system` and `./uninstall.sh --system`. The command manages a rolling capture of SSH, HTTP, and HTTPS packets.

It stops only the `tcpdump` process recorded in its PID file after checking the command line, verifies and archives the previous pcap under a unique name, and starts a new capture. It refuses a PID file naming an unrelated live process. Stop a capture launched by an older version manually before first use of the managed version.

The default interface comes from the system default route. Override it with `sudo env TCPDUMP_INTERFACE=ens6 capture-traffic`. Other settings are `TCPDUMP_FILE`, `TCPDUMP_PID_FILE`, `TCPDUMP_COMMAND`, and `TCPDUMP_BACKUP_DIR`; see `configuration/capture.env.example`. The log is `tcpdump.log` beside the pcap. The command needs `tcpdump`, `tar`, `bzip2`, `ip`, `nohup`, `flock`, GNU coreutils, and capture privileges. Set `TCPDUMP_BACKUP_DIR` explicitly if you previously used the shared `BACKUP_ROOT` setting for captures.

System-wide setup installs the inactive template at `/etc/cron.d/capture-traffic`; edit it to enable a schedule. Uninstall tracks this file and requires `--force` if it has been edited. The command detaches from cron. Run `bash src/modules/monitoring/network/tests/capture_traffic_test.sh` for a mocked rotation and process-scope check.
