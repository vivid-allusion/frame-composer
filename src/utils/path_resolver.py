"""Path resolution utilities with USER-FILES fallback."""

from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.constants import TIMESTAMP_FORMAT

USER_FILES_INPUT = Path("USER-FILES/04.INPUT")
USER_FILES_OUTPUT = Path("USER-FILES/05.OUTPUT")
OUTPUT_DIR_SUFFIX = "_IMG"


def resolve_input_path(
    profile: dict[str, Any],
) -> tuple[Path, str | None]:
    custom_input_path = profile.get("paths", {}).get("input")
    project_name = profile.get("project", "") if custom_input_path else None

    if custom_input_path:
        input_path = Path(custom_input_path)
        logger.info(f"Using custom input path: {input_path}")
    else:
        input_path = USER_FILES_INPUT
        logger.info(f"Using default input path: {input_path}")

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_path}")

    return input_path, project_name


def resolve_output_base_path(
    profile: dict[str, Any],
) -> Path:
    custom_output_path = profile.get("paths", {}).get("output")

    if custom_output_path:
        output_base = Path(custom_output_path)
        logger.info(f"Using custom output path: {output_base}")
    else:
        output_base = USER_FILES_OUTPUT
        logger.info(f"Using default output path: {output_base}")

    return output_base


def create_timestamped_output_path(base_path: Path) -> Path:
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    output_path = base_path / f"{timestamp}{OUTPUT_DIR_SUFFIX}"
    output_path.mkdir(parents=True, exist_ok=True)

    return output_path
