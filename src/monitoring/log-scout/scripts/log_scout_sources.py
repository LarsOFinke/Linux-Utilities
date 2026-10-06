"""Bounded read-only adapters for the journal and explicitly selected text files."""

from __future__ import annotations

import json
import os
import selectors
import stat
import subprocess
import time
from pathlib import Path

MAX_BYTES = 8 * 1024 * 1024
MAX_FILES = 16


def journal_output(limit: int, since: str, timeout: float = 20) -> tuple[bytes, str]:
    command = ["journalctl", "--no-pager", "--output=json", f"--lines={limit + 1}",
               f"--since={since}", "--output-fields=MESSAGE,PRIORITY,_SYSTEMD_UNIT,SYSLOG_IDENTIFIER,__REALTIME_TIMESTAMP"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = bytearray()
    errors = bytearray()
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, output)
            selector.register(process.stderr, selectors.EVENT_READ, errors)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("journalctl timed out; retry with a smaller window")
                for key, _ in selector.select(min(remaining, 0.25)):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    key.data.extend(chunk)
                    if len(output) + len(errors) > MAX_BYTES:
                        raise RuntimeError("journalctl output exceeds 8 MiB; reduce --limit or --since")
        result = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        warning = errors.decode("utf-8", errors="replace").strip()
        if result:
            raise RuntimeError(f"journalctl failed ({result}): {warning[:1000]}")
        return bytes(output), warning
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("journalctl timed out; retry with a smaller window") from error
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()


def read_journal(limit: int, since: str) -> tuple[list[dict], list[str]]:
    payload, diagnostic = journal_output(limit, since)
    records = []
    for line in payload.splitlines():
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError("Journal returned a non-object entry")
        message = record.get("MESSAGE", "")
        if isinstance(message, list) and all(isinstance(n, int) and 0 <= n < 256 for n in message):
            message = bytes(message).decode("utf-8", errors="replace")
        records.append({"message": str(message), "priority": record.get("PRIORITY"),
                        "unit": record.get("_SYSTEMD_UNIT", record.get("SYSLOG_IDENTIFIER", "")),
                        "timestamp": record.get("__REALTIME_TIMESTAMP", "")})
    warnings = [diagnostic] if diagnostic else []
    if len(records) > limit:
        warnings.append(f"Journal limited to newest {limit} entries in the requested window")
    return records[-limit:], warnings


def read_file(path: Path, limit: int) -> tuple[list[dict], list[str]]:
    # O_NONBLOCK prevents hanging on a FIFO; fstat validates the opened object.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        status = os.fstat(stream.fileno())
        if not stat.S_ISREG(status.st_mode):
            raise RuntimeError("Expected a regular text log (no symlinks, devices, or pipes)")
        header = stream.read(8)
        if header.startswith((b"\x1f\x8b", b"BZh", b"\xfd7zXZ", b"\x28\xb5\x2f\xfd", b"LPKSHHRH")):
            raise RuntimeError("Compressed/binary logs are unsupported; select a plain text log")
        offset = max(0, status.st_size - MAX_BYTES)
        stream.seek(offset)
        payload = stream.read(MAX_BYTES)
    if b"\0" in payload:
        raise RuntimeError("Binary/compressed logs are unsupported; select a plain text log")
    warnings = []
    if offset:
        payload = payload.partition(b"\n")[2]
        warnings.append("Only the last 8 MiB were read; earlier entries omitted")
    lines = payload.decode("utf-8", errors="replace").splitlines()
    if len(lines) > limit:
        warnings.append(f"Text log limited to newest {limit} lines")
    return [{"message": line, "priority": None, "unit": "", "timestamp": ""}
            for line in lines[-limit:]], warnings
