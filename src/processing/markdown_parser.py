"""
Markdown parsing utilities for extracting image URLs and prompts.

This module provides functions to parse markdown files and extract:
- Image URLs from any line (markdown ![alt](URL) or raw https:// URL)
- Text prompt from line 1

Format:
    Line 1: Text prompt
    Lines 2+: ![image](URL) or https://...  (multiple images supported)

PRD Reference: Section 05.1, 06.2
"""

import re
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from ..types import MarkdownFile

if TYPE_CHECKING:
    from collections.abc import Callable


_IMG_URL_PATTERN = re.compile(r"!\[.*?\]\((https?://[^\)]+)\)")
_LINK_WITHOUT_BANG = re.compile(r"(?<!!)\[.*?\]\((https?://[^\)]+)\)")
_BANG_SPACE_PATTERN = re.compile(r"! +\[.*?\]\(.*?\)")
_PAREN_SPACE_PATTERN = re.compile(r"!\[.*?\] +\(.*?\)")
_SWAPPED_PATTERN = re.compile(r"!\[(https?://[^\]]+)\]\([^\)]+\)")
_UNCLOSED_PATTERN = re.compile(r"!\[.*?\]\([^\)]*$")
_HTML_IMG_PATTERN = re.compile(r"<img[^>]*src\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
_NON_HTTP_URL = re.compile(
    r"!\[.*?\]\((?!https?://)(\.\.?/|\.\.?\\|//|/|data:|file:|ftp:|[A-Za-z]:\\|\w+://)[^\)]+\)"
)


def _check_line(line: str, lineno: int, warn: "Callable[[str], None] | None") -> None:
    """Inspect a line for common image-embed formatting mistakes."""
    if warn is None:
        return

    if _BANG_SPACE_PATTERN.search(line):
        warn(f"Line {lineno}: space between '!' and '[' — use ![alt](URL) not ! [alt](URL)")

    if _PAREN_SPACE_PATTERN.search(line):
        warn(f"Line {lineno}: space before '(' — use ![alt](URL) not ![alt] (URL)")

    if _SWAPPED_PATTERN.search(line):
        warn(f"Line {lineno}: URL and alt text appear swapped. Use ![alt](URL), not ![URL](alt)")

    if _UNCLOSED_PATTERN.search(line):
        warn(f"Line {lineno}: unclosed parenthesis — missing ')' after URL")

    if _LINK_WITHOUT_BANG.search(line):
        warn(f"Line {lineno}: missing '!' prefix — use ![alt](URL) not [alt](URL)")

    if _HTML_IMG_PATTERN.search(line):
        warn(f"Line {lineno}: HTML <img> tag found. Use markdown ![alt](URL) instead")

    if _NON_HTTP_URL.search(line):
        warn(f"Line {lineno}: image URL does not start with https:// — only remote URLs are supported")


def parse_markdown(markdown_content: str, warn: "Callable[[str], None] | None" = None) -> tuple[str, list[str]]:
    """Parse a .md file, returning (prompt, image_urls) in one pass.

    Args:
        markdown_content: Full markdown file content
        warn: Optional callback for format warnings (e.g. logger.warning)

    Returns:
        Tuple of (prompt_text, list_of_image_urls)

    Raises:
        ValueError: If no prompt found
    """
    lines = markdown_content.split("\n")
    prompt = ""
    urls: list[str] = []

    seen_prompt = False
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue

        if not seen_prompt:
            prompt = stripped
            seen_prompt = True
            continue

        match = _IMG_URL_PATTERN.search(line)
        if match:
            urls.append(match.group(1))
        elif stripped.startswith("http://") or stripped.startswith("https://"):
            urls.append(stripped)
        else:
            _check_line(line, lineno, warn)

    if not prompt:
        raise ValueError("No prompt text found in markdown")

    return prompt, urls


def extract_prompt_text(markdown_content: str) -> str:
    """Extract text prompt from first line of markdown."""
    prompt, _ = parse_markdown(markdown_content)
    return prompt


def extract_all_image_urls(
    markdown_content: str, warn: "Callable[[str], None] | None" = None
) -> list[str]:
    """Extract all image URLs from markdown content, preserving order."""
    _, urls = parse_markdown(markdown_content, warn=warn)
    return urls


def validate_image_urls(urls: list[str], timeout: float = 5.0) -> tuple[list[str], list[str]]:
    """Validate image URLs are reachable via HEAD request.

    Args:
        urls: List of image URLs to check.
        timeout: Seconds per request.

    Returns:
        Tuple of (valid_urls, invalid_urls). Invalid URLs are stripped.
    """
    valid: list[str] = []
    invalid: list[str] = []
    headers = {"User-Agent": "FrameComposer/1.0"}
    for url in urls:
        try:
            req = urllib.request.Request(url, method="HEAD", headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status >= 400:
                    invalid.append(url)
                else:
                    valid.append(url)
        except Exception:
            invalid.append(url)
    return valid, invalid


def read_markdown_files(input_dir: Path) -> list[MarkdownFile]:
    """Read .md files from input_dir, extract prompt + reference URLs."""
    md_files = sorted(input_dir.rglob("*.md"))
    result: list[MarkdownFile] = []
    for md_path in md_files:
        content = md_path.read_text(encoding="utf-8")
        prompt = ""
        try:
            prompt = extract_prompt_text(content)
        except ValueError as e:
            logger.warning(f"Failed to extract prompt from {md_path.name}: {e}")
        urls: list[str] = []
        try:
            urls = extract_all_image_urls(content, warn=logger.warning)
        except ValueError as e:
            logger.warning(f"Failed to extract URLs from {md_path.name}: {e}")
        if urls:
            valid, invalid = validate_image_urls(urls)
            if invalid:
                for url in invalid:
                    logger.warning(f"Unreachable image URL in {md_path.name}: {url}")
            urls = valid
            if not urls and (valid or invalid):
                logger.warning(
                    f"No reachable image URLs in {md_path.name} "
                    f"— treating as text-to-image"
                )
        result.append({"path": md_path, "prompt": prompt, "reference_urls": urls})
    if not result:
        logger.warning(f"No .md files found in {input_dir}")
        return result
    logger.info(f"Discovered {len(result)} markdown file(s) in {input_dir}")
    return result
