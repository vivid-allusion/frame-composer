"""Result helpers shared across pipeline stages."""

from pathlib import Path
from typing import Any


def is_success(result: Any) -> bool:
    """True when a result generated successfully and carries an output path."""
    return getattr(result, "status", "") == "ok" and getattr(result, "path", None) is not None


def success_paths(results: list[Any]) -> list[Path]:
    """Return the output paths of successful results, in order."""
    return [r.path for r in results if is_success(r)]
