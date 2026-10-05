"""Interactive prompts for VPS connection records."""

from __future__ import annotations

import ipaddress
from pathlib import Path

from Connection import Connection, USER_PATTERN
from ConnectVpsError import ConnectVpsError


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt) as error:
        raise ConnectVpsError("selection cancelled") from error


def select(connections: list[Connection]) -> Connection | None:
    if not connections:
        raise ConnectVpsError("no saved VPS connections; run 'connect-vps add' first")
    print("Saved VPS connections:")
    for number, item in enumerate(connections, 1):
        print(f"  {number}. {item.name} ({item.user}@{item.ip}:{item.port}, {item.auth})")
    while True:
        answer = ask("Select a number or 'q' to cancel: ")
        if answer.lower() in {"q", "quit"}:
            return None
        try:
            number = int(answer)
            if 1 <= number <= len(connections):
                return connections[number - 1]
        except ValueError:
            pass
        print("Enter one listed number or 'q'.")


def _name(current: str | None) -> str:
    while True:
        answer = ask(f"Name [{current}]: " if current else "Name: ") or current or ""
        if answer and len(answer) <= 80 and answer.isprintable():
            return answer
        print("Name must be 1–80 printable characters.")


def _ip(current: str | None) -> str:
    while True:
        answer = ask(f"IP address [{current}]: " if current else "IP address: ") or current or ""
        try:
            return str(ipaddress.ip_address(answer))
        except ValueError:
            print("Enter a valid IPv4 or IPv6 address.")


def _user(current: str | None) -> str:
    while True:
        answer = ask(f"SSH login user [{current}]: " if current else "SSH login user: ") or current or ""
        if USER_PATTERN.fullmatch(answer):
            return answer
        print("Enter a valid SSH login user.")


def _port(current: int | None) -> int:
    default = current if current is not None else 22
    while True:
        answer = ask(f"SSH port [{default}]: ") or str(default)
        try:
            port = int(answer)
            if 1 <= port <= 65535:
                return port
        except ValueError:
            pass
        print("Port must be between 1 and 65535.")


def _auth(current: str | None) -> str:
    default = current or "key"
    while True:
        answer = ask(f"Authentication: [k]ey or [p]assword [{default}]: ").lower()
        if not answer:
            return default
        if answer in {"k", "key"}:
            return "key"
        if answer in {"p", "password"}:
            return "password"
        print("Enter 'k' or 'p'.")


def _key_path(current: str | None) -> str | None:
    while True:
        if current:
            answer = ask(f"Private key path [{current}] (blank keeps, 'default' uses agent): ")
            if not answer:
                return current
        else:
            answer = ask("Private key path (blank uses SSH defaults/agent): ")
            if not answer:
                return None
        if answer.lower() == "default":
            return None
        if answer.endswith(".pub"):
            print("Select the private key file; the .pub file belongs on the server.")
            continue
        try:
            path = Path(answer).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as error:
            print(f"Cannot use that key path: {error}")
            continue
        if path.is_file():
            return str(path)
        print("Select an existing private key file.")


def prompt_connection(current: Connection | None = None) -> Connection:
    print("Press Enter to keep a shown value." if current else "Add a VPS connection.")
    name = _name(current.name if current else None)
    ip = _ip(current.ip if current else None)
    user = _user(current.user if current else None)
    port = _port(current.port if current else None)
    auth = _auth(current.auth if current else None)
    key_path = _key_path(current.key_path if current and current.auth == "key" else None) if auth == "key" else None
    if auth == "password":
        print("SSH will ask for the password when you connect; it is not saved.")
    return Connection(current.id if current else None, name, ip, user, port, auth, key_path)
