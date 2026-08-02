"""Vendored Engine discovery and loading.

Snapshot from pipeline/engine_loader.py in studiolot.
Update the studiolot canonical copy first, then re-vendor.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from typing import Any


def load_engine(
    platform: str | None,
    search_paths: list[Path],
    profile: dict[str, Any],
    output_dir: str | Path,
    api_key: str | None = None,
    on_progress: Callable[[str], None] | None = None,
):
    """Find and load an Engine for the given platform.

    Args:
        platform: Engine platform name (e.g. "replicate", "fal").
                  None -> defaults to "replicate" (old-profile backward compat).
        search_paths: Directories to search for ``engine-<platform>/``.
        profile: Parsed profile YAML dict.
        output_dir: Where generated files are written.
        api_key: Provider API key (or None to use env var).
        on_progress: Optional progress callback.

    Returns:
        Engine instance.

    Raises:
        FileNotFoundError: No Engine directory found in search_paths.
        ImportError: Engine package exists but cannot be imported.
    """
    resolved = platform or "replicate"
    engine_dir_name = f"engine-{resolved}"

    engine_dir = None
    for sp in search_paths:
        candidate = sp / engine_dir_name
        if candidate.is_dir():
            engine_dir = candidate
            break

    if engine_dir is None:
        searched = "\n  ".join(str(sp / engine_dir_name) for sp in search_paths)
        raise FileNotFoundError(
            f"Engine '{resolved}' not found. Searched:\n  {searched}"
        )

    parent = str(engine_dir.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    import importlib

    pkg_name = f"engine_{resolved}"
    try:
        pkg = importlib.import_module(pkg_name)
    except ImportError:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                pkg_name, engine_dir / "__init__.py"
            )
            pkg = importlib.util.module_from_spec(spec)
            sys.modules[pkg_name] = pkg
            spec.loader.exec_module(pkg)
        except Exception:
            raise ImportError(
                f"Engine package '{pkg_name}' found at {engine_dir} but cannot be "
                f"imported. Check requirements: pip install -r "
                f"{engine_dir / 'requirements.txt'}"
            ) from None

    engine = pkg.Engine(
        profile=profile,
        output_dir=output_dir,
        api_key=api_key,
        on_progress=on_progress,
    )
    return engine
