"""Logging setup with loguru."""

import sys
from pathlib import Path

from loguru import logger

CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
    "<level>{message}</level>"
)

FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
    "{name}:{function}:{line} - {message}"
)


def setup_logging(debug: bool = False, verbose: bool = False) -> None:
    """Configure console logging for the application."""
    logger.remove()

    level = "DEBUG" if debug else "INFO"
    logger.add(
        sys.stderr,
        format=CONSOLE_FORMAT,
        level=level,
        colorize=True,
    )

    logger.debug(f"Logging configured (debug={debug})")


def add_file_logging(output_dir: Path) -> None:
    """Attach a file log sink to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        output_dir / "frame_composer_{time}.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format=FILE_FORMAT,
    )
