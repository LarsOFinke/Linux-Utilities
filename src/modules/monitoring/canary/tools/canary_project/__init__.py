"""canary_project package."""

from .cli import main
from .generator import build_project

__all__ = ["build_project", "main"]
