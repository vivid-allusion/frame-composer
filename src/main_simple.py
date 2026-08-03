"""Vivid Allusion Frame Composer — migrated to Engine interface.

Both studiolot and standalone modes share the same Engine-based execution.
The Vehicle reads bullets, loads an Engine, and calls engine.run().
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import yaml
from pathlib import Path
from typing import Any

from loguru import logger

from .auth import get_api_key
from .cli import parse_args
from .engine_loader import load_engine
from .exceptions import AuthenticationError, ConfigurationError, ValidationError
from .processing.markdown_parser import extract_all_image_urls, extract_prompt_text
from .processing.discovery import InputDiscovery
from .utils.logging import setup_logging

ENGINE_INSTALL_MESSAGE = (
    "To install an Engine:\n"
    "  git clone https://github.com/vivid-allusion/engine-replicate.git "
    "ENGINES/engine-replicate/\n"
    "  pip install -r ENGINES/engine-replicate/requirements.txt\n\n"
    "Or install via pip:\n"
    "  pip install engine-replicate\n\n"
    "Set your API key in .env:  REPLICATE_API_TOKEN=r8_...\n"
)

SUPPORTED_PLATFORMS = ["replicate", "fal", "openrouter", "google"]


def _read_bullets(input_dir: Path) -> list[dict[str, Any]]:
    """Read bullet .md files from input_dir, extract prompt + reference URLs."""
    md_files = sorted(input_dir.rglob("*.md"))
    bullets: list[dict[str, Any]] = []
    for md_path in md_files:
        content = md_path.read_text(encoding="utf-8")
        prompt = ""
        try:
            prompt = extract_prompt_text(content)
        except ValueError:
            pass
        urls: list[str] = []
        try:
            urls = extract_all_image_urls(content)
        except ValueError:
            pass
        bullets.append({"path": md_path, "prompt": prompt, "reference_urls": urls})
    if not bullets:
        logger.error(f"No .md files found in {input_dir}")
        raise FileNotFoundError(f"No .md files found in {input_dir}")
    logger.info(f"Discovered {len(bullets)} bullet(s) in {input_dir}")
    return bullets


def _load_profile_standalone() -> dict[str, Any]:
    """Load profile from USER-FILES for standalone mode."""
    profiles_dir = Path("USER-FILES/03.PROFILES")
    yamls = sorted(profiles_dir.glob("*.yaml")) + sorted(profiles_dir.glob("*.yml"))
    if not yamls:
        standby = Path("USER-FILES/02.STANDBY")
        yamls = sorted(standby.glob("*.yaml")) + sorted(standby.glob("*.yml"))
    if not yamls:
        raise ConfigurationError(
            "No profile found in USER-FILES/03.PROFILES/ or USER-FILES/02.STANDBY/"
        )
    data = yaml.safe_load(yamls[0].read_text(encoding="utf-8")) or {}
    data["profile_name"] = yamls[0].stem
    return data


def _load_profile_studiolot(profile_path: Path) -> dict[str, Any]:
    """Load profile YAML from --profile flag."""
    if not profile_path.exists():
        raise ConfigurationError(f"Profile not found: {profile_path}")
    data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    data["profile_name"] = profile_path.stem
    return data


def _find_project_engines_dir(start_dir: Path) -> Path | None:
    """Walk up from start_dir looking for 00_APPLICATIONS/ENGINES/."""
    current = start_dir.resolve()
    for _ in range(10):
        candidate = current / "00_APPLICATIONS" / "ENGINES"
        if candidate.is_dir():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def _find_vehicle_engines_dir() -> Path:
    """Return <vehicle-root>/ENGINES/."""
    return Path(__file__).resolve().parent.parent / "ENGINES"


def _print_engine_not_found(platform: str):
    sys.stderr.write(
        f"\nError: No Engine found for platform '{platform}'.\n"
        f"Supported platforms: {', '.join(SUPPORTED_PLATFORMS)}\n\n"
        f"{ENGINE_INSTALL_MESSAGE}"
    )


def _auto_install_engine(platform: str) -> bool:
    vehicle_root = Path(__file__).resolve().parent.parent
    engines_dir = vehicle_root / "ENGINES"
    engines_dir.mkdir(exist_ok=True)
    target = engines_dir / f"engine-{platform}"

    if target.is_dir():
        logger.info(f"Engine directory already exists: {target}")
        return True

    repo_url = f"https://github.com/vivid-allusion/engine-{platform}.git"
    logger.info(f"Cloning {repo_url} → {target}")
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


def _build_inputs(bullets, platform) -> list[Any]:
    """Construct InputFile objects using the Engine's datatype."""
    pkg = importlib.import_module(f"engine_{platform}")
    InputFile = pkg.InputFile
    return [
        InputFile(
            path=b["path"],
            prompt=b["prompt"],
            reference_urls=b["reference_urls"],
        )
        for b in bullets
    ]


def main():
    args = parse_args()
    is_studiolot = bool(args.profile or args.input_dir or args.output_dir)
    setup_logging(debug=args.debug)

    logger.info("=" * 60)
    logger.info("Vivid Allusion Frame Composer v2.1.0")
    logger.info("=" * 60)

    try:
        if is_studiolot:
            return _run_studiolot(args)
        else:
            return _run_standalone(args)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except (AuthenticationError, ConfigurationError, ValidationError) as e:
        logger.error(f"Error: {e}")
        return 1
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


def _run_studiolot(args) -> int:
    if not args.output_dir:
        raise ConfigurationError("--output_dir is required in studiolot mode")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_path = Path(args.profile) if args.profile else None
    if not profile_path:
        raise ConfigurationError("--profile is required in studiolot mode")

    profile = _load_profile_studiolot(profile_path)
    platform = profile.get("platform") or "replicate"

    input_dir = Path(args.input_dir) if args.input_dir else Path(".")

    bullets = _read_bullets(input_dir)

    if args.dry_run:
        logger.info(f"DRY RUN — would process {len(bullets)} bullet(s)")
        return 0

    api_key = get_api_key()

    project_engines = _find_project_engines_dir(output_dir)
    if not project_engines:
        raise FileNotFoundError(
            "Engine directory not found. Expected 00_APPLICATIONS/ENGINES/ "
            "under the project root."
        )

    engine = load_engine(
        platform=platform,
        search_paths=[project_engines],
        profile=profile,
        output_dir=output_dir,
        api_key=api_key,
        on_progress=lambda msg: logger.info(msg),
    )

    inputs = _build_inputs(bullets, platform)
    results = engine.run(inputs)

    ok = sum(1 for r in results if r.status == "ok")
    failed = sum(1 for r in results if r.status == "error")
    logger.success(f"Complete: {ok} generated, {failed} errors")

    for r in results:
        if r.status == "error":
            logger.error(f"  {r.bullet_path.name}: {r.error_msg}")

    return 1 if failed else 0


def _run_standalone(args) -> int:
    profile = _load_profile_standalone()
    platform = profile.get("platform") or "replicate"

    auto_install = args.install_default_engine or os.environ.get(
        "STUDIOLOT_AUTO_INSTALL_ENGINE"
    )

    from src.utils.path_resolver import (
        resolve_input_path,
        resolve_output_base_path,
        create_timestamped_output_path,
    )

    input_path, _ = resolve_input_path(
        {}, [profile], Path("USER-FILES/03.PROFILES")
    )
    output_base = resolve_output_base_path({}, [profile])
    output_dir = create_timestamped_output_path(output_base)

    bullets = _read_bullets(input_path)

    params = dict(profile.get("parameters", {}))
    if args.force_png:
        params["force_png"] = True
    if not args.save_payloads:
        params["save_payloads"] = False
    profile["parameters"] = params

    search_paths = [_find_vehicle_engines_dir()]

    api_key = None if args.dry_run else get_api_key()

    if args.cost_estimation:
        total = len(bullets)
        cost = profile.get("pricing", {}).get("base_cost", 0.0)
        logger.info(
            f"Estimated cost: {total} files × ${cost:.3f} = ${total * cost:.2f}"
        )
        return 0

    if args.dry_run:
        logger.info(f"DRY RUN — would process {len(bullets)} bullet(s)")
        return 0

    try:
        engine = load_engine(
            platform=platform,
            search_paths=search_paths,
            profile=profile,
            output_dir=output_dir,
            api_key=api_key,
            on_progress=lambda msg: logger.info(msg),
        )
    except FileNotFoundError:
        if auto_install:
            logger.info(f"Auto-installing Engine: {auto_install}")
            if _auto_install_engine(auto_install):
                engine = load_engine(
                    platform=platform,
                    search_paths=search_paths,
                    profile=profile,
                    output_dir=output_dir,
                    api_key=api_key,
                    on_progress=lambda msg: logger.info(msg),
                )
            else:
                return 1
        else:
            _print_engine_not_found(platform)
            logger.info(
                "Re-run with --install-default-engine=replicate "
                "to auto-install the default Engine."
            )
            return 1

    inputs = _build_inputs(bullets, platform)
    results = engine.run(inputs)

    ok = sum(1 for r in results if r.status == "ok")
    failed = sum(1 for r in results if r.status == "error")
    logger.success(f"Complete: {ok} generated, {failed} errors")

    for r in results:
        if r.status == "error":
            logger.error(f"  {r.bullet_path.name}: {r.error_msg}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
