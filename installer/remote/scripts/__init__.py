"""Small dependency-free programs sent to SSH targets."""

from pathlib import Path


def source(name: str) -> str:
    """Read a fixed remote program for execution with ``python3 -c``."""
    if name not in {"bootstrap", "scan"}:
        raise ValueError(f"Unknown remote script: {name}")
    return (Path(__file__).parent / f"{name}.py").read_text(encoding="utf-8")
