"""Choose loopback backend ports without duplicating gateway routes."""

from __future__ import annotations

import argparse
import re
from itertools import chain
from pathlib import Path

from vps_site_model import port

FIRST_BACKEND_PORT = 18081
LOOPBACK_PORT = re.compile(r"\b127\.0\.0\.1:(\d{1,5})\b")


def configured_ports(sites_available: Path) -> set[int]:
    """Reserve ports mentioned by site files, including disabled sites."""
    if not sites_available.is_dir():
        return set()
    used: set[int] = set()
    for site in sites_available.glob("*.conf"):
        for value in LOOPBACK_PORT.findall(site.read_text(encoding="utf-8")):
            used.add(int(value))
    return used


def port_is_listening(value: int) -> bool:
    """Inspect Linux TCP listeners without needing to open a probe socket."""
    for table in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        for line in table.read_text(encoding="ascii").splitlines()[1:]:
            fields = line.split()
            if len(fields) > 3 and fields[3] == "0A" and int(fields[1].split(":")[1], 16) == value:
                return True
    return False


def next_port(used: set[int]) -> int:
    start = max((FIRST_BACKEND_PORT - 1, *used)) + 1
    for candidate in chain(range(start, 65536), range(FIRST_BACKEND_PORT, min(start, 65536))):
        if candidate not in used and not port_is_listening(candidate):
            return candidate
    raise RuntimeError("no unused backend port remains; review site configurations")


def ask_backend_port(sites_available: Path) -> int:
    used = configured_ports(sites_available)
    suggestion = next_port(used)
    while True:
        value = input(f"Loopback host port [{suggestion}]: ").strip()
        try:
            selected = port(value) if value else suggestion
        except argparse.ArgumentTypeError as error:
            print(f"Invalid value: {error}")
            continue
        if selected in used:
            print(f"Port {selected} is already referenced by a gateway site. Choose another port.")
            continue
        if value and port_is_listening(selected):
            print(f"Port {selected} has a local listener; use it only if that is your intended app.")
        return selected


def acknowledge_backend_port(selected: int) -> bool:
    print(f"\nConfigure this project's host-facing endpoint as 127.0.0.1:{selected}.")
    print("For a container, publish its web port to that host endpoint; the app may listen on 0.0.0.0 inside the container.")
    while True:
        response = input(f"When the project is configured, type {selected} to continue (or 'cancel'): ").strip()
        if response == str(selected):
            return True
        if response.lower() == "cancel":
            return False
        print("Port not acknowledged; the site has not been activated.")
