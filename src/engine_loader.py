"""Canonical Engine discovery and loading.

Per ENGINE_CONTRACT.md §7a: this is the single canonical implementation of
load_engine(). Vehicle repos vendor a snapshot copy — update here first,
then re-vendor.
"""

import importlib
import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import DEFAULT_PLATFORM

if TYPE_CHECKING:
    from typing import Any, Callable


@dataclass
class EngineLoadContext:
    """Bundled parameters for `load_engine()`.

    Collapses the old 6-param signature into a single typed object.
    """

    platform: str | None
    search_paths: list[Path]
    profile: dict[str, Any]
    output_dir: str | Path
    api_key: str | None = None
    on_progress: Callable[[str], None] | None = None


def load_engine(ctx: EngineLoadContext):
    """Find and load an Engine for the given platform.

    Args:
        ctx: EngineLoadContext with platform, search_paths, profile,
             output_dir, and optional api_key / on_progress.

    Returns:
        Engine instance.

    Raises:
        FileNotFoundError: No Engine directory found in search_paths.
        ImportError: Engine package exists but cannot be imported.
    """
    resolved = ctx.platform or DEFAULT_PLATFORM
    engine_dir_name = f"engine-{resolved}"

    engine_dir = None
    for sp in ctx.search_paths:
        candidate = sp / engine_dir_name
        if candidate.is_dir():
            engine_dir = candidate
            break

    if engine_dir is None:
        searched = "\n  ".join(
            str(sp / engine_dir_name) for sp in ctx.search_paths
        )
        raise FileNotFoundError(
            f"Engine '{resolved}' not found. Searched:\n  {searched}"
        )

    root = str(engine_dir)
    if root not in sys.path:
        sys.path.insert(0, root)

    pkg_name = f"engine_{resolved}"

    spec = importlib.util.spec_from_file_location(
        pkg_name, engine_dir / pkg_name / "__init__.py"
    )
    pkg = None
    if spec is not None:
        try:
            pkg = importlib.util.module_from_spec(spec)
            sys.modules[pkg_name] = pkg
            spec.loader.exec_module(pkg)
        except Exception:
            pkg = None

    if pkg is None:
        try:
            pkg = importlib.import_module(pkg_name)
        except ImportError:
            raise ImportError(
                f"Engine package '{pkg_name}' found at {engine_dir} but "
                f"cannot be imported. Check requirements: pip install -r "
                f"{engine_dir / 'requirements.txt'}"
            ) from None

    engine = pkg.Engine(
        profile=ctx.profile,
        output_dir=ctx.output_dir,
        api_key=ctx.api_key,
        on_progress=ctx.on_progress,
    )
    return engine


def copy_standby_profiles(platform: str, vehicle_root: Path | None = None) -> int:
    """Copy standby YAML profiles from engine package to Vehicle's 02.STANDBY/.

    Args:
        platform: Engine platform name (e.g. 'replicate').
        vehicle_root: Vehicle project root.  Defaults to two levels above this file.

    Returns:
        Number of profile files copied.
    """
    if vehicle_root is None:
        vehicle_root = Path(__file__).resolve().parent.parent

    try:
        pkg = importlib.import_module(f"engine_{platform}")
    except ImportError:
        return 0

    profile_files: list[Path] = []
    if hasattr(pkg, "list_standby_profiles"):
        profile_files = pkg.list_standby_profiles()
    else:
        source = Path(pkg.__file__).parent / "profiles" / "standby"
        if source.is_dir():
            profile_files = sorted(source.glob("*.yaml"))

    if not profile_files:
        return 0

    dest = vehicle_root / "USER-FILES" / "02.STANDBY"
    dest.mkdir(parents=True, exist_ok=True)

    count = 0
    for yaml_file in profile_files:
        shutil.copy2(str(yaml_file), str(dest / yaml_file.name))
        count += 1

    return count
