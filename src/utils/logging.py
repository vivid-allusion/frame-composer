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


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the application."""
    logger.remove()

    level = "DEBUG" if debug else "WARNING"
    logger.add(
        sys.stderr,
        format=CONSOLE_FORMAT,
        level=level,
        colorize=True,
    )

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "frame_composer_{time}.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format=FILE_FORMAT,
    )

    logger.info(f"Logging configured (debug={debug})")
