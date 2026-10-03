"""Deterministic triage and bounded, best-effort redaction of diagnostic text."""

from __future__ import annotations

import re

CATEGORIES = {
    "security": "Authentication and permissions",
    "storage": "Disks and filesystems",
    "memory": "Memory pressure",
    "network": "Network and connectivity",
    "services": "Services and applications",
    "kernel": "Kernel and hardware",
    "other": "Other warnings and errors",
}
RULES = [
    ("memory", r"out of memory|oom[-_ ]kill|killed process|memory pressure"),
    ("storage", r"no space left|disk full|i/o error|read-only file system|filesystem|ext4|btrfs|nvme|\bsata\b"),
    ("security", r"authentication|failed password|permission denied|access denied|unauthorized|\bsudo\b|\bpam_"),
    ("network", r"network|connection|timed? out|timeout|dns|dhcp|unreachable|\btls\b|\bssl\b"),
    ("services", r"service|systemd|segfault|exception|traceback|crash"),
    ("kernel", r"kernel|firmware|hardware|\bacpi\b|\busb\b"),
]
SECRET = re.compile(r'''(?ix)
    (\b(?:password|passwd|token|secret|api[_-]?key|authorization|cookie)\b["']?\s*[:=]\s*)
    (?:"[^"]*"|'[^']*'|[^\s,;]+)
''')


def sanitize(value: object, limit: int = 2048) -> str:
    text = str(value)
    text = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [redacted]", text)
    text = SECRET.sub(r"\1[redacted]", text)
    text = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[redacted]@", text)
    text = re.sub(r"(https?://[^\s?]+)\?[^\s]+", r"\1?[redacted]", text)
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email]", text)
    # Strip terminal controls, including ESC, C1 and bidi formatting controls.
    text = "".join(char if char.isprintable() else " " for char in text)
    return text[:limit] + (" …" if len(text) > limit else "")


def classify(message: str, priority: object = None, unit: str = "") -> tuple[str, str] | None:
    # Structured journal priorities are authoritative; ignore informational entries.
    if priority is not None:
        try:
            number = int(priority)
        except (TypeError, ValueError):
            number = -1
        if 0 <= number <= 7:
            if number > 4:
                return None
            severity = "critical" if number <= 2 else "error" if number == 3 else "warning"
        else:
            priority = None
    if priority is None:
        if re.search(r"\b(panic|fatal|critical)\b|out of memory|oom[-_ ]kill", message, re.I):
            severity = "critical"
        elif re.search(r"\b(error|failed|failure|exception|segfault|denied)\b", message, re.I):
            severity = "error"
        elif re.search(r"\b(warn(?:ing)?|timeout)\b|timed out", message, re.I):
            severity = "warning"
        else:
            return None
    for category, pattern in RULES:
        if re.search(pattern, message + " " + unit, re.I):
            return category, severity
    return "other", severity


def signature(message: str) -> str:
    """Group repeated messages without claiming the group is a root cause."""
    text = re.sub(r"\b\d{4}-\d\d-\d\d[T ][\d:.+Z-]+", "<time>", message)
    text = re.sub(r"\b[0-9a-f]{12,}\b|\b0x[0-9a-f]+\b", "<id>", text, flags=re.I)
    return re.sub(r"\b\d+\b", "#", text)
