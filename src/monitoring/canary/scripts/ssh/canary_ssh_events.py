"""Classify OpenSSH journal messages into selectable Canary events."""

import re

EVENTS = ("attempt", "success", "failure", "invalid-user", "disconnect", "session-open", "session-close")
_USER = r"(?P<user>[^\s]+)"
_RULES = (
    ("success", re.compile(r"^Accepted \S+ for " + _USER + r" from (?P<address>\S+)")),
    ("failure", re.compile(r"^Failed \S+ for (?:invalid user )?" + _USER + r" from (?P<address>\S+)")),
    ("invalid-user", re.compile(r"^Invalid user " + _USER + r" from (?P<address>\S+)")),
    ("session-open", re.compile(r"^pam_unix\(sshd:session\): session opened for user (?P<user>[^\s(]+)")),
    ("session-close", re.compile(r"^pam_unix\(sshd:session\): session closed for user " + _USER)),
    ("disconnect", re.compile(r"^(?:Disconnected from|Connection closed by) (?:authenticating |invalid )?user "
                              + _USER + r" (?P<address>\S+)")),
    ("disconnect", re.compile(r"^(?:Disconnected from|Connection closed by) (?P<address>\S+)")),
    ("attempt", re.compile(r"^Connection from (?P<address>\S+)")),
)


def classify(entry):
    """Return one normalized event, or None for an unrelated journal entry."""
    if not isinstance(entry, dict):
        return None
    if entry.get("SYSLOG_IDENTIFIER") not in ("sshd", "sshd-session"):
        return None
    message = entry.get("MESSAGE")
    if not isinstance(message, str):
        return None
    for kind, pattern in _RULES:
        match = pattern.match(message)
        if match:
            return {"event": kind, "user": match.groupdict().get("user"),
                    "address": match.groupdict().get("address"),
                    "timestamp_us": entry.get("__REALTIME_TIMESTAMP"),
                    "message": message}
    return None


def selected(event, config):
    if event is None or event["event"] not in config["events"]:
        return False
    return config["scope"] == "system" or event["user"] == config["user"]
