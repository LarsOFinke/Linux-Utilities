#!/usr/bin/env python3
"""Exercise each module with the portable helper bundled only in an SSH archive."""

from __future__ import annotations

import json
import io
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY / "installer"))
from remote.deploy import archive_module

CATALOG = json.loads((REPOSITORY / "configuration/install.json").read_text(encoding="utf-8"))["modules"]


def run(command: list[str | Path], environment: dict[str, str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in command], env=environment, text=True, capture_output=True, check=True, **kwargs)


def main() -> None:
    helper = (REPOSITORY / "installer/portable/portable_module.py").read_bytes()
    support = REPOSITORY / "installer/portable/portable_support"
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
            source_dir = (REPOSITORY / manifest_path).parent
            assert not (source_dir / "portable_module.py").exists(), name
            assert not (source_dir / "portable_support").exists(), name
            archive_root = root / "modules" / name
            archive_root.mkdir(parents=True)
            with tarfile.open(fileobj=io.BytesIO(archive_module(name)), mode="r:gz") as archive:
                packaged = set(archive.getnames())
                archive.extractall(archive_root)
            bundle = archive_root / "module"
            assert (bundle / "portable_module.py").read_bytes() == helper, name
            for source in support.glob("*.py"):
                assert (bundle / "portable_support" / source.name).read_bytes() == source.read_bytes(), (name, source.name)
            assert "module/portable_module.py" in packaged
            assert all(f"module/portable_support/{source.name}" in packaged for source in support.glob("*.py"))
            manifest = json.loads((bundle / "module.json").read_text(encoding="utf-8"))
            system = "user" not in manifest["scopes"]
            args = ["--system"] if system else []
            run(["python3", bundle / "portable_module.py", "install", *args], environment, cwd=root)
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
                failed = subprocess.run(["python3", str(bundle / "portable_module.py"), "uninstall"], env=environment, cwd=root,
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
            if name == "system":
                # An older install had inline H848 templates. Refresh adds the new files.
                state_path = home / ".local/state/shell-scripts/portable/system.json"
                state = json.loads(state_path.read_text(encoding="utf-8"))
                for command in ("h848_wireplumber_05.conf", "h848_wireplumber_04.lua", "h848_audio_guard.service"):
                    (bin_dir / command).unlink()
                    del state["commands"][command]
                state_path.write_text(json.dumps(state), encoding="utf-8")
                run(["python3", bundle / "portable_module.py", "update", "--component", "h848-audio"], environment, cwd=root)
                assert all((bin_dir / command).is_file() for command in
                           ("h848_wireplumber_05.conf", "h848_wireplumber_04.lua", "h848_audio_guard.service"))
            run(["python3", bundle / "portable_module.py", "uninstall", *args], environment, cwd=root)
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
