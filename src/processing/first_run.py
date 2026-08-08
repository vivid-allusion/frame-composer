"""First-run wizard path — engine check, interactive wizard, STANDBY seeding.

Extracted from _run_standalone() to keep main_simple.py under 250 lines.
"""

import sys
from pathlib import Path
from typing import Any

from loguru import logger

from ..auth import get_api_key_interactive
from ..engine_helpers import load_engine_or_install, print_engine_not_found
from ..utils.logging import add_file_logging
from ..utils.path_resolver import create_timestamped_output_path, resolve_output_base_path


def handle_first_run(
    platform: str,
    search_paths: list[Path],
    dry_run: bool,
    auto_install: str | None,
) -> tuple[str, str | None, Path] | None:
    """Check for engine, launch wizard if missing, seed STANDBY profiles.

    Returns (platform, api_key, output_dir) on success, None on non-TTY
    failure (caller should exit).
    """
    has_engine = False
    for sp in search_paths:
        try:
            for entry in sp.iterdir():
                if entry.is_dir() and entry.name.startswith("engine-"):
                    has_engine = True
                    platform = entry.name.removeprefix("engine-")
                    break
        except OSError:
            continue
        if has_engine:
            break

    api_key: str | None = None
    if not dry_run and not has_engine:
        if sys.stdin.isatty():
            platform, api_key = get_api_key_interactive()
            auto_install = platform
        else:
            print_engine_not_found(platform)
            return None

    profile: dict[str, Any] = {"platform": platform}
    output_base = resolve_output_base_path(profile)
    output_dir = create_timestamped_output_path(output_base)
    add_file_logging(output_dir)

    try:
        load_engine_or_install(
            platform, search_paths, profile, output_dir, api_key, auto_install
        )
    except FileNotFoundError:
        print_engine_not_found(platform)
        logger.info(
            "Re-run with --install-default-engine=replicate "
            "to auto-install the default Engine."
        )
        return None

    return platform, api_key, output_dir
