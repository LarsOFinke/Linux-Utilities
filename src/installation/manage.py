#!/usr/bin/env python3
"""Install or remove the repository's command wrappers by module."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY / "configuration/install.json"
DEFAULT_PROFILE_LINE = 'export PATH="$HOME/.local/bin:$PATH" # shell-scripts setup'


def relative_path(value: str, label: str) -> Path:
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[a-zA-Z0-9_./-]+", value)
        or Path(value).is_absolute()
        or ".." in Path(value).parts
        or Path(value) == Path(".")
    ):
        raise SystemExit(f"Invalid {label} in {CATALOG_PATH}: {value!r}")
    return Path(value)


def load_catalog() -> dict:
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot read installation catalog {CATALOG_PATH}: {error}") from error
    if not isinstance(data, dict) or data.get("schema_version") != 2:
        raise SystemExit(f"Unsupported installation catalog: {CATALOG_PATH}")
    scopes = data.get("scopes")
    references = data.get("modules")
    if not isinstance(scopes, dict) or not isinstance(references, dict) or not references:
        raise SystemExit(f"Invalid scopes or modules in {CATALOG_PATH}")
    for scope in ("user", "system"):
        definition = scopes.get(scope)
        if not isinstance(definition, dict):
            raise SystemExit(f"Missing {scope} scope in {CATALOG_PATH}")
        for field in ("bin_dir", "registry"):
            relative_path(definition.get(field), f"{scope}.{field}")

    modules = {}
    for module, reference in references.items():
        if not isinstance(module, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", module):
            raise SystemExit(f"Invalid module name in {CATALOG_PATH}: {module!r}")
        manifest_relative = relative_path(reference, f"{module}.manifest")
        manifest_path = REPOSITORY / manifest_relative
        try:
            source = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"Cannot read module manifest {manifest_path}: {error}") from error
        if not isinstance(source, dict) or source.get("schema_version") != 1 or source.get("id") != module:
            raise SystemExit(f"Invalid module manifest: {manifest_path}")
        for field in ("display_name", "category", "description"):
            value = source.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > 120:
                raise SystemExit(f"Invalid {module}.{field} in {manifest_path}")
        supported_scopes = source.get("scopes")
        if (not isinstance(supported_scopes, list) or not supported_scopes or
                any(not isinstance(scope, str) or scope not in ("user", "system") for scope in supported_scopes) or
                len(set(supported_scopes)) != len(supported_scopes)):
            raise SystemExit(f"Invalid {module}.scopes in {manifest_path}")
        def source_path(value: str, label: str) -> str:
            return str(manifest_relative.parent / relative_path(value, label))

        definition = {key: source[key] for key in ("display_name", "category", "description")}
        definition["scopes"] = supported_scopes
        definition["system_only"] = "user" not in supported_scopes
        definition["manifest"] = str(manifest_relative)
        for field in ("setup", "documentation"):
            definition[field] = source_path(source.get(field), f"{module}.{field}")
        commands = source.get("commands")
        if not isinstance(commands, dict) or not commands:
            raise SystemExit(f"Invalid {module}.commands in {manifest_path}")
        definition["commands"] = {}
        for name, path in commands.items():
            if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name):
                raise SystemExit(f"Invalid command name: {name!r}")
            definition["commands"][name] = source_path(path, f"{module}.commands.{name}")
        helpers = source.get("non_executable_commands", [])
        if not isinstance(helpers, list) or any(name not in commands for name in helpers):
            raise SystemExit(f"Invalid {module}.non_executable_commands in {manifest_path}")
        definition["non_executable_commands"] = helpers
        for field in ("examples", "cron_templates"):
            items = source.get(field)
            if not isinstance(items, list):
                raise SystemExit(f"Invalid {module}.{field} in {manifest_path}")
            definition[field] = [source_path(item, f"{module}.{field}") for item in items]
        cron = source.get("system_cron")
        if cron is not None:
            if not isinstance(cron, dict) or not isinstance(cron.get("name"), str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", cron["name"]):
                raise SystemExit(f"Invalid {module}.system_cron in {manifest_path}")
            definition["system_cron"] = {"name": cron["name"], "source": source_path(cron.get("source"), f"{module}.system_cron.source")}
        builds = source.get("build_commands", {})
        if not isinstance(builds, dict) or any(name not in commands for name in builds):
            raise SystemExit(f"Invalid {module}.build_commands in {manifest_path}")
        definition["build_commands"] = {name: source_path(script, f"{module}.build_commands.{name}") for name, script in builds.items()}
        hook = source.get("pre_remove")
        if hook is not None:
            if not isinstance(hook, dict) or hook.get("command") not in commands or not isinstance(hook.get("args"), list) or any(not isinstance(arg, str) for arg in hook["args"]):
                raise SystemExit(f"Invalid {module}.pre_remove in {manifest_path}")
            for field in ("system_arg", "purge_arg"):
                if field in hook and not isinstance(hook[field], str):
                    raise SystemExit(f"Invalid {module}.pre_remove.{field} in {manifest_path}")
            if "root_env" in hook and (not isinstance(hook["root_env"], str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", hook["root_env"])):
                raise SystemExit(f"Invalid {module}.pre_remove.root_env in {manifest_path}")
            definition["pre_remove"] = hook
        post_install = source.get("post_install")
        if post_install is not None:
            if not isinstance(post_install, dict) or post_install.get("command") not in commands or not isinstance(post_install.get("args"), list) or any(not isinstance(arg, str) for arg in post_install["args"]):
                raise SystemExit(f"Invalid {module}.post_install in {manifest_path}")
            if not isinstance(post_install.get("prompt"), str) or not post_install["prompt"].strip():
                raise SystemExit(f"Invalid {module}.post_install.prompt in {manifest_path}")
            for field in ("system_arg", "root_env"):
                if field in post_install and not isinstance(post_install[field], str):
                    raise SystemExit(f"Invalid {module}.post_install.{field} in {manifest_path}")
            if "root_env" in post_install and not re.fullmatch(r"[A-Z][A-Z0-9_]*", post_install["root_env"]):
                raise SystemExit(f"Invalid {module}.post_install.root_env in {manifest_path}")
            definition["post_install"] = post_install
        for field in ("runtime_configs", "schedules"):
            scoped = source.get(field, {})
            if not isinstance(scoped, dict) or any(key not in ("user", "system") for key in scoped):
                raise SystemExit(f"Invalid {module}.{field} in {manifest_path}")
            for scope, items in scoped.items():
                if not isinstance(items, list):
                    raise SystemExit(f"Invalid {module}.{field}.{scope} in {manifest_path}")
                for item in items:
                    if field == "schedules" and scope == "user" and isinstance(item, str) and item.startswith("user crontab: ") and "\n" not in item:
                        continue
                    relative_path(item, f"{module}.{field}.{scope}")
            definition[field] = scoped
        modules[module] = definition
    data["modules"] = modules
    return data


CATALOG = load_catalog()
MODULES = CATALOG["modules"]


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
    return data


def choose_modules(
    requested: list[str],
    all_modules: bool,
    available: list[str],
    descriptions: dict[str, str] | None = None,
) -> list[str]:
    if all_modules:
        return available
    if requested:
        unknown = set(requested) - set(available)
        if unknown:
            raise RuntimeError(f"Unknown or uninstalled module: {', '.join(sorted(unknown))}")
        return list(dict.fromkeys(requested))
    if not sys.stdin.isatty():
        raise RuntimeError("Choose modules with --module NAME or --all.")
    print("Modules:")
    for index, name in enumerate(available, 1):
        description = f" — {descriptions[name]}" if descriptions and name in descriptions else ""
        print(f"  {index}. {name}{description}")
    while True:
        try:
            answer = input("Select numbers separated by commas, 'all', or 'q': ").strip()
        except EOFError as error:
            raise RuntimeError("Selection cancelled.") from error
        if answer == "all":
            return available
        if answer.lower() in {"q", "quit"}:
            raise RuntimeError("Selection cancelled.")
        try:
            indices = [int(piece.strip()) for piece in answer.split(",")]
            if any(index < 1 or index > len(available) for index in indices):
                raise ValueError("Module number is out of range")
            selected = [available[index - 1] for index in indices]
        except (ValueError, IndexError):
            print("Enter listed numbers, 'all', or 'q'.")
            continue
        return list(dict.fromkeys(selected))


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


def build_commands(selected: list[str], directory: Path) -> dict[tuple[str, str], Path]:
    built = {}
    for module in selected:
        for name, script in MODULES[module].get("build_commands", {}).items():
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
            built: dict[tuple[str, str], Path] | None = None) -> None:
    changes = copy.deepcopy(registry)
    targets: dict[Path, tuple[str, dict | None]] = {}
    stale: dict[Path, dict] = {}
    for module in selected:
        definition = MODULES[module]
        scope = "system" if system else "user"
        if scope not in definition["scopes"]:
            raise RuntimeError(f"{module} does not support {scope} installation; choose a supported scope.")
        sources = [definition["manifest"], definition["setup"], definition["documentation"]]
        sources.extend(definition["commands"].values())
        sources.extend(definition.get("build_commands", {}).values())
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
        for name in definition["commands"]:
            target = bin_dir / name
            recorded = previous.get(name)
            if target in targets:
                raise RuntimeError(f"Selected modules share a command path: {target}")
            targets[target] = (module, recorded)
        for name, recorded in previous.items():
            if name not in definition["commands"]:
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
            commands = {}
            for name, source_relative in definition["commands"].items():
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
        print(f"Installed {module}: {', '.join(name for name in definition['commands'] if name not in definition.get('non_executable_commands', []))}")
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
) -> None:
    for module in selected:
        entry = registry["modules"][module]
        for name, record in entry["commands"].items():
            target = Path(record["path"])
            if target.is_symlink():
                raise RuntimeError(f"Refusing symbolic-link command: {target}")
            if target.exists() and not force and sha256(target) != record["sha256"]:
                raise RuntimeError(f"Installed command changed locally: {target}; use --force to remove it.")
        for path, record in entry.get("managed_cron_files", {}).items():
            target = Path(path)
            if target.is_symlink():
                raise RuntimeError(f"Refusing symbolic-link cron file: {target}")
            if target.exists() and not force and sha256(target) != record["sha256"]:
                raise RuntimeError(f"Installed cron file changed locally: {target}; use --force to remove it.")
        hook = entry.get("pre_remove") or MODULES.get(module, {}).get("pre_remove")
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
        for record in entry["commands"].values():
            target = Path(record["path"])
            if target.is_file() and not target.is_symlink():
                target.unlink()
        for path in entry.get("managed_cron_files", {}):
            target = Path(path)
            if target.is_file() and not target.is_symlink():
                target.unlink()
        del registry["modules"][module]
        registry["updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json(registry_path, registry)
        print(f"Removed {module}")
    if not registry["modules"] and not system:
        remove_profile_line(base, registry)
        atomic_json(registry_path, registry)
    print(f"Registry: {registry_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "uninstall"])
    parser.add_argument("--system", action="store_true", help="Use /usr/local/bin and the system registry")
    parser.add_argument("--module", action="append", default=[], help="Select a module by name; repeatable")
    parser.add_argument("--all", action="store_true", help="Select all available modules")
    parser.add_argument("--list", action="store_true", help="List available or installed modules")
    parser.add_argument("--force", action="store_true", help="Remove locally modified installed commands")
    parser.add_argument("--purge-config", action="store_true", help="Also delete privacy runtime configuration")
    args = parser.parse_args()
    bin_dir, registry_path, base = paths(args.system)
    registry = read_registry(registry_path, "system" if args.system else "user", bin_dir)
    available = sorted(MODULES if args.action == "install" else registry["modules"])
    if args.list:
        print("\n".join(available))
        return 0
    if not available:
        raise RuntimeError("No installed modules are recorded.")
    selected = choose_modules(args.module, args.all, available)
    if args.action == "install":
        with tempfile.TemporaryDirectory(prefix="linux-utilities-build-") as directory:
            built = build_commands(selected, Path(directory))
            install(selected, registry, bin_dir, registry_path, args.system, built)
    else:
        uninstall(selected, registry, registry_path, args.system, base, args.force, args.purge_config)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Linux-Utilities setup: {error}", file=sys.stderr)
        sys.exit(1)
