"""Logging setup with loguru + complete run-output capture.

Capture lets every generated file ship a full-run log beside it:
`<generated-file-stem>.log` mirrors the image/video name so runs are
traceable from the output directory alone.
"""

import io
import re
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
    "<level>{message}</level>"
)

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

_capture: io.StringIO | None = None


class _TeeStream(io.TextIOBase):
    """Forward writes to the real stream while capturing a plain-text copy."""

    def __init__(self, target: io.TextIOBase) -> None:
        self._target = target

    def write(self, data: str) -> int:
        if _capture is not None:
            _capture.write(_ANSI_ESCAPE.sub("", data))
        return self._target.write(data)

    def flush(self) -> None:
        self._target.flush()

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return self._target.isatty()

    def fileno(self) -> int:
        return self._target.fileno()

    @property
    def encoding(self) -> str:
        return getattr(self._target, "encoding", "utf-8")


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


def start_output_capture() -> None:
    """Tee stdout/stderr into a buffer so the full run output can be logged."""
    global _capture
    _capture = io.StringIO()
    sys.stdout = _TeeStream(sys.stdout)  # type: ignore[assignment]
    sys.stderr = _TeeStream(sys.stderr)  # type: ignore[assignment]


def captured_output() -> str:
    """Return everything written to stdout/stderr since capture started."""
    return _capture.getvalue() if _capture is not None else ""


def write_run_logs(generated_paths: list[Path], output_dir: Path) -> list[Path]:
    """Write one complete-run log per generated file, named after the file.

    Falls back to a single timestamped log in output_dir when nothing was
    generated, so failed runs still leave a debug trail.
    """
    text = captured_output()
    if generated_paths:
        written: list[Path] = []
        for gen_path in generated_paths:
            log_path = gen_path.with_suffix(".log")
            log_path.write_text(text)
            written.append(log_path)
        return written

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = output_dir / f"frame_composer_{ts}.log"
    log_path.write_text(text)
    return [log_path]
