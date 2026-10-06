"""A saved SSH destination and its authentication method."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path

from ConnectVpsError import ConnectVpsError

USER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*\$?\Z")


@dataclass(frozen=True)
class Connection:
    id: int | None
    name: str
    ip: str
    user: str
    port: int
    auth: str
    key_path: str | None = None

    def __post_init__(self) -> None:
        if not self.name or len(self.name) > 80 or not self.name.isprintable():
            raise ConnectVpsError("name must be 1–80 printable characters")
        try:
            ipaddress.ip_address(self.ip)
        except ValueError as error:
            raise ConnectVpsError("enter a valid IPv4 or IPv6 address") from error
        if not USER_PATTERN.fullmatch(self.user):
            raise ConnectVpsError("enter a valid SSH login user")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ConnectVpsError("port must be between 1 and 65535")
        if self.auth not in {"key", "password"}:
            raise ConnectVpsError("authentication must be SSH key or password")
        if self.auth == "password" and self.key_path is not None:
            raise ConnectVpsError("password connections cannot specify a key")
        if self.key_path is not None and (not Path(self.key_path).is_absolute() or "\0" in self.key_path):
            raise ConnectVpsError("private key path must be absolute")
