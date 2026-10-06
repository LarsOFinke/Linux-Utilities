#!/usr/bin/env python3
"""Follow SSH journal entries and write selected events as private JSONL."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from canary_ssh_events import classify, selected


def append_event(path, event):
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
            descriptor = -1
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    finally:
        if descriptor != -1:
            os.close(descriptor)


def watch(config):
    command = ["journalctl", "--follow", "--lines=0", "--output=json",
               "--identifier=sshd", "--identifier=sshd-session"]
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True) as journal:
        for line in journal.stdout:
            try:
                event = classify(json.loads(line))
            except json.JSONDecodeError:
                continue
            if not selected(event, config):
                continue
            append_event(config["log"], event)
            if config.get("action"):
                result = subprocess.run([config["action"]], input=json.dumps(event) + "\n",
                                        text=True, check=False)
                if result.returncode:
                    print(f"canary-ssh-watcher: action exited {result.returncode}", file=sys.stderr)
        if journal.wait() != 0:
            raise RuntimeError("journalctl stopped; systemd will restart the SSH watcher")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    if args.config.is_symlink():
        raise RuntimeError("refusing a symlinked SSH watcher config")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    watch(config)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        print(f"canary-ssh-watcher: {error}", file=sys.stderr)
        sys.exit(1)
