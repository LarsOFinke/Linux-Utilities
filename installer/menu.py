"""Persistent interactive entry menu; explicit command-line actions remain one-shot."""
import os
from pathlib import Path
import subprocess
import sys

REPOSITORY = Path(__file__).resolve().parents[1]


def main():
    if not sys.stdin.isatty():
        print("Run with a terminal, or use ./main.sh setup|update|uninstall [options].", file=sys.stderr)
        return 2
    while True:
        print("\nLinux-Utilities\n"
              "  1. Setup — choose categories, modules and components\n"
              "  2. Update installed modules\n"
              "  3. Uninstall selected modules\n"
              "  4. Browse available modules (read-only)\n"
              "  5. Setup for all users (system scope; requires sudo)\n"
              "  0. Exit\n"
              "Nothing is installed until you select modules. Use b to go back in selectors.")
        try:
            choice = input("Choose an action [0-5, q]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nLeaving Linux-Utilities.")
            return 0
        if choice in {"0", "q", "quit", "exit"}:
            return 0
        actions = {"1": ["setup"], "2": ["update"], "3": ["uninstall"],
                   "4": ["setup", "--list"], "5": ["setup", "--system"],
                   "setup": ["setup"], "update": ["update"], "uninstall": ["uninstall"]}
        if choice not in actions:
            print("Enter a listed number, or q to exit.")
            continue
        action, *options = actions[choice]
        try:
            command = [str(REPOSITORY / "scripts" / (action + ".sh")), *options]
            if choice == "5" and os.geteuid() != 0:
                command = ["sudo", "--", *command]
            status = subprocess.run(command).returncode
        except OSError as error:
            print(f"Could not start {action}: {error}", file=sys.stderr)
            continue
        except KeyboardInterrupt:
            print("\nAction interrupted. Review its output before retrying.")
            continue
        if status == 0:
            print("\nFinished. Choose another action or 0 to exit.")
        elif status != 3:
            print(f"\nAction stopped (status {status}). Review the output; you can retry or choose 0 to exit.")


if __name__ == "__main__":
    raise SystemExit(main())
