"""Generation payload embedding — marry each generated image to its recipe.

compose_payload() builds the recipe JSON (schema v1); inject_payload()
embeds it as an XMP packet in PNG/JPEG/WebP; read_payload() reverses it.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from ..constants import __version__
from ..datatypes import MarkdownFile
from ..utils.path_resolver import relative_posix
from .context import PipelineContext
from .markdown_parser import index_md_files
from .payload_containers import (
    detect_format,
    extract_description,
    inject_jpeg,
    inject_png,
    inject_webp,
    read_jpeg,
    read_png,
    read_webp,
)

MAX_JPEG_PAYLOAD = 60_000

_ERROR_CODE = re.compile(r"\bE\d{3}\b")
_ERROR_ID = re.compile(r"(?:p/|prediction[_ -]?id[:\s=]+)([A-Za-z0-9]{8,})", re.I)


def error_info(error_msg: str) -> dict[str, Any]:
    """Extract structured error details (code + provider id) from a message."""
    info: dict[str, Any] = {"message": error_msg}
    match = _ERROR_CODE.search(error_msg)
    if match:
        info["code"] = match.group(0)
    match = _ERROR_ID.search(error_msg)
    if match:
        info["id"] = match.group(1)
    return info


def compose_payload(
    ctx: PipelineContext,
    md_file: MarkdownFile,
    out_path: Path,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prefix = str(ctx.profile.get("prompt_prefix", "") or "")
    suffix = str(ctx.profile.get("prompt_suffix", "") or "")
    raw = md_file["prompt"]
    payload: dict[str, Any] = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vehicle": {"name": "frame-composer", "version": __version__},
        "engine": {
            "platform": ctx.platform,
            "provider": getattr(ctx.engine, "PROVIDER_NAME", ctx.platform),
        },
        "endpoint": ctx.profile.get("endpoint", ""),
        "parameters": dict(ctx.profile.get("parameters", {})),
        "prompt": {"raw": raw, "wrapped": f"{prefix}{raw}{suffix}".strip()},
        "prefix": prefix,
        "suffix": suffix,
        "reference_urls": list(md_file["reference_urls"]),
        "input_file": relative_posix(md_file["path"], ctx.input_root) or md_file["path"].name,
        "media_type": str(ctx.profile.get("media_type") or "image"),
        "output_file": out_path.name,
    }
    if error is not None:
        payload["error"] = error
    return payload


def fit_payload(payload: dict[str, Any], limit: int = MAX_JPEG_PAYLOAD) -> str:
    """Serialize payload, truncating error.message until it fits the limit."""
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    error = payload.get("error")
    while len(text) > limit and error and error.get("message"):
        error["message"] = error["message"][: max(1, len(error["message"]) // 2)]
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    return text


def compose_run_payloads(ctx: PipelineContext, results: list[Any]) -> dict[str, str]:
    """Compose each payload once per run; keys are str(output path).

    Error results use their reserved destination (expected_path) and carry
    the structured error, so placeholder and log stay in sync.
    """
    by_source = index_md_files(ctx.md_files)
    payloads: dict[str, str] = {}
    for result in results:
        out = result.path if result.status == "ok" else getattr(result, "expected_path", None)
        md_file = by_source.get(str(result.source_path))
        if not out or md_file is None:
            continue
        error = (
            error_info(getattr(result, "error_msg", "") or "") if result.status == "error" else None
        )
        payload = compose_payload(ctx, md_file, out, error=error)
        text = (
            fit_payload(payload)
            if result.status == "error"
            else json.dumps(payload, indent=2, ensure_ascii=False)
        )
        payloads[str(out)] = text
    return payloads


def embed_payloads(results: list[Any], payloads: dict[str, str]) -> None:
    """Embed each generated file's precomposed payload. Failures log and continue."""
    for result in results:
        if getattr(result, "status", "") != "ok" or not getattr(result, "path", None):
            continue
        text = payloads.get(str(result.path))
        if text is None:
            continue
        try:
            inject_payload(result.path, text=text)
            logger.debug(f"Payload embedded: {result.path.name}")
        except Exception as exc:
            logger.error(f"Failed to embed payload in {result.path.name}: {exc}")


def inject_payload(
    path: Path, payload: dict[str, Any] | None = None, text: str | None = None
) -> None:
    """Embed payload in the file at path, replacing any previous payload."""
    data = path.read_bytes()
    if text is None:
        if payload is None:
            raise ValueError("payload or text required")
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    fmt = detect_format(data)
    if fmt == "png":
        new_data = inject_png(data, text)
    elif fmt == "jpeg":
        if len(text) > MAX_JPEG_PAYLOAD:
            raise ValueError(f"payload too large for JPEG: {len(text)} bytes")
        new_data = inject_jpeg(data, text)
    elif fmt == "webp":
        new_data = inject_webp(data, text)
    else:
        raise ValueError(f"unsupported image format: {path.suffix or path.name}")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(new_data)
    os.replace(tmp, path)


def read_payload(path: Path) -> dict[str, Any] | None:
    """Return the embedded payload, or None if the file carries none."""
    data = path.read_bytes()
    fmt = detect_format(data)
    if fmt == "png":
        xml = read_png(data)
    elif fmt == "jpeg":
        xml = read_jpeg(data)
    elif fmt == "webp":
        xml = read_webp(data)
    else:
        return None
    if xml is None:
        return None
    text = extract_description(xml)
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None
