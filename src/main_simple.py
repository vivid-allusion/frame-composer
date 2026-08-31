"""Vivid Allusion Frame Composer — migrated to Engine interface.

Both studiolot and standalone modes share the same Engine-based execution.
The Vehicle reads markdowns, loads an Engine, and calls engine.run().
"""

import os
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from .auth import get_api_key, get_api_key_interactive
from .cli import parse_args
from .constants import DEFAULT_PLATFORM, __version__
from .datatypes import MarkdownFile
from .engine_helpers import (
    build_inputs,
    find_project_engines_dir,
    make_engine_ctx,
)
from .engine_loader import load_engine
from .exceptions import (
    AuthenticationError,
    ConfigurationError,
    PreflightExit,
    ValidationError,
)
from .processing.first_run import handle_first_run
from .processing.markdown_parser import read_markdown_files
from .processing.payload import embed_payloads
from .processing.placeholders import write_placeholders
from .processing.profiles import (
    load_profile_standalone,
    load_profile_studiolot,
)
from .utils.logging import setup_logging, start_output_capture, write_run_logs
from .utils.path_resolver import (
    resolve_input_path,
)

# ── CLI / orchestration helpers ────────────────────────────────────────────────


def _apply_cli_overrides(profile: dict[str, Any], args: Any) -> dict[str, Any]:
    """Return a copy of profile with CLI flags merged into parameters."""
    params = dict(profile.get("parameters", {}))
    if args.force_png:
        params["force_png"] = True
    return {**profile, "parameters": params}


def _handle_preflight_checks(
    args: Any, md_files: list[MarkdownFile], profile: dict[str, Any]
) -> None:
    if args.cost_estimation:
        total = len(md_files)
        cost = profile.get("pricing", {}).get("base_cost", 0.0)
        logger.info(f"Estimated cost: {total} files x ${cost:.3f} = ${total * cost:.2f}")
        raise PreflightExit(0)
    if args.dry_run:
        logger.info(f"DRY RUN -- would process {len(md_files)} markdown file(s)")
        raise PreflightExit(0)


def _report_results(results: list[Any], placeholders: int = 0) -> int:
    """Summarise engine.run() results and return exit code."""
    ok = sum(1 for r in results if r.status == "ok")
    failed = sum(1 for r in results if r.status == "error")
    missing = failed - placeholders
    parts = [f"{ok} generated"]
    if placeholders:
        parts.append(f"{placeholders} placeholders written")
    if missing:
        parts.append(f"{missing} errors")
    sys.stderr.write("Complete: " + ", ".join(parts) + "\n")
    for r in results:
        if r.status == "error":
            logger.error(f"  {r.source_path.name}: {r.error_msg}")
    return 1 if failed else 0


def _execute_pipeline(
    md_files: list[MarkdownFile],
    engine: Any,
    platform: str,
    profile: dict[str, Any],
    output_dir: Path,
    input_root: Path | None = None,
    save_payloads: bool = True,
) -> int:
    """Run the core generation pipeline: build inputs → run → report → log."""
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    inputs = build_inputs(md_files, platform, input_root)
    total = len(inputs)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
    ) as bar:
        task = bar.add_task("Processing...", total=total)

        def on_progress(msg: Any) -> None:
            text = msg.message if hasattr(msg, "message") else str(msg)
            bar.update(task, description=text)
            current = getattr(msg, "current", 0)
            if current:
                bar.update(task, completed=current)

        original = engine._on_progress
        engine._on_progress = on_progress
        try:
            results = engine.run(inputs)
        finally:
            engine._on_progress = original

    generated = [r.path for r in results if r.status == "ok" and getattr(r, "path", None)]
    placeholders = write_placeholders(
        results,
        md_files,
        profile,
        platform,
        engine,
        input_root,
        save_payloads=save_payloads,
    )
    exit_code = _report_results(results, len(placeholders))
    write_run_logs(generated + placeholders, output_dir)
    if save_payloads:
        embed_payloads(results, md_files, profile, platform, engine, input_root)
    return exit_code


def _resolve_engine_for_studiolot(
    output_dir: Path,
    platform: str,
    profile: dict[str, Any],
    api_key: str | None,
) -> Any:
    project_engines = find_project_engines_dir(output_dir)
    if not project_engines:
        raise FileNotFoundError(
            "Engine directory not found. Expected 00_APPLICATIONS/ENGINES/ "
            "under the project root."
        )
    return load_engine(make_engine_ctx(platform, [project_engines], profile, output_dir, api_key))


# ── entry point ────────────────────────────────────────────────────────────────


def main() -> int:
    args = parse_args()
    is_studiolot = bool(args.profile or args.input_dir or args.output_dir)
    start_output_capture()
    setup_logging(debug=args.debug, verbose=args.verbose)

    logger.debug("=" * 60)
    logger.debug(f"Vivid Allusion Frame Composer v{__version__}")
    logger.debug("=" * 60)

    try:
        if is_studiolot:
            return _run_studiolot(args)
        else:
            return _run_standalone(args)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except PreflightExit as e:
        return e.exit_code
    except (AuthenticationError, ConfigurationError, ValidationError) as e:
        logger.error(f"Error: {e}")
        return 1
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


# ── run modes ──────────────────────────────────────────────────────────────────


def _run_studiolot(args) -> int:
    if not args.output_dir:
        raise ConfigurationError("--output_dir is required in studiolot mode")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_path = Path(args.profile) if args.profile else None
    if not profile_path:
        raise ConfigurationError("--profile is required in studiolot mode")

    profile = load_profile_studiolot(profile_path)
    profile = _apply_cli_overrides(profile, args)
    platform = args.platform or profile.get("platform") or DEFAULT_PLATFORM
    profile["platform"] = platform

    input_dir = Path(args.input_dir) if args.input_dir else Path(".")

    md_files = read_markdown_files(input_dir)
    if not md_files:
        raise FileNotFoundError(f"No .md files found in {input_dir}")
    _handle_preflight_checks(args, md_files, profile)

    api_key = get_api_key(platform)
    engine = _resolve_engine_for_studiolot(output_dir, platform, profile, api_key)

    return _execute_pipeline(
        md_files,
        engine,
        platform,
        profile,
        output_dir,
        input_root=input_dir,
        save_payloads=args.save_payloads,
    )


def _run_standalone(args) -> int:
    search_paths = [Path(__file__).resolve().parent.parent / "ENGINES"]
    platform = DEFAULT_PLATFORM

    auto_install = args.install_default_engine or os.environ.get("STUDIOLOT_AUTO_INSTALL_ENGINE")

    result = handle_first_run(platform, search_paths, args.dry_run, auto_install)
    if result is None:
        return 1
    platform, api_key = result

    # ── active profile (STANDBY is now populated) ────────────────────────────

    try:
        profile = load_profile_standalone()
        platform = profile.get("platform") or platform
    except ConfigurationError:
        print(
            "\nThanks for supplying your API key. "
            "To make the script operational, pick a profile YAML\n"
            "from frame-composer/USER-FILES/02.STANDBY/ and copy it to\n"
            "frame-composer/USER-FILES/03.PROFILES/, then re-run.\n"
        )
        return 0

    profile = _apply_cli_overrides(profile, args)

    # ── check inputs before creating output dir ──────────────────────────────

    input_path, _ = resolve_input_path(profile)
    md_files = read_markdown_files(input_path)
    _handle_preflight_checks(args, md_files, profile)

    if not md_files:
        logger.warning(f"No .md files to process. Add .md files to {input_path} and re-run.")
        return 0

    # ── output directory (only created when generation is confirmed) ────────

    from .utils.path_resolver import create_timestamped_output_path, resolve_output_base_path

    output_base = resolve_output_base_path(profile)
    output_dir = create_timestamped_output_path(output_base)

    # ── API key (engine existed but wizard was skipped) ──────────────────────

    if not args.dry_run and api_key is None:
        try:
            api_key = get_api_key(platform)
        except AuthenticationError:
            if sys.stdin.isatty():
                platform, api_key = get_api_key_interactive()
                profile["platform"] = platform
            else:
                raise

    # ── engine with proper profile ───────────────────────────────────────────

    engine = load_engine(make_engine_ctx(platform, search_paths, profile, output_dir, api_key))

    return _execute_pipeline(
        md_files,
        engine,
        platform,
        profile,
        output_dir,
        input_root=input_path,
        save_payloads=args.save_payloads,
    )


if __name__ == "__main__":
    sys.exit(main())
