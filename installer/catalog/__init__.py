"""Validated repository catalog and component ownership helpers."""

from __future__ import annotations

from catalog.commands import component_commands as _component_commands
from catalog.commands import installed_components as _installed_components
from catalog.loader import load_catalog
from catalog.source import CATALOG_PATH, REPOSITORY, relative_path

CATALOG = load_catalog()
MODULES = CATALOG["modules"]


def component_commands(module: str, names: set[str]) -> set[str]:
    return _component_commands(module, names, MODULES)


def installed_components(module: str, entry: dict) -> set[str]:
    return _installed_components(module, entry, MODULES)


__all__ = ["CATALOG", "CATALOG_PATH", "MODULES", "REPOSITORY", "relative_path",
           "load_catalog", "component_commands", "installed_components"]
