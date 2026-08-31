"""Logging setup with loguru + complete run-output capture.

Capture reduces raw terminal output to plain text (ANSI sequences stripped,
CR redraws collapsed) so every generated file can ship a readable,
LLM-friendly log beside it: `<generated-file-stem>.log`.
"""

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from ..constants import __version__
from ..datatypes import MarkdownFile
from ..processing.payload import error_info

CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
    "<level>{message}</level>"
)


class _TerminalCleaner:
    """Reduce raw terminal output to the plain text a terminal shows.

    Strips CSI/OSC escape sequences and collapses CR redraws, handling
    sequences split across write boundaries.
    """

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._line: list[str] = []
        self._esc = ""
        self._osc_prev = ""

    def feed(self, text: str) -> None:
        """Process one chunk of output text."""
        for ch in text:
            self._feed_char(ch)

    def text(self) -> str:
        """Return the cleaned text, flushing any partial trailing line."""
        return "".join(self._lines) + "".join(self._line)

    def _feed_char(self, ch: str) -> None:
        if self._esc == "csi":
            if "\x40" <= ch <= "\x7e":
                self._esc = ""
            return
        if self._esc == "osc":
            if ch == "\x07":
                self._esc = ""
            elif ch == "\\" and self._osc_prev == "\x1b":
                self._esc = ""
            self._osc_prev = ch
            return
        if self._esc == "esc":
            self._esc = ""
            if ch == "[":
                self._esc = "csi"
            elif ch == "]":
                self._esc = "osc"
                self._osc_prev = ""
            return
        if ch == "\x1b":
            self._esc = "esc"
        elif ch == "\r":
            self._line = []
        elif ch == "\n":
            self._lines.append("".join(self._line) + "\n")
            self._line = []
        else:
            self._line.append(ch)


_CAPTURE: _TerminalCleaner | None = None


class _TeeStream(io.TextIOBase):
    """Forward writes to the real stream while capturing a plain-text copy."""

    def __init__(self, target: io.TextIOBase) -> None:
        self._target = target

    def write(self, data: str) -> int:
        if _CAPTURE is not None:
            _CAPTURE.feed(data)
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
    """Tee stdout/stderr into a cleaner so the full run output can be logged."""
    global _CAPTURE
    _CAPTURE = _TerminalCleaner()
    sys.stdout = _TeeStream(sys.stdout)  # type: ignore[assignment]
    sys.stderr = _TeeStream(sys.stderr)  # type: ignore[assignment]


def captured_output() -> str:
    """Return the cleaned run output captured since start_output_capture()."""
    return _CAPTURE.text() if _CAPTURE is not None else ""


def write_run_logs(
    generated_paths: list[Path],
    output_dir: Path,
    run_info: dict[str, Any],
    payloads: dict[str, str],
    results: list[Any],
    md_files: list[MarkdownFile],
) -> list[Path]:
    """Write one self-contained run log per generated file, named after it.

    Each log holds, in order: the run header, the file's own payload JSON,
    the cleaned console capture, and the per-input summary. Falls back to a
    single timestamped log in output_dir when nothing was generated.
    """
    header = _build_header(run_info)
    capture = captured_output()
    summary = _build_summary(results, md_files)
    written: list[Path] = []
    for gen_path in generated_paths:
        log_path = gen_path.with_suffix(".log")
        log_path.write_text(_log_text(header, payloads.get(str(gen_path)), capture, summary))
        written.append(log_path)
    if not written:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = output_dir / f"frame_composer_{ts}.log"
        log_path.write_text(_log_text(header, None, capture, summary))
        written.append(log_path)
    return written


def _log_text(header: str, payload_text: str | None, capture: str, summary: str) -> str:
    """Assemble the four log sections in order."""
    parts = [header.rstrip("\n"), ""]
    if payload_text is not None:
        parts += ["=== Payload ===", payload_text.rstrip("\n"), ""]
    parts += [
        "=== Console output ===",
        capture.rstrip("\n"),
        "=== Run summary ===",
        summary.rstrip("\n"),
    ]
    return "\n".join(parts) + "\n"


def _build_header(run_info: dict[str, Any]) -> str:
    """Render the run-header section with verbose troubleshooting context."""
    profile = run_info["profile"]
    counts = run_info["counts"]
    lines = [
        "=== Frame Composer run log ===",
        f"vehicle: frame-composer v{__version__}",
        f"started_at: {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC",
        f"run_mode: {run_info['run_mode']}",
        f"platform: {run_info['platform']}",
        f"engine: {run_info['engine_name']}",
        f"profile: {run_info.get('profile_path') or 'unknown'}",
        f"endpoint: {profile.get('endpoint', '')}",
        f"media_type: {profile.get('media_type') or 'image'}",
        f"parameters: {json.dumps(profile.get('parameters', {}), ensure_ascii=False)}",
        f"pricing: {json.dumps(profile.get('pricing', {}), ensure_ascii=False)}",
        f"input_root: {run_info.get('input_root')}",
        f"output_dir: {run_info.get('output_dir')}",
        f"cli_args: {json.dumps(run_info.get('cli_args') or {}, ensure_ascii=False)}",
        f"counts: inputs={counts['inputs']} generated={counts['generated']} "
        f"failed={counts['failed']} placeholders={counts['placeholders']}",
    ]
    return "\n".join(lines)


def _build_summary(results: list[Any], md_files: list[MarkdownFile]) -> str:
    """Render the per-input outcome summary."""
    names = {str(b["path"]): b["path"].name for b in md_files}
    lines = []
    for r in results:
        name = names.get(str(r.source_path), str(r.source_path))
        parts = [f"{name}: {r.status}"]
        out = getattr(r, "path", None)
        if out:
            parts.append(f"output: {out.name}")
        if r.status == "error":
            err = error_info(getattr(r, "error_msg", "") or "")
            parts.append(f"error: {err.get('message', '')}")
            if err.get("code"):
                parts.append(f"code: {err['code']}")
            if err.get("id"):
                parts.append(f"id: {err['id']}")
        lines.append("  " + " | ".join(parts))
    return "\n".join(lines)
