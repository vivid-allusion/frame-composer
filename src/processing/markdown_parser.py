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
from pathlib import Path

from loguru import logger

from ..types import MarkdownFile


def parse_markdown(markdown_content: str) -> tuple[str, list[str]]:
    """Parse a .md file, returning (prompt, image_urls) in one pass.

    Args:
        markdown_content: Full markdown file content

    Returns:
        Tuple of (prompt_text, list_of_image_urls)

    Raises:
        ValueError: If no prompt text found in markdown
    """
    lines = markdown_content.split("\n")
    prompt = ""
    urls: list[str] = []
    url_pattern = re.compile(r"!\[.*?\]\((https?://[^\)]+)\)")

    seen_prompt = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if not seen_prompt:
            prompt = stripped
            seen_prompt = True
            continue

        match = url_pattern.search(line)
        if match:
            urls.append(match.group(1))
        elif stripped.startswith("http://") or stripped.startswith("https://"):
            urls.append(stripped)

    if not prompt:
        raise ValueError("No prompt text found in markdown")

    return prompt, urls


def extract_prompt_text(markdown_content: str) -> str:
    """Extract text prompt from first line of markdown."""
    prompt, _ = parse_markdown(markdown_content)
    return prompt


def extract_all_image_urls(markdown_content: str) -> list[str]:
    """Extract all image URLs from markdown content, preserving order."""
    _, urls = parse_markdown(markdown_content)
    return urls


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
            urls = extract_all_image_urls(content)
        except ValueError as e:
            logger.warning(f"Failed to extract URLs from {md_path.name}: {e}")
        result.append({"path": md_path, "prompt": prompt, "reference_urls": urls})
    if not result:
        logger.warning(f"No .md files found in {input_dir}")
        return result
    logger.info(f"Discovered {len(result)} markdown file(s) in {input_dir}")
    return result
