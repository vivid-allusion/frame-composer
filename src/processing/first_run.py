"""First-run wizard path — engine check, interactive wizard, STANDBY seeding.

Extracted from _run_standalone() to keep main_simple.py under 250 lines.
"""

import sys
from pathlib import Path
from typing import Any

from loguru import logger

from ..auth import get_api_key_interactive
from ..engine_helpers import (
    load_engine_or_install,
    make_engine_ctx,
    print_engine_not_found,
)
from ..engine_loader import find_first_engine_dir


def handle_first_run(
    platform: str,
    search_paths: list[Path],
    dry_run: bool,
    auto_install: str | None,
) -> tuple[str, str | None] | None:
    """Check for engine, launch wizard if missing, seed STANDBY profiles.

    Returns (platform, api_key) on success, None on non-TTY
    failure (caller should exit).
    """
    platform, has_engine = _detect_engine_platform(search_paths, platform)

    api_key: str | None = None
    if not dry_run and not has_engine:
        if sys.stdin.isatty():
            platform, api_key = get_api_key_interactive()
            auto_install = platform
        else:
            print_engine_not_found(platform)
            return None

    profile: dict[str, Any] = {"platform": platform}
    ctx = make_engine_ctx(platform, search_paths, profile, Path("/tmp"), api_key)

    try:
        load_engine_or_install(ctx, auto_install)
    except FileNotFoundError:
        print_engine_not_found(platform)
        logger.info(
            "Re-run with --install-default-engine=replicate " "to auto-install the default Engine."
        )
        return None

    return platform, api_key


def _detect_engine_platform(search_paths: list[Path], fallback: str) -> tuple[str, bool]:
    """Return (platform, has_engine) from the first engine-* dir found."""
    found = find_first_engine_dir(search_paths)
    if found is None:
        return fallback, False
    return found[1], True
