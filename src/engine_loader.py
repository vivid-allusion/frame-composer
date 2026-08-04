"""Canonical Engine discovery and loading.

Per ENGINE_CONTRACT.md §7a: this is the single canonical implementation of
load_engine(). Vehicle repos vendor a snapshot copy — update here first,
then re-vendor.
"""

import importlib
import importlib.util
import re
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

    source = Path(pkg.__file__).parent / "profiles" / "standby"
    if not source.is_dir():
        return 0

    dest = vehicle_root / "USER-FILES" / "02.STANDBY"
    dest.mkdir(parents=True, exist_ok=True)

    count = 0
    for yaml_file in sorted(source.glob("*.yaml")):
        shutil.copy2(str(yaml_file), str(dest / yaml_file.name))
        count += 1

    return count


def seed_default_profile(platform: str, vehicle_root: Path | None = None) -> int:
    """Generate a minimal profile from engine endpoints and save to 02.STANDBY/.

    Used as a fallback when the engine package has no profiles/standby/ directory.
    Reads the first IMG-Models endpoint TOML to derive a working profile.

    Returns:
        1 if a profile was created, 0 otherwise.
    """
    if vehicle_root is None:
        vehicle_root = Path(__file__).resolve().parent.parent

    try:
        pkg = importlib.import_module(f"engine_{platform}")
    except ImportError:
        return 0

    pkg_dir = Path(pkg.__file__).parent
    endpoints_dir = pkg_dir / "endpoints" / "IMG-Models"
    if not endpoints_dir.is_dir():
        return 0

    toml_files = sorted(endpoints_dir.glob("*.toml"))
    if not toml_files:
        return 0

    content = toml_files[0].read_text()
    match = re.search(r'endpoint\s*=\s*"([^"]+)"', content)
    if not match:
        return 0
    endpoint = match.group(1)

    cost_match = re.search(r'base_cost\s*=\s*([0-9.]+)', content)
    base_cost = float(cost_match.group(1)) if cost_match else 0.001

    params: dict[str, object] = {}
    for pm in re.finditer(
        r"\[params\.(\w+)\]\n((?:(?!\[params\.).*\n?)*)", content
    ):
        name = pm.group(1)
        block = pm.group(2)
        dm = re.search(r"default\s*=\s*(.+)", block)
        if not dm or name in params:
            continue
        raw = dm.group(1).strip()
        if raw.startswith('"'):
            params[name] = raw.strip('"')
        elif raw == "true":
            params[name] = True
        elif raw == "false":
            params[name] = False
        else:
            try:
                params[name] = int(raw)
            except ValueError:
                try:
                    params[name] = float(raw)
                except ValueError:
                    params[name] = raw

    if params:
        param_lines = "\n".join(
            f"  {k}: {v!r}" if isinstance(v, str) else f"  {k}: {v}"
            for k, v in params.items()
        )
        param_block = f"parameters:\n{param_lines}"
    else:
        param_block = f"parameters: {{}}"

    profile_yaml = (
        f"# Auto-generated profile for {platform} — customise before use\n"
        f"platform: {platform}\n"
        f"endpoint: {endpoint}\n"
        f"media_type: image\n"
        f"{param_block}\n"
        f"pricing:\n"
        f"  base_cost: {base_cost}\n"
    )

    dest = vehicle_root / "USER-FILES" / "02.STANDBY"
    dest.mkdir(parents=True, exist_ok=True)
    profile_path = dest / f"default_{platform}.yaml"
    profile_path.write_text(profile_yaml)
    return 1
