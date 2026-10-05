"""Private SQLite storage for saved SSH destinations."""

from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path

from Connection import Connection
from ConnectVpsError import ConnectVpsError


def database_path() -> Path:
    configured = os.environ.get("XDG_DATA_HOME")
    if configured:
        base = Path(configured).expanduser()
        if not base.is_absolute():
            raise ConnectVpsError("XDG_DATA_HOME must be an absolute path")
    else:
        base = Path.home() / ".local/share"
    return base / "connect-vps" / "connections.sqlite3"


class ConnectionStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else database_path()
        self.database: sqlite3.Connection | None = None
        self._previous_umask: int | None = None

    def __enter__(self) -> "ConnectionStore":
        directory = self.path.parent
        if directory.is_symlink():
            raise ConnectVpsError(f"refusing symbolic-link data directory: {directory}")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if directory.is_symlink():
            raise ConnectVpsError(f"refusing symbolic-link data directory: {directory}")
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fchmod(directory_fd, 0o700)
        finally:
            os.close(directory_fd)
        if self.path.is_symlink():
            raise ConnectVpsError(f"refusing symbolic-link database: {self.path}")
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ConnectVpsError(f"database is not a regular file: {self.path}")
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)
        self._previous_umask = os.umask(0o077)
        try:
            self.database = sqlite3.connect(self.path, timeout=5)
            self.database.execute("""CREATE TABLE IF NOT EXISTS connections (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                ip TEXT NOT NULL,
                user TEXT NOT NULL,
                port INTEGER NOT NULL,
                auth TEXT NOT NULL CHECK (auth IN ('key', 'password')),
                key_path TEXT
            )""")
            self.database.commit()
        except BaseException:
            if self.database is not None:
                self.database.close()
                self.database = None
            os.umask(self._previous_umask)
            self._previous_umask = None
            raise
        return self

    def __exit__(self, *_: object) -> None:
        try:
            if self.database is not None:
                self.database.close()
                self.database = None
        finally:
            if self._previous_umask is not None:
                os.umask(self._previous_umask)
                self._previous_umask = None

    def list(self) -> list[Connection]:
        assert self.database is not None
        rows = self.database.execute(
            "SELECT id, name, ip, user, port, auth, key_path FROM connections "
            "ORDER BY name COLLATE NOCASE, id"
        ).fetchall()
        return [Connection(*row) for row in rows]

    def add(self, item: Connection) -> None:
        assert self.database is not None
        try:
            with self.database:
                self.database.execute(
                    "INSERT INTO connections (name, ip, user, port, auth, key_path) VALUES (?, ?, ?, ?, ?, ?)",
                    (item.name, item.ip, item.user, item.port, item.auth, item.key_path),
                )
        except sqlite3.IntegrityError as error:
            raise ConnectVpsError(f"a connection named '{item.name}' already exists") from error

    def update(self, item: Connection) -> None:
        assert self.database is not None
        if item.id is None:
            raise ConnectVpsError("connection has no saved ID")
        try:
            with self.database:
                cursor = self.database.execute(
                    "UPDATE connections SET name=?, ip=?, user=?, port=?, auth=?, key_path=? WHERE id=?",
                    (item.name, item.ip, item.user, item.port, item.auth, item.key_path, item.id),
                )
                if cursor.rowcount != 1:
                    raise ConnectVpsError("selected connection no longer exists")
        except sqlite3.IntegrityError as error:
            raise ConnectVpsError(f"a connection named '{item.name}' already exists") from error

    def delete(self, item: Connection) -> None:
        assert self.database is not None
        with self.database:
            cursor = self.database.execute("DELETE FROM connections WHERE id=?", (item.id,))
            if cursor.rowcount != 1:
                raise ConnectVpsError("selected connection no longer exists")
