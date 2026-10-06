# Saved VPS connections (`connect-vps`)

`connect-vps` keeps named IP addresses and SSH login settings in a private SQLite database. Run it without a subcommand to select a saved VPS and open an interactive SSH session:

```bash
connect-vps
connect-vps add
connect-vps update
connect-vps delete
```

All four flows require a terminal. `add` asks for a name, IPv4 or IPv6 address, SSH user, port, and authentication method. `update` and `delete` first show a numbered selection of saved connections. Enter `q` to cancel. `update` shows each current value; an empty answer keeps it. `delete` asks for confirmation before removing the entry. The commands take no flags or positional parameters beyond the subcommand; `--help` shows usage.

**SSH key is the default authentication method.** At the private key prompt, press Enter to use OpenSSH's default identities and SSH agent. To use a specific key, enter the path to its **private** key file. The matching public key belongs on the VPS in `authorized_keys`; a `.pub` file alone cannot be used as the client's private key. During an update, an empty key answer keeps an existing explicit path; enter `default` to return to SSH defaults and the agent.

Choose password authentication for a VPS that does not accept your key. The database stores only the word `password` for that entry. OpenSSH asks for the password when you connect; `connect-vps` never records it. SSH keys and passwords are therefore not hashed or encrypted in SQLite, because no authentication secret is stored there. SSH still handles host-key verification using your normal SSH configuration.

The database is `$XDG_DATA_HOME/connect-vps/connections.sqlite3`, or `~/.local/share/connect-vps/connections.sqlite3` if `XDG_DATA_HOME` is unset. `XDG_DATA_HOME` must be absolute. The module makes the data directory mode 0700 and the database mode 0600 and refuses a symbolic link at either path. Uninstall preserves saved connections.

Install with `./main.sh setup --module connect-vps` from the repository root, or this module's `setup.sh` within the checkout. The default command install is for the current user; `--system` installs the command for all users, while each user keeps a separate database. Python 3.9 or newer and an OpenSSH `ssh` client are required. Installed commands work from any directory.

Run `python3 src/system-utilities/connect-vps/tests/ConnectVpsTest.py` for focused tests. Tests use temporary homes and mock SSH; they do not contact a server.
