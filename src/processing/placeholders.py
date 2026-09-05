"""Vehicle-side error placeholder images for failed generations.

Failed results get a red card with the error text written to the exact
path the engine reserved (expected_path), so the output serial stays
intact. Placeholders are only written when at least one generation
succeeded in the run.
"""

import textwrap
from pathlib import Path
from typing import Any

from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from ..datatypes import MarkdownFile
from .context import PipelineContext
from .markdown_parser import index_md_files
from .payload import compose_payload, error_info, fit_payload, inject_payload
from .results import success_paths

_ASPECT_1K = {
    "21:9": (1584, 672),
    "16:9": (1280, 720),
    "1:1": (1024, 1024),
    "9:16": (672, 1584),
}

BACKGROUND = (200, 0, 0)
FOREGROUND = (0, 0, 0)


def write_placeholders(
    ctx: PipelineContext,
    results: list[Any],
    payloads: dict[str, str] | None = None,
) -> list[Path]:
    """Write error placeholders for failed results; returns paths written."""
    successes = success_paths(results)
    errors = [r for r in results if r.status == "error"]
    if not _should_write_placeholders(errors, successes, ctx):
        return []
    size = derive_size(ctx.profile, successes)
    if size is None:
        logger.error("Cannot determine placeholder size - skipping placeholders")
        return []

    by_source = index_md_files(ctx.md_files)
    written: list[Path] = []
    for result in errors:
        path = _write_error_placeholder(ctx, result, by_source, payloads, size)
        if path is not None:
            written.append(path)
    return written


def _should_write_placeholders(
    errors: list[Any],
    successes: list[Path],
    ctx: PipelineContext,
) -> bool:
    """Guard placeholders: needs errors, >=1 success, and image media_type."""
    if not errors:
        return False
    if not successes:
        logger.error(
            f"All {len(errors)} generation(s) failed - no images produced; "
            "no placeholders written"
        )
        return False
    media_type = str(ctx.profile.get("media_type") or "image")
    if media_type != "image":
        logger.warning(
            f"Skipping {len(errors)} placeholder(s): media_type={media_type} "
            "is not supported (image-only)"
        )
        return False
    return True


def _write_error_placeholder(
    ctx: PipelineContext,
    result: Any,
    by_source: dict[str, MarkdownFile],
    payloads: dict[str, str] | None,
    size: tuple[int, int],
) -> Path | None:
    """Render one error card at its reserved path; None when skipped."""
    expected = getattr(result, "expected_path", None)
    if not expected:
        logger.error(
            f"{result.source_path.name}: engine '{ctx.platform}' does not "
            "support error placeholders - update the engine "
            "(missing expected_path)"
        )
        return None
    md_file = by_source.get(str(result.source_path))
    if md_file is None:
        logger.warning(f"{result.source_path.name}: no matching input - placeholder skipped")
        return None
    try:
        expected.parent.mkdir(parents=True, exist_ok=True)
        render_placeholder(expected, result.error_msg, size)
        if ctx.save_payloads:
            text = payloads.get(str(expected)) if payloads is not None else None
            if text is None:
                payload = compose_payload(
                    ctx,
                    md_file,
                    expected,
                    error=error_info(result.error_msg),
                )
                text = fit_payload(payload)
            inject_payload(expected, text=text)
        logger.info(f"Placeholder written: {expected}")
        return expected
    except Exception as exc:
        logger.error(f"Failed to write placeholder for {result.source_path.name}: {exc}")
        return None


def derive_size(profile: dict[str, Any], success_paths: list[Path]) -> tuple[int, int] | None:
    """Placeholder size: profile aspect/resolution, else first success image."""
    params = dict(profile.get("parameters", {}))
    aspect = str(params.get("aspect_ratio", "") or "").strip()
    resolution = str(params.get("resolution", "1K") or "").strip().upper()
    base = _ASPECT_1K.get(aspect)
    if base:
        factor = 2 if resolution == "2K" else 1
        return (base[0] * factor, base[1] * factor)
    for path in success_paths:
        try:
            with Image.open(path) as img:
                return (img.width, img.height)
        except Exception:
            continue
    return None


def render_placeholder(path: Path, error_msg: str, size: tuple[int, int]) -> None:
    """Draw red background with wrapped black error text; overflow crops."""
    width, height = size
    image = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    font_size = max(12, width // 60)
    font = ImageFont.load_default(size=font_size)
    margin = max(8, width // 100)
    chars = max(10, (width - 2 * margin) // (font_size // 2))
    lines = textwrap.wrap(error_msg or "Generation failed", chars)
    y = margin
    for line in lines:
        if y + font_size > height - margin:
            break
        draw.text((margin, y), line, fill=FOREGROUND, font=font)
        y += font_size + font_size // 3
    image.save(path)
