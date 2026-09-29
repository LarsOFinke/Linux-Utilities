"""Create and remove named Canary services."""

import json
import os
import subprocess

from canary_state import (BIN, CONFIG, ROOT, UNITS, atomic_write, digest, fail,
                          name_path, owned_files, runtime_path, systemctl, verify_owned)


def configure(args):
    state = name_path(args.name)
    config = CONFIG / f"{args.name}.conf"
    unit = UNITS / f"fs-file-monitor-{args.name}.service"
    target = runtime_path(args.path, "target")
    log = runtime_path(args.log, "log")
    action = runtime_path(args.action, "action") if args.action else None
    if not BIN.is_file() or BIN.is_symlink():
        fail(f"install the canary module first: {BIN}")
    if not target.is_file():
        fail(f"target file must exist: {target}")
    if target.resolve() == log.resolve():
        fail("log and target must be different files")
    if action and (not action.is_file() or not os.access(action, os.X_OK)):
        fail(f"action must be executable: {action}")
    for path in (state, config, unit):
        if path.exists() or path.is_symlink():
            fail(f"refusing to replace existing file: {path}")
    config_text = f"TRACK_PATH={target}\nTRACK_LOG={log}\n"
    if action:
        config_text += f"TRACK_ACTION={action}\n"
    unit_text = (f"[Unit]\nDescription=File activity monitor ({args.name})\nAfter=local-fs.target\n\n"
                 f"[Service]\nType=simple\nUMask=0077\nExecStart={BIN} --config {config}\nRestart=on-failure\n\n"
                 "[Install]\nWantedBy=multi-user.target\n")
    try:
        log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write(config, config_text, 0o600)
        atomic_write(unit, unit_text, 0o644)
        record = {"name": args.name, "target": str(target), "log": str(log),
                  "config_sha256": digest(config), "unit_sha256": digest(unit)}
        atomic_write(state, json.dumps(record, indent=2) + "\n", 0o600)
        systemctl("daemon-reload")
        systemctl("enable", "--now", unit.name)
    except Exception:
        if ROOT == Path("/"):
            subprocess.run(["systemctl", "disable", "--now", unit.name], check=False)
        state.unlink(missing_ok=True)
        config.unlink(missing_ok=True)
        unit.unlink(missing_ok=True)
        raise
    print(f"Configured {args.name}: {unit.name}")


def remove_one(record):
    verify_owned(record)
    unit = f"fs-file-monitor-{record['name']}.service"
    systemctl("disable", "--now", unit)
    for path, _ in owned_files(record):
        path.unlink()
    name_path(record["name"]).unlink()
    systemctl("daemon-reload")
    print(f"Removed {record['name']}; target and log retained")
