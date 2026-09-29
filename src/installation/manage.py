#!/usr/bin/env python3
"""Install or remove the repository's command wrappers by module."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from catalog import CATALOG, MODULES, REPOSITORY, choose_targets, component_commands, installed_components, selection_options

DEFAULT_PROFILE_LINE = 'export PATH="$HOME/.local/bin:$PATH" # shell-scripts setup'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".registry.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def paths(system: bool) -> tuple[Path, Path, Path]:
    if system:
        prefix = Path(os.environ.get("SHELL_SCRIPTS_INSTALL_ROOT", "/")).resolve()
        if prefix == Path("/") and os.geteuid() != 0:
            raise RuntimeError("Use sudo for --system installation or removal.")
        return (
            prefix / CATALOG["scopes"]["system"]["bin_dir"],
            prefix / CATALOG["scopes"]["system"]["registry"],
            prefix,
        )
    home = Path.home()
    return (
        home / CATALOG["scopes"]["user"]["bin_dir"],
        home / CATALOG["scopes"]["user"]["registry"],
        home,
    )


def read_registry(path: Path, scope: str, bin_dir: Path) -> dict:
    if path.is_symlink():
        raise RuntimeError(f"Refusing symbolic-link registry: {path}")
    if not path.exists():
        return {
            "schema_version": 1,
            "scope": scope,
            "bin_dir": str(bin_dir),
            "modules": {},
            "profile_added": False,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("scope") != scope:
        raise RuntimeError(f"Unsupported or mismatched registry: {path}")
    if data.get("bin_dir") != str(bin_dir):
        raise RuntimeError(f"Registry uses a different command directory: {path}")
    if not isinstance(data.get("modules"), dict):
        raise RuntimeError(f"Registry has no valid module map: {path}")
    migrate_legacy_system_update(data)
    return data


def migrate_legacy_system_update(registry: dict) -> None:
    """Preserve ownership when the old system:update component becomes a module."""
    modules = registry["modules"]
    old = modules.get("system")
    if not old or "update-system" not in old["commands"]:
        return
    if "system-update" in modules:
        raise RuntimeError("Both system:update and system-update claim update-system in the registry")
    update = copy.deepcopy(old)
    update["commands"] = {"update-system": old["commands"].pop("update-system")}
    update["commands"]["update-system"]["source"] = str(
        REPOSITORY / MODULES["system-update"]["commands"]["update-system"])
    update["setup_script"] = str(REPOSITORY / MODULES["system-update"]["setup"])
    update["documentation"] = str(REPOSITORY / MODULES["system-update"]["documentation"])
    update["config_examples"] = []
    update["cron_templates"] = []
    update["managed_cron_files"] = {}
    update["runtime_configs"] = []
    update["schedules"] = []
    update["pre_remove"] = None
    update.pop("components", None)
    modules["system-update"] = update
    if old["commands"]:
        old["components"] = sorted(installed_components("system", {**old, "components": None}))
    else:
        del modules["system"]


def registry_inventory(registry: dict) -> dict[str, dict]:
    """Report registered ownership and check its installed files."""
    inventory = {}
    for module, entry in registry["modules"].items():
        components = ([name for name in MODULES[module]["components"]
                       if name in installed_components(module, entry)]
                      if module in MODULES and MODULES[module]["components"] else None)
        issues = []
        files = [(f"command {name}", Path(record["path"]), record["sha256"])
                 for name, record in entry["commands"].items()]
        files.extend((f"cron {path}", Path(path), record["sha256"])
                     for path, record in entry.get("managed_cron_files", {}).items())
        for label, path, recorded_hash in files:
            if path.is_symlink() or not path.is_file():
                issues.append(f"{label} is missing or not a regular file")
            else:
                try:
                    if sha256(path) != recorded_hash:
                        issues.append(f"{label} was modified")
                except OSError as error:
                    issues.append(f"{label} cannot be read: {error}")
        inventory[module] = {"components": components, "issues": issues}
    return inventory


def copy_command(source: Path, target: Path, executable: bool) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".shell-scripts.", dir=target.parent)
    os.close(descriptor)
    try:
        shutil.copyfile(source, temporary)
        os.chmod(temporary, 0o755 if executable else 0o644)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build_commands(selected: list[str], directory: Path,
                   components: dict[str, set[str] | None] | None = None) -> dict[tuple[str, str], Path]:
    built = {}
    for module in selected:
        requested = (components or {}).get(module)
        allowed = None if requested is None else component_commands(module, requested)
        for name, script in MODULES[module].get("build_commands", {}).items():
            if allowed is not None and name not in allowed:
                continue
            path = REPOSITORY / script
            if not path.is_file():
                raise RuntimeError(f"Missing build script for {module}: {path}")
            output = directory / f"{module}-{name}"
            subprocess.run([str(path), str(output)], check=True)
            if not output.is_file():
                raise RuntimeError(f"Build script did not produce {output}")
            built[module, name] = output
    return built


def restore_files(snapshots: dict[Path, tuple[bytes, int] | None]) -> None:
    for path, original in reversed(list(snapshots.items())):
        if original is None:
            path.unlink(missing_ok=True)
            continue
        contents, mode = original
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".shell-scripts-restore.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(contents)
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def ensure_user_path(home: Path, registry: dict, bin_dir: Path) -> Path | None:
    if str(bin_dir) in os.environ.get("PATH", "").split(os.pathsep):
        return None
    relative_bin = bin_dir.relative_to(home)
    profile_line = f'export PATH="$HOME/{relative_bin}:$PATH" # shell-scripts setup'
    profile = home / ".profile"
    content = profile.read_text(encoding="utf-8") if profile.exists() else ""
    if profile_line not in content:
        with profile.open("a", encoding="utf-8") as stream:
            stream.write(("" if not content or content.endswith("\n") else "\n") + profile_line + "\n")
        registry["profile_added"] = True
        registry["profile_line"] = profile_line
    return profile


def install(selected: list[str], registry: dict, bin_dir: Path, registry_path: Path, system: bool,
            built: dict[tuple[str, str], Path] | None = None,
            components: dict[str, set[str] | None] | None = None) -> None:
    changes = copy.deepcopy(registry)
    desired: dict[str, tuple[set[str], set[str] | None]] = {}
    writing: dict[str, set[str]] = {}
    for module in selected:
        definition = MODULES[module]
        requested = (components or {}).get(module)
        if requested is None or not definition["components"]:
            desired[module] = (set(definition["commands"]),
                               set(definition["components"]) if definition["components"] else None)
            writing[module] = set(definition["commands"])
        else:
            previous = registry["modules"].get(module)
            names = set(requested) | (installed_components(module, previous) if previous else set())
            desired[module] = (component_commands(module, names), names)
            writing[module] = component_commands(module, requested)
    targets: dict[Path, tuple[str, dict | None]] = {}
    stale: dict[Path, dict] = {}
    for module in selected:
        definition = MODULES[module]
        scope = "system" if system else "user"
        if scope not in definition["scopes"]:
            raise RuntimeError(f"{module} does not support {scope} installation; choose a supported scope.")
        sources = [definition["manifest"], definition["setup"], definition["documentation"]]
        sources.extend(definition["commands"][name] for name in writing[module])
        sources.extend(script for name, script in definition.get("build_commands", {}).items()
                       if name in writing[module])
        sources.extend(definition["examples"])
        sources.extend(definition["cron_templates"])
        if system and "system_cron" in definition:
            sources.append(definition["system_cron"]["source"])
        for source in sources:
            if not (REPOSITORY / source).is_file():
                raise RuntimeError(f"Missing source file for {module}: {source}")
    for module in selected:
        definition = MODULES[module]
        previous = registry["modules"].get(module, {}).get("commands", {})
        for name in writing[module]:
            target = bin_dir / name
            recorded = previous.get(name)
            if target in targets:
                raise RuntimeError(f"Selected modules share a command path: {target}")
            targets[target] = (module, recorded)
        for name, recorded in previous.items():
            if components is None or components.get(module) is None:
                obsolete = name not in desired[module][0]
            else:
                obsolete = False
            if obsolete:
                target = Path(recorded["path"])
                if target != bin_dir / name:
                    raise RuntimeError(f"Unexpected recorded command path: {target}")
                stale[target] = recorded
        previous_cron = registry["modules"].get(module, {}).get("managed_cron_files", {})
        if system and "system_cron" in definition:
            cron_name = definition["system_cron"]["name"]
            cron_target = paths(True)[2] / "etc/cron.d" / cron_name
            recorded = previous_cron.get(str(cron_target))
            if cron_target in targets:
                raise RuntimeError(f"Selected modules share a cron path: {cron_target}")
            targets[cron_target] = (module, recorded)
        for path, recorded in previous_cron.items():
            if not system or "system_cron" not in definition or path != str(cron_target):
                stale[Path(path)] = recorded

    for other, entry in registry["modules"].items():
        if other in selected:
            continue
        for record in entry["commands"].values():
            if Path(record["path"]) in targets or Path(record["path"]) in stale:
                raise RuntimeError(f"Installed modules share an owned path: {record['path']}")
        for path in entry.get("managed_cron_files", {}):
            if Path(path) in targets or Path(path) in stale:
                raise RuntimeError(f"Installed modules share an owned path: {path}")
    if stale.keys() & targets.keys():
        raise RuntimeError("An obsolete file is also used by a selected module; uninstall first.")
    for target, (_, recorded) in targets.items():
        if target.is_symlink() or (target.exists() and not recorded):
            raise RuntimeError(f"Refusing to replace an unmanaged file: {target}")
        if target.exists() and recorded and sha256(target) != recorded["sha256"]:
            raise RuntimeError(f"Installed file changed locally: {target}")
    for target, record in stale.items():
        if target.is_symlink():
            raise RuntimeError(f"Refusing symbolic-link obsolete file: {target}")
        if target.exists() and sha256(target) != record["sha256"]:
            raise RuntimeError(f"Obsolete installed file changed locally: {target}")

    snapshots: dict[Path, tuple[bytes, int] | None] = {}
    profile = Path.home() / ".profile"
    if not system and profile.is_symlink():
        raise RuntimeError(f"Refusing symbolic-link profile: {profile}")
    for target in list(targets) + list(stale) + [registry_path] + ([] if system else [profile]):
        snapshots[target] = (target.read_bytes(), target.stat().st_mode & 0o777) if target.exists() else None
    profile_notice = None
    try:
        bin_dir.mkdir(parents=True, exist_ok=True)
        for module in selected:
            definition = MODULES[module]
            commands = ({} if components is None or components.get(module) is None
                        else copy.deepcopy(changes["modules"].get(module, {}).get("commands", {})))
            for name, source_relative in definition["commands"].items():
                if name not in writing[module]:
                    continue
                source = (built or {}).get((module, name), REPOSITORY / source_relative)
                target = bin_dir / name
                copy_command(source, target, name not in definition.get("non_executable_commands", []))
                commands[name] = {"path": str(target), "source": str(REPOSITORY / source_relative), "sha256": sha256(target)}
            managed_cron_files = {}
            if system and "system_cron" in definition:
                cron = definition["system_cron"]
                cron_target = paths(True)[2] / "etc/cron.d" / cron["name"]
                cron_target.parent.mkdir(parents=True, exist_ok=True)
                source = REPOSITORY / cron["source"]
                copy_command(source, cron_target, False)
                managed_cron_files[str(cron_target)] = {"source": str(source), "sha256": sha256(cron_target)}
            scope = "system" if system else "user"
            base = paths(system)[2]
            changes["modules"][module] = {
                "commands": commands,
                "setup_script": str(REPOSITORY / definition["setup"]),
                "documentation": str(REPOSITORY / definition["documentation"]),
                "config_examples": [str(REPOSITORY / item) for item in definition["examples"]],
                "cron_templates": [str(REPOSITORY / item) for item in definition["cron_templates"]],
                "managed_cron_files": managed_cron_files,
                "runtime_configs": [str(base / item) for item in definition.get("runtime_configs", {}).get(scope, [])],
                "schedules": [item if item.startswith("user crontab:") else str(base / item) for item in definition.get("schedules", {}).get(scope, [])],
                "pre_remove": definition.get("pre_remove"),
            }
            if desired[module][1] is not None:
                changes["modules"][module]["components"] = sorted(desired[module][1])
        for target in stale:
            target.unlink(missing_ok=True)
        changes["repository"] = str(REPOSITORY)
        changes["updated_at"] = datetime.now(timezone.utc).isoformat()
        if not system:
            profile_notice = ensure_user_path(Path.home(), changes, bin_dir)
        atomic_json(registry_path, changes)
    except Exception as error:
        try:
            restore_files(snapshots)
        except OSError as rollback_error:
            raise RuntimeError(f"Install failed: {error}; rollback failed: {rollback_error}") from error
        raise
    if profile_notice is not None:
        print(f"Open a new shell or run: source {profile_notice}")
    for module in selected:
        definition = MODULES[module]
        print(f"Installed {module}: {', '.join(name for name in definition['commands'] if name in writing[module] and name not in definition.get('non_executable_commands', []))}")
    print(f"Registry: {registry_path}")


def remove_profile_line(home: Path, registry: dict) -> None:
    if not registry.get("profile_added"):
        return
    profile = home / ".profile"
    if not profile.exists():
        return
    lines = profile.read_text(encoding="utf-8").splitlines()
    profile_line = registry.get("profile_line", DEFAULT_PROFILE_LINE)
    profile.write_text("\n".join(line for line in lines if line != profile_line) + "\n", encoding="utf-8")
    registry["profile_added"] = False


def uninstall(
    selected: list[str],
    registry: dict,
    registry_path: Path,
    system: bool,
    base: Path,
    force: bool,
    purge_config: bool,
    components: dict[str, set[str] | None] | None = None,
) -> None:
    for module in selected:
        entry = registry["modules"][module]
        requested = (components or {}).get(module)
        if requested is None:
            removing = set(entry["commands"])
            owned = set()
        else:
            owned = installed_components(module, entry)
            if not requested <= owned:
                raise RuntimeError(f"Component is not installed for {module}: {', '.join(sorted(requested - owned))}")
            removing = component_commands(module, requested)
        for name in removing:
            record = entry["commands"][name]
            target = Path(record["path"])
            if target.is_symlink():
                raise RuntimeError(f"Refusing symbolic-link command: {target}")
            if target.exists() and not force and sha256(target) != record["sha256"]:
                raise RuntimeError(f"Installed command changed locally: {target}; use --force to remove it.")
        for path, record in (entry.get("managed_cron_files", {}) if requested is None else {}).items():
            target = Path(path)
            if target.is_symlink():
                raise RuntimeError(f"Refusing symbolic-link cron file: {target}")
            if target.exists() and not force and sha256(target) != record["sha256"]:
                raise RuntimeError(f"Installed cron file changed locally: {target}; use --force to remove it.")
        hook = (entry.get("pre_remove") or MODULES.get(module, {}).get("pre_remove")) if requested is None else None
        if hook:
            command = entry["commands"][hook["command"]]
            target = Path(command["path"])
            if not target.is_file() or target.is_symlink() or sha256(target) != command["sha256"]:
                raise RuntimeError(f"Cannot safely run {module} removal hook with a missing or changed command: {target}")
            hook_args = [str(target)]
            if system and hook.get("system_arg"):
                hook_args.append(hook["system_arg"])
            hook_args.extend(hook["args"])
            if purge_config and hook.get("purge_arg"):
                hook_args.append(hook["purge_arg"])
            environment = dict(os.environ)
            if hook.get("root_env"):
                environment[hook["root_env"]] = str(base)
            subprocess.run(hook_args, env=environment, check=True)
        for name in removing:
            record = entry["commands"][name]
            target = Path(record["path"])
            if target.is_file() and not target.is_symlink():
                target.unlink()
        for path in (entry.get("managed_cron_files", {}) if requested is None else {}):
            target = Path(path)
            if target.is_file() and not target.is_symlink():
                target.unlink()
        if requested is None or requested == installed_components(module, entry):
            del registry["modules"][module]
        else:
            for name in removing:
                del entry["commands"][name]
            entry["components"] = sorted(owned - requested)
        registry["updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json(registry_path, registry)
        label = module if requested is None else ", ".join(f"{module}:{name}" for name in sorted(requested))
        print(f"Removed {label}")
    if not registry["modules"] and not system:
        remove_profile_line(base, registry)
        atomic_json(registry_path, registry)
    print(f"Registry: {registry_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "uninstall"])
    parser.add_argument("--system", action="store_true", help="Use /usr/local/bin and the system registry")
    parser.add_argument("--module", action="append", default=[], help="Select a module by name; repeatable")
    parser.add_argument("--component", action="append", default=[], metavar="MODULE:NAME",
                        help="Select an independently managed component; repeatable")
    parser.add_argument("--all", action="store_true", help="Select all available modules")
    parser.add_argument("--list", action="store_true", help="List available or installed modules")
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--force", action="store_true", help="Remove locally modified installed commands")
    parser.add_argument("--purge-config", action="store_true", help="Also delete privacy runtime configuration")
    args = parser.parse_args()
    bin_dir, registry_path, base = paths(args.system)
    registry = read_registry(registry_path, "system" if args.system else "user", bin_dir)
    available = sorted(MODULES if args.action == "install" else registry["modules"])
    available_components = (None if args.action == "install" else
                            {module: installed_components(module, registry["modules"][module])
                             for module in available if module in MODULES and MODULES[module]["components"]})
    if args.list:
        if args.json:
            print(json.dumps(registry_inventory(registry) if args.action == "uninstall" else {}))
            return 0
        print("\n".join(selection_options(available, available_components)))
        return 0
    if not available:
        raise RuntimeError("No installed modules are recorded.")
    selection = choose_targets(args.module, args.component, args.all, available,
                               available_components=available_components)
    selected = list(selection)
    if args.action == "install":
        with tempfile.TemporaryDirectory(prefix="linux-utilities-build-") as directory:
            built = build_commands(selected, Path(directory), selection)
            install(selected, registry, bin_dir, registry_path, args.system, built, selection)
    else:
        uninstall(selected, registry, registry_path, args.system, base, args.force, args.purge_config, selection)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Linux-Utilities setup: {error}", file=sys.stderr)
        sys.exit(1)
