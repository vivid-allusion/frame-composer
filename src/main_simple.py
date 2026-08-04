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
from .engine_helpers import (

    build_inputs,
    find_project_engines_dir,
    load_engine_or_install,
    make_engine_ctx,
    print_engine_not_found,
)
from .engine_loader import load_engine
from .exceptions import (
    AuthenticationError,
    ConfigurationError,
    PreflightExit,
    ValidationError,
)
from .processing.markdown_parser import extract_all_image_urls, extract_prompt_text
from .processing.profiles import (
    load_profile_standalone,
    load_profile_studiolot,
)
from .types import MarkdownFile
from .utils.logging import add_file_logging, setup_logging
from .utils.path_resolver import (
    create_timestamped_output_path,
    resolve_input_path,
    resolve_output_base_path,
)

# ── markdown parsing ──────────────────────────────────────────────────────


def _read_markdown_files(input_dir: Path) -> list[MarkdownFile]:
    """Read .md files from input_dir, extract prompt + reference URLs."""
    md_files = sorted(input_dir.rglob("*.md"))
    result: list[MarkdownFile] = []
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
        result.append({"path": md_path, "prompt": prompt, "reference_urls": urls})
    if not result:
        logger.warning(f"No .md files found in {input_dir}")
        return result
    logger.info(f"Discovered {len(result)} markdown file(s) in {input_dir}")
    return result


# ── CLI / orchestration helpers ────────────────────────────────────────────────


def _apply_cli_overrides(profile: dict[str, Any], args: Any) -> dict[str, Any]:
    """Return a copy of profile with CLI flags merged into parameters."""
    params = dict(profile.get("parameters", {}))
    if args.force_png:
        params["force_png"] = True
    if not args.save_payloads:
        params["save_payloads"] = False
    return {**profile, "parameters": params}


def _handle_preflight_checks(
    args: Any, md_files: list[MarkdownFile], profile: dict[str, Any]
) -> None:
    if args.cost_estimation:
        total = len(md_files)
        cost = profile.get("pricing", {}).get("base_cost", 0.0)
        logger.info(
            f"Estimated cost: {total} files x ${cost:.3f} = ${total * cost:.2f}"
        )
        raise PreflightExit(0)
    if args.dry_run:
        logger.info(f"DRY RUN -- would process {len(md_files)} markdown file(s)")
        raise PreflightExit(0)


def _report_results(results: list[Any]) -> int:
    """Summarise engine.run() results and return exit code."""
    from rich.console import Console

    console = Console()
    ok = sum(1 for r in results if r.status == "ok")
    failed = sum(1 for r in results if r.status == "error")

    if failed:
        console.print(f"\n[bold red]✗ {failed} failed[/bold red]  [green]✓ {ok} ok[/green]")
    else:
        console.print(f"\n[bold green]✓ All {ok} generated successfully[/bold green]")

    for r in results:
        if r.status == "error":
            console.print(f"  [red]{r.source_path.name}[/red]: {r.error_msg}")
        else:
            console.print(f"  [dim]{r.source_path.name}[/dim] → [green]{r.path}[/green]")
    return 1 if failed else 0


def _execute_pipeline(
    md_files: list[MarkdownFile], engine: Any, platform: str
) -> int:
    """Run the core generation pipeline: build inputs → run → report."""
    from rich.console import Console

    console = Console()
    inputs = build_inputs(md_files, platform)
    total = len(inputs)

    with console.status(f"[cyan]Sending {total} markdown file(s) to AI model...[/cyan]") as status:
        results = engine.run(inputs)

    return _report_results(results)


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
    return load_engine(
        make_engine_ctx(platform, [project_engines], profile, output_dir, api_key)
    )


# ── entry point ────────────────────────────────────────────────────────────────


def main() -> int:
    args = parse_args()
    is_studiolot = bool(args.profile or args.input_dir or args.output_dir)
    setup_logging(debug=args.debug)

    logger.info("=" * 60)
    logger.info(f"Vivid Allusion Frame Composer v{__version__}")
    logger.info("=" * 60)

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
    add_file_logging(output_dir)

    profile_path = Path(args.profile) if args.profile else None
    if not profile_path:
        raise ConfigurationError("--profile is required in studiolot mode")

    profile = load_profile_studiolot(profile_path)
    profile = _apply_cli_overrides(profile, args)
    platform = profile.get("platform") or DEFAULT_PLATFORM

    input_dir = Path(args.input_dir) if args.input_dir else Path(".")

    md_files = _read_markdown_files(input_dir)
    _handle_preflight_checks(args, md_files, profile)

    api_key = get_api_key(platform)
    engine = _resolve_engine_for_studiolot(output_dir, platform, profile, api_key)

    return _execute_pipeline(md_files, engine, platform)


def _run_standalone(args) -> int:
    search_paths = [Path(__file__).resolve().parent.parent / "ENGINES"]
    platform = DEFAULT_PLATFORM

    auto_install = args.install_default_engine or os.environ.get(
        "STUDIOLOT_AUTO_INSTALL_ENGINE"
    )

    # ── engine check (must come first — seeds STANDBY) ───────────────────────

    has_engine = any((sp / f"engine-{platform}").is_dir() for sp in search_paths)

    api_key: str | None = None
    if not args.dry_run and not has_engine:
        if sys.stdin.isatty():
            platform, api_key = get_api_key_interactive()
            auto_install = platform
        else:
            print_engine_not_found(platform)
            return 1

    # ── engine install (before profile — populates STANDBY shelf) ────────────

    profile = {"platform": platform}
    output_base = resolve_output_base_path(profile)
    output_dir = create_timestamped_output_path(output_base)
    add_file_logging(output_dir)

    try:
        engine = load_engine_or_install(
            platform, search_paths, profile, output_dir, api_key, auto_install
        )
    except FileNotFoundError:
        print_engine_not_found(platform)
        logger.info(
            "Re-run with --install-default-engine=replicate "
            "to auto-install the default Engine."
        )
        return 1

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

    # ── API key (engine existed but wizard was skipped) ──────────────────────

    if not args.dry_run and has_engine and api_key is None:
        try:
            api_key = get_api_key(platform)
        except AuthenticationError:
            if sys.stdin.isatty():
                platform, api_key = get_api_key_interactive()
                profile["platform"] = platform
            else:
                raise

    # ── engine with proper profile ───────────────────────────────────────────

    engine = load_engine(
        make_engine_ctx(platform, search_paths, profile, output_dir, api_key)
    )

    # ── processing phase ─────────────────────────────────────────────────────

    input_path, _ = resolve_input_path(profile)
    md_files = _read_markdown_files(input_path)
    _handle_preflight_checks(args, md_files, profile)

    if not md_files:
        logger.warning(
            f"No .md files to process. Add .md files to {input_path} and re-run."
        )
        return 0

    return _execute_pipeline(md_files, engine, platform)


if __name__ == "__main__":
    sys.exit(main())
