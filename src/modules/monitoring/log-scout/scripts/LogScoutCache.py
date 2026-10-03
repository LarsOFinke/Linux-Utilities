"""Private, versioned scan snapshots with atomic publication and bounded retention."""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from log_scout_rules import CATEGORIES

SCAN_ID = re.compile(r"\d{8}T\d{12}Z-[0-9a-f]{8}")
MAX_CACHE_BYTES = 8 * 1024 * 1024


class LogScoutCache:
    def __init__(self, directory: Path):
        if not directory.is_absolute():
            raise ValueError("Cache directory must be absolute")
        self.directory = directory

    @contextmanager
    def locked(self):
        self.directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        status = self.directory.lstat()
        if not stat.S_ISDIR(status.st_mode) or status.st_uid != os.geteuid() or status.st_mode & 0o077:
            raise RuntimeError("Cache must be an owned, private directory (0700), not a symlink")
        descriptor = os.open(self.directory / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise RuntimeError("Cache lock must be a regular file")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            os.close(descriptor)

    def _paths(self) -> list[Path]:
        return sorted((p for p in self.directory.iterdir() if p.suffix == ".json" and SCAN_ID.fullmatch(p.stem)),
                      reverse=True)

    def _read(self, path: Path) -> dict:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            status = os.fstat(stream.fileno())
            if not stat.S_ISREG(status.st_mode) or status.st_mode & 0o077 or status.st_uid != os.geteuid():
                raise ValueError("Cache snapshot must be an owned, private regular file")
            raw = stream.read(MAX_CACHE_BYTES + 1)
        if len(raw) > MAX_CACHE_BYTES:
            raise ValueError("Cache snapshot exceeds size limit")
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("Unsupported cache schema; preserve this snapshot for a compatible version")
        if data.get("id") != path.stem or not isinstance(data.get("created_at"), str):
            raise ValueError("Invalid cache identity")
        if datetime.fromisoformat(data["created_at"]).tzinfo is None:
            raise ValueError("Cache timestamp must include a timezone")
        if (not isinstance(data.get("categories"), dict) or set(data["categories"]) != set(CATEGORIES)
                or any(type(n) is not int or n < 0 for n in data["categories"].values())
                or any(type(data.get(key)) is not int or data[key] < 0 for key in ("examined", "matches", "omitted_matches"))
                or type(data.get("partial")) is not bool):
            raise ValueError("Invalid cached summary")
        groups = data.get("groups")
        if not isinstance(groups, list) or len(groups) > 250:
            raise ValueError("Invalid cached groups")
        for group in groups:
            if (not isinstance(group, dict) or not isinstance(group.get("category"), str)
                    or group["category"] not in CATEGORIES
                    or group.get("severity") not in ("critical", "error", "warning")
                    or type(group.get("count")) is not int or group["count"] < 1
                    or any(not isinstance(group.get(k), str) for k in ("pattern", "source", "unit"))
                    or not isinstance(group.get("examples"), list) or len(group["examples"]) > 2
                    or any(not isinstance(e, dict) or any(not isinstance(e.get(k), str) for k in ("message", "timestamp"))
                           for e in group["examples"])):
                raise ValueError("Invalid cached finding")
        sources = data.get("sources")
        if not isinstance(sources, list) or len(sources) > 17:
            raise ValueError("Invalid cached sources")
        for source in sources:
            if (not isinstance(source, dict) or not isinstance(source.get("name"), str)
                    or not isinstance(source.get("error"), str)
                    or type(source.get("examined")) is not int
                    or not isinstance(source.get("warnings"), list)
                    or any(not isinstance(w, str) for w in source["warnings"])):
                raise ValueError("Invalid cached source")
        return data

    def load(self, scan_id: str = "latest") -> dict:
        with self.locked():
            if scan_id == "latest":
                paths = self._paths()
                if not paths:
                    raise RuntimeError("No cached scans; run log-scout scan first")
                path = paths[0]
            else:
                if not SCAN_ID.fullmatch(scan_id):
                    raise ValueError("Invalid scan ID; use log-scout history")
                path = self.directory / (scan_id + ".json")
            return self._read(path)

    def save(self, data: dict) -> None:
        payload = (json.dumps(data, ensure_ascii=True, indent=2) + "\n").encode()
        if len(payload) > MAX_CACHE_BYTES:
            raise ValueError("Scan exceeds cache size limit; previous scans preserved")
        if not SCAN_ID.fullmatch(data["id"]):
            raise ValueError("Invalid scan ID")
        with self.locked():
            target = self.directory / (data["id"] + ".json")
            if target.exists() or target.is_symlink():
                raise RuntimeError("Scan ID already exists")
            descriptor, temporary = tempfile.mkstemp(prefix=".scan-", dir=self.directory)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            for index, path in enumerate(self._paths()):
                if path == target:
                    continue
                # Unknown/corrupt data is never silently deleted by retention.
                try:
                    old = self._read(path)
                except (ValueError, OSError):
                    continue
                if index >= 10 or datetime.fromisoformat(old["created_at"]) < cutoff:
                    path.unlink()

    def history(self) -> list[dict]:
        with self.locked():
            return [self._read(path) for path in self._paths()]

    def purge(self) -> int:
        with self.locked():
            paths = self._paths()
            for path in paths:
                self._read(path)  # Validate the whole selection before deleting anything.
            for path in paths:
                path.unlink()
            return len(paths)
