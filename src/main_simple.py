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
from .utils.logging import setup_logging
from .utils.path_resolver import (
    create_timestamped_output_path,
    resolve_input_path,
    resolve_output_base_path,
)

# ── shared helpers ──────────────────────────────────────────────────────────


def _read_bullets(input_dir: Path) -> list[dict[str, Any]]:
    """Read bullet .md files from input_dir, extract prompt + reference URLs."""
    md_files = sorted(input_dir.rglob("*.md"))
    bullets: list[dict[str, Any]] = []
    for md_path in md_files:
        content = md_path.read_text(encoding="utf-8")
        prompt = ""
        try:
            prompt = extract_prompt_text(content)
        except ValueError as e:
            logger.warning(f"Failed to extract prompt from {md_path.name}: {e}")
        urls: list[str] = []
        try:
            urls = extract_all_image_urls(content)
        except ValueError as e:
            logger.warning(f"Failed to extract URLs from {md_path.name}: {e}")
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


def _find_project_engines_dir(start_dir: Path, max_depth: int = 10) -> Path | None:
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


def _find_vehicle_engines_dir() -> Path:
    """Return <vehicle-root>/ENGINES/."""
    return Path(__file__).resolve().parent.parent / "ENGINES"


def _print_engine_not_found(platform: str):
    from .auth import _key_name

    key_name = _key_name(platform)
    sys.stderr.write(
        f"\nError: No Engine found for platform '{platform}'.\n\n"
        f"To install an Engine:\n"
        f"  git clone https://github.com/vivid-allusion/engine-{platform}.git "
        f"ENGINES/engine-{platform}/\n"
        f"  pip install -r ENGINES/engine-{platform}/requirements.txt\n\n"
        f"Or install via pip:\n"
        f"  pip install engine-{platform}\n\n"
        f"Set your API key in .env:  {key_name}=...\n"
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


def _build_inputs(bullets: list[dict[str, Any]], platform: str) -> list[Any]:
    """Construct InputFile objects using the Engine's datatype."""
    try:
        pkg = importlib.import_module(f"engine_{platform}")
        InputFile = pkg.InputFile
    except (ImportError, AttributeError) as e:
        raise ImportError(
            f"Engine '{platform}' is missing or does not export InputFile: {e}"
        ) from e
    return [
        InputFile(
            path=b["path"],
            prompt=b["prompt"],
            reference_urls=b["reference_urls"],
        )
        for b in bullets
    ]


def _report_results(results: list[Any]) -> int:
    """Summarise engine.run() results and return exit code."""
    ok = sum(1 for r in results if r.status == "ok")
    failed = sum(1 for r in results if r.status == "error")
    logger.success(f"Complete: {ok} generated, {failed} errors")
    for r in results:
        if r.status == "error":
            logger.error(f"  {r.bullet_path.name}: {r.error_msg}")
    return 1 if failed else 0


def _call_load_engine(
    platform: str,
    search_paths: list[Path],
    profile: dict[str, Any],
    output_dir: Path,
    api_key: str | None,
) -> Any:
    return load_engine(
        platform=platform,
        search_paths=search_paths,
        profile=profile,
        output_dir=output_dir,
        api_key=api_key,
        on_progress=lambda msg: logger.info(msg),
    )


def _load_engine_or_install(
    platform: str,
    search_paths: list[Path],
    profile: dict[str, Any],
    output_dir: Path,
    api_key: str | None,
    auto_install: str | None = None,
) -> Any:
    """Load engine with optional auto-install fallback on FileNotFoundError."""
    try:
        return _call_load_engine(platform, search_paths, profile, output_dir, api_key)
    except FileNotFoundError:
        if not auto_install:
            raise
        logger.info(f"Auto-installing Engine: {auto_install}")
        if not _auto_install_engine(auto_install):
            raise FileNotFoundError(
                f"Failed to auto-install engine '{auto_install}'"
            )
        return _call_load_engine(platform, search_paths, profile, output_dir, api_key)


def _apply_cli_overrides(profile: dict[str, Any], args: Any) -> dict[str, Any]:
    """Return a copy of profile with CLI flags merged into parameters."""
    params = dict(profile.get("parameters", {}))
    if args.force_png:
        params["force_png"] = True
    if not args.save_payloads:
        params["save_payloads"] = False
    return {**profile, "parameters": params}


# ── entry point ─────────────────────────────────────────────────────────────


def main() -> int:
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


# ── run modes ───────────────────────────────────────────────────────────────


def _resolve_engine_for_studiolot(
    output_dir: Path,
    platform: str,
    profile: dict[str, Any],
    api_key: str | None,
) -> Any:
    project_engines = _find_project_engines_dir(output_dir)
    if not project_engines:
        raise FileNotFoundError(
            "Engine directory not found. Expected 00_APPLICATIONS/ENGINES/ "
            "under the project root."
        )
    return _call_load_engine(platform, [project_engines], profile, output_dir, api_key)


def _run_studiolot(args) -> int:
    if not args.output_dir:
        raise ConfigurationError("--output_dir is required in studiolot mode")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_path = Path(args.profile) if args.profile else None
    if not profile_path:
        raise ConfigurationError("--profile is required in studiolot mode")

    profile = _load_profile_studiolot(profile_path)
    profile = _apply_cli_overrides(profile, args)
    platform = profile.get("platform") or "replicate"

    input_dir = Path(args.input_dir) if args.input_dir else Path(".")

    bullets = _read_bullets(input_dir)

    if args.dry_run:
        logger.info(f"DRY RUN -- would process {len(bullets)} bullet(s)")
        return 0

    api_key = get_api_key(platform)
    engine = _resolve_engine_for_studiolot(output_dir, platform, profile, api_key)

    inputs = _build_inputs(bullets, platform)
    results = engine.run(inputs)
    return _report_results(results)


def _handle_preflight_checks(args, bullets: list[dict[str, Any]], profile: dict[str, Any]) -> int | None:
    if args.cost_estimation:
        total = len(bullets)
        cost = profile.get("pricing", {}).get("base_cost", 0.0)
        logger.info(
            f"Estimated cost: {total} files x ${cost:.3f} = ${total * cost:.2f}"
        )
        return 0

    if args.dry_run:
        logger.info(f"DRY RUN -- would process {len(bullets)} bullet(s)")
        return 0

    return None


def _run_standalone(args) -> int:
    profile = _load_profile_standalone()
    platform = profile.get("platform") or "replicate"

    auto_install = args.install_default_engine or os.environ.get(
        "STUDIOLOT_AUTO_INSTALL_ENGINE"
    )

    input_path, _ = resolve_input_path(profile)
    output_base = resolve_output_base_path(profile)
    output_dir = create_timestamped_output_path(output_base)

    bullets = _read_bullets(input_path)

    profile = _apply_cli_overrides(profile, args)
    search_paths = [_find_vehicle_engines_dir()]

    api_key = None if args.dry_run else get_api_key(platform)

    early_exit = _handle_preflight_checks(args, bullets, profile)
    if early_exit is not None:
        return early_exit

    try:
        engine = _load_engine_or_install(
            platform, search_paths, profile, output_dir, api_key, auto_install
        )
    except FileNotFoundError:
        _print_engine_not_found(platform)
        logger.info(
            "Re-run with --install-default-engine=replicate "
            "to auto-install the default Engine."
        )
        return 1

    inputs = _build_inputs(bullets, platform)
    results = engine.run(inputs)
    return _report_results(results)


if __name__ == "__main__":
    sys.exit(main())
