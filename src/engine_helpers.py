"""Engine discovery, installation, input construction, and loading."""

import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from src.engine_contract import validate_input_file
from src.engine_loader import EngineLoadContext, copy_standby_profiles, load_engine
from src.types import MarkdownFile


def find_project_engines_dir(start_dir: Path, max_depth: int = 10) -> Path | None:
    """Walk up from start_dir looking for 00_APPLICATIONS/ENGINES/."""
    current = start_dir.resolve()
    for _ in range(max_depth):
        candidate = current / "00_APPLICATIONS" / "ENGINES"
        if candidate.is_dir():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def find_vehicle_engines_dir() -> Path:
    """Return <vehicle-root>/ENGINES/."""
    return Path(__file__).resolve().parent.parent / "ENGINES"


def print_engine_not_found(platform: str) -> None:
    from src.auth import SUPPORTED_PLATFORMS, _key_name

    lines = [f"\nError: No Engine found for platform '{platform}'.\n\n"]

    lines.append("Supported platforms:\n\n")
    for p in SUPPORTED_PLATFORMS:
        p_key = _key_name(p)
        marker = "  ← default" if p == platform else ""
        lines.append(f"  [{p}]{marker}\n")
        lines.append(f"    git clone https://github.com/vivid-allusion/engine-{p}.git "
                     f"ENGINES/engine-{p}/\n")
        lines.append(f"    pip install engine-{p}\n")
        lines.append(f"    {p_key}=...  (in .env)\n")
        lines.append("\n")

    lines.append(
        f"To auto-install the default engine:  python3 run.py --install-default-engine=replicate\n"
    )

    sys.stderr.write("".join(lines))


def auto_install_engine(platform: str) -> bool:
    vehicle_root = Path(__file__).resolve().parent.parent
    engines_dir = vehicle_root / "ENGINES"
    engines_dir.mkdir(exist_ok=True)
    target = engines_dir / f"engine-{platform}"

    if target.is_dir():
        logger.info(f"Engine directory already exists: {target}")
        return True

    repo_url = f"https://github.com/vivid-allusion/engine-{platform}.git"
    logger.info(f"Cloning {repo_url} -> {target}")
    result = subprocess.run(
        ["git", "clone", repo_url, str(target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"git clone failed: {result.stderr}")
        return False

    req = target / "requirements.txt"
    if req.exists():
        logger.info("Installing Engine dependencies...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
            check=False,
        )

    logger.success(f"Engine '{platform}' installed")
    return True


def build_inputs(md_files: list[MarkdownFile], platform: str) -> list[Any]:
    """Construct InputFile objects using the Engine's datatype."""
    try:
        pkg = importlib.import_module(f"engine_{platform}")
        InputFile = pkg.InputFile
    except (ImportError, AttributeError) as e:
        raise ImportError(
            f"Engine '{platform}' is missing or does not export InputFile: {e}"
        ) from e
    validate_input_file(InputFile, platform)
    return [
        InputFile(
            path=b["path"],
            prompt=b["prompt"],
            reference_urls=b["reference_urls"],
        )
        for b in md_files
    ]


def _emit_progress(msg: str) -> None:
    """Write progress message to stderr immediately.

    msg may be a str or a ProgressEvent (duck-typed — any object with .message).
    """
    text = msg.message if hasattr(msg, "message") else str(msg)
    sys.stderr.write(f"{text}\n")
    sys.stderr.flush()


def make_engine_ctx(
    platform: str,
    search_paths: list[Path],
    profile: dict[str, Any],
    output_dir: Path,
    api_key: str | None,
) -> EngineLoadContext:
    return EngineLoadContext(
        platform=platform,
        search_paths=search_paths,
        profile=profile,
        output_dir=output_dir,
        api_key=api_key,
        on_progress=lambda msg: _emit_progress(msg),
    )


def load_engine_or_install(
    platform: str,
    search_paths: list[Path],
    profile: dict[str, Any],
    output_dir: Path,
    api_key: str | None,
    auto_install: str | None = None,
) -> Any:
    """Load engine with optional auto-install fallback on FileNotFoundError."""
    ctx = make_engine_ctx(platform, search_paths, profile, output_dir, api_key)
    try:
        engine = load_engine(ctx)
    except FileNotFoundError:
        if not auto_install:
            raise
        logger.info(f"Auto-installing Engine: {auto_install}")
        if not auto_install_engine(auto_install):
            raise FileNotFoundError(
                f"Failed to auto-install engine '{auto_install}'"
            )
        engine = load_engine(ctx)
    copied = copy_standby_profiles(platform)
    if copied:
        logger.debug(f"Seeded {copied} standby profile(s) from engine-{platform}")
    return engine
