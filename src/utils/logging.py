"""Logging setup with loguru."""
from pathlib import Path
from loguru import logger
import sys


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the application."""
    logger.remove()

    level = "DEBUG" if debug else "WARNING"
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
               "<level>{message}</level>",
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
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
               "{name}:{function}:{line} - {message}",
    )

    logger.info(f"Logging configured (debug={debug})")
