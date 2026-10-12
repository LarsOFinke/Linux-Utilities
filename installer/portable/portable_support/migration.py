"""Move module-owned scheduled entry points when command names change."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(module_id: str, previous: dict, root: Path, system: bool) -> list[Path]:
    old = set(previous)
    if module_id == "privacy" and "privacy-scheduled" in old and system:
        path = root / "etc/cron.d/privacy-cleanup"
        if path.is_symlink():
            raise RuntimeError(f"Refusing symbolic-link Privacy schedule: {path}")
        return [path] if path.is_file() else []
    if module_id != "canary" or not old.intersection({"fs-tracker", "canary-ssh-watcher"}):
        return []
    state = root / "var/lib/shell-scripts/canary"
    if state.is_symlink() or (state / "ssh").is_symlink():
        raise RuntimeError(f"Refusing symbolic-link Canary state: {state}")
    paths = []
    for record in sorted(state.glob("*.json")):
        if record.is_symlink():
            raise RuntimeError(f"Refusing symbolic-link Canary state: {record}")
        data = json.loads(record.read_text(encoding="utf-8"))
        if data.get("name") != record.stem or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", record.stem):
            raise RuntimeError(f"Invalid Canary state: {record}")
        unit = root / "etc/systemd/system" / f"fs-file-monitor-{data['name']}.service"
        if unit.parent.is_symlink() or unit.is_symlink() or _digest(unit) != data["unit_sha256"]:
            raise RuntimeError(f"Managed Canary unit changed: {unit}")
        paths.extend((record, unit))
    record = state / "ssh/record.json"
    if record.exists() or record.is_symlink():
        if record.is_symlink():
            raise RuntimeError(f"Refusing symbolic-link Canary state: {record}")
        data = json.loads(record.read_text(encoding="utf-8"))
        if data.get("kind") != "ssh":
            raise RuntimeError(f"Invalid Canary state: {record}")
        unit = root / "etc/systemd/system/fs-ssh-watch.service"
        if unit.parent.is_symlink() or unit.is_symlink() or _digest(unit) != data["unit_sha256"]:
            raise RuntimeError(f"Managed Canary unit changed: {unit}")
        paths.extend((record, unit))
    return paths


def user_crontab(module_id: str, previous: dict, system: bool) -> bytes | None:
    if module_id != "privacy" or system or "privacy-scheduled" not in previous:
        return None
    result = subprocess.run(["crontab", "-l"], capture_output=True, check=False)
    if result.returncode:
        if b"no crontab" in result.stderr.lower():
            return b""
        raise RuntimeError("Unable to read user crontab for privacy migration")
    return result.stdout


def restore_crontab(original: bytes | None) -> None:
    if original is None:
        return
    if original:
        subprocess.run(["crontab", "-"], input=original, check=True)
    else:
        subprocess.run(["crontab", "-r"], check=False)


def apply(module_id: str, previous: dict, root: Path, system: bool,
          crontab: bytes | None) -> bool:
    changed = False
    if module_id == "privacy" and "privacy-scheduled" in previous:
        if system:
            path = root / "etc/cron.d/privacy-cleanup"
            if path.is_file() and not path.is_symlink():
                original = path.read_text(encoding="utf-8")
                if original.startswith("# managed by shell-scripts privacy\n"):
                    revised = original.replace("privacy-scheduled", "privacy")
                    revised = revised.replace("privacy --system", "privacy --system scheduled")
                    if revised != original:
                        path.write_text(revised, encoding="utf-8")
                        changed = True
        elif crontab is not None:
            lines = crontab.decode().splitlines(keepends=True)
            revised = b"".join((line.replace("privacy-scheduled", "privacy scheduled")
                                 if line.rstrip().endswith("# privacy-cleanup user") else line).encode()
                                for line in lines)
            if revised != crontab:
                subprocess.run(["crontab", "-"], input=revised, check=True)
                changed = True
    if module_id == "canary" and previous.keys() & {"fs-tracker", "canary-ssh-watcher"}:
        paths = files(module_id, previous, root, system)
        for record, unit in zip(paths[::2], paths[1::2]):
            original = unit.read_text(encoding="utf-8")
            revised = original.replace("/usr/local/bin/fs-tracker --config",
                                       "/usr/local/bin/canary tracker --config")
            revised = revised.replace("/usr/local/bin/canary-ssh-watcher --config",
                                       "/usr/local/bin/canary ssh-watch --config")
            if revised != original:
                unit.write_text(revised, encoding="utf-8")
                data = json.loads(record.read_text(encoding="utf-8"))
                data["unit_sha256"] = _digest(unit)
                record.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                changed = True
    return changed


def reload_canary(module_id: str, changed: bool, root: Path) -> None:
    if changed and module_id == "canary" and root == Path("/"):
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        # Restart only the services managed by this module.
        for unit in sorted((root / "var/lib/shell-scripts/canary").glob("*.json")):
            subprocess.run(["systemctl", "try-restart", f"fs-file-monitor-{unit.stem}.service"], check=True)
        if (root / "var/lib/shell-scripts/canary/ssh/record.json").is_file():
            subprocess.run(["systemctl", "try-restart", "fs-ssh-watch.service"], check=True)
