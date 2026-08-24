"""Generation payload embedding — marry each generated image to its recipe.

compose_payload() builds the recipe JSON (schema v1); inject_payload()
embeds it as an XMP packet in PNG/JPEG/WebP; read_payload() reverses it.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from ..constants import __version__
from ..datatypes import MarkdownFile
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


def compose_payload(
    md_file: MarkdownFile,
    profile: dict[str, Any],
    platform: str,
    engine: Any,
    input_root: Path | None,
    out_path: Path,
) -> dict[str, Any]:
    prefix = str(profile.get("prompt_prefix", "") or "")
    suffix = str(profile.get("prompt_suffix", "") or "")
    raw = md_file["prompt"]
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vehicle": {"name": "frame-composer", "version": __version__},
        "engine": {
            "platform": platform,
            "provider": getattr(engine, "PROVIDER_NAME", platform),
        },
        "endpoint": profile.get("endpoint", ""),
        "parameters": dict(profile.get("parameters", {})),
        "prompt": {"raw": raw, "wrapped": f"{prefix}{raw}{suffix}".strip()},
        "prefix": prefix,
        "suffix": suffix,
        "reference_urls": list(md_file["reference_urls"]),
        "input_file": _relative_input_file(md_file["path"], input_root),
        "media_type": str(profile.get("media_type") or "image"),
        "output_file": out_path.name,
    }


def embed_payloads(
    results: list[Any],
    md_files: list[MarkdownFile],
    profile: dict[str, Any],
    platform: str,
    engine: Any,
    input_root: Path | None,
) -> None:
    """Embed every generated file's payload. Failures log and continue."""
    by_source = {str(b["path"]): b for b in md_files}
    for result in results:
        if getattr(result, "status", "") != "ok" or not getattr(result, "path", None):
            continue
        md_file = by_source.get(str(result.source_path))
        if md_file is None:
            continue
        payload = compose_payload(
            md_file, profile, platform, engine, input_root, result.path
        )
        try:
            inject_payload(result.path, payload)
            logger.debug(f"Payload embedded: {result.path.name}")
        except Exception as exc:
            logger.error(f"Failed to embed payload in {result.path.name}: {exc}")


def inject_payload(path: Path, payload: dict[str, Any]) -> None:
    """Embed payload in the file at path, replacing any previous payload."""
    data = path.read_bytes()
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


def _relative_input_file(path: Path, input_root: Path | None) -> str:
    if input_root is not None:
        try:
            return path.relative_to(input_root).as_posix()
        except ValueError:
            pass
    return path.name
