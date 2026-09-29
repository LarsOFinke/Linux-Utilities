#!/usr/bin/env python3
"""Copy each module alone and exercise its standalone install/uninstall lifecycle."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
CATALOG = json.loads((REPOSITORY / "configuration/install.json").read_text(encoding="utf-8"))["modules"]


def run(command: list[str | Path], environment: dict[str, str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in command], env=environment, text=True, capture_output=True, check=True, **kwargs)


def main() -> None:
    helper = (REPOSITORY / "src/installation/portable_module.py").read_bytes()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        home = root / "home"
        install_root = root / "system"
        mock_bin = root / "bin"
        home.mkdir()
        install_root.mkdir()
        mock_bin.mkdir()
        crontab_state = root / "crontab"
        crontab = mock_bin / "crontab"
        crontab.write_text(
            "#!/usr/bin/env bash\n"
            'if [[ "$1" == -l ]]; then [[ -f "$MOCK_CRONTAB" ]] && cat "$MOCK_CRONTAB"; '
            'elif [[ "$1" == - ]]; then cat > "$MOCK_CRONTAB"; '
            'else cp -- "$1" "$MOCK_CRONTAB"; fi\n',
            encoding="utf-8",
        )
        crontab.chmod(0o755)
        environment = dict(
            os.environ,
            HOME=str(home),
            SHELL_SCRIPTS_INSTALL_ROOT=str(install_root),
            UU_ROOT=str(install_root),
            PRIVACY_ROOT=str(install_root),
            MOCK_CRONTAB=str(crontab_state),
            PYTHONDONTWRITEBYTECODE="1",
            PATH=f"{mock_bin}:{os.environ['PATH']}",
        )
        for name, manifest_path in CATALOG.items():
            copied = root / "modules" / name
            shutil.copytree((REPOSITORY / manifest_path).parent, copied,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            assert (copied / "portable_module.py").read_bytes() == helper, name
            manifest = json.loads((copied / "module.json").read_text(encoding="utf-8"))
            system = "user" not in manifest["scopes"]
            args = ["--system"] if system else []
            run([copied / "setup.sh", *args], environment, cwd=root)
            bin_dir = install_root / "usr/local/bin" if system else home / ".local/bin"
            for command in manifest["commands"]:
                assert (bin_dir / command).is_file(), (name, command)
            if name == "backup":
                source = root / "homes/sampleuser"
                source.mkdir(parents=True)
                (source / "data.txt").write_text("portable\n", encoding="utf-8")
                backup_env = dict(environment, BACKUP_SOURCE_ROOT=str(source.parent), BACKUP_ROOT=str(root / "archives"))
                run([bin_dir / "backup-home-cron", "sampleuser"], backup_env, cwd=root)
                assert (root / "archives/sampleuser/latest.tar.bz2").is_symlink()
                installed = bin_dir / "backup-home"
                original = installed.read_bytes()
                installed.write_bytes(original + b"# local edit\n")
                failed = subprocess.run([str(copied / "uninstall.sh")], env=environment, cwd=root,
                                        text=True, capture_output=True, check=False)
                assert failed.returncode != 0 and "changed locally" in failed.stderr
                assert installed.exists()
                installed.write_bytes(original)
            if name == "privacy":
                run([bin_dir / "privacy-cleanup", "configure"], environment, input="\n\n\n\n\n", cwd=root)
                assert "privacy-cleanup user" in crontab_state.read_text(encoding="utf-8")
            if name == "canary":
                run([bin_dir / "fs-tracker", "--help"], environment, cwd=root)
                target = root / "decoy.txt"
                target.write_text("decoy\n", encoding="utf-8")
                run([bin_dir / "canary-control", "configure", "demo", "--path", str(target),
                     "--log", str(root / "events.jsonl")], environment, cwd=root)
            run([copied / "uninstall.sh", *args], environment, cwd=root)
            for command in manifest["commands"]:
                assert not (bin_dir / command).exists(), (name, command)
            if name == "privacy":
                assert "privacy-cleanup user" not in crontab_state.read_text(encoding="utf-8")
            if name == "canary":
                assert not (install_root / "etc/fs-tracker/demo.conf").exists()
                assert target.exists()
        print("Portable module tests passed")


if __name__ == "__main__":
    main()
