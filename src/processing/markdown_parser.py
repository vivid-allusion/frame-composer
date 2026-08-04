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


def extract_all_image_urls(markdown_content: str) -> list[str]:
    """
    Extract all image URLs from markdown content, preserving order.

    Supports both markdown syntax ![alt](URL) and raw URLs.
    Scans all lines and returns URLs in the order they appear.

    Args:
        markdown_content: Full markdown file content

    Returns:
        List of extracted image URLs in order of appearance

    Raises:
        ValueError: If no image URL found

    Example:
        >>> content = "Prompt here\\n![img1](https://example.com/1.jpg)\\n![img2](https://example.com/2.jpg)"
        >>> extract_all_image_urls(content)
        ['https://example.com/1.jpg', 'https://example.com/2.jpg']
    """
    urls: list[str] = []
    lines = markdown_content.split("\n")

    pattern = r"!\[.*?\]\((https?://[^\)]+)\)"

    for line in lines:
        match = re.search(pattern, line)
        if match:
            urls.append(match.group(1))
            continue

        stripped = line.strip()
        if stripped.startswith("http://") or stripped.startswith("https://"):
            urls.append(stripped)

    if not urls:
        raise ValueError("No image URLs found in markdown")

    return urls


def extract_prompt_text(markdown_content: str) -> str:
    """
    Extract text prompt from first line of markdown.

    Takes only the first non-empty line as the prompt text.
    Subsequent lines contain image URLs.

    Args:
        markdown_content: Full markdown file content

    Returns:
        Extracted prompt text (stripped of whitespace)

    Raises:
        ValueError: If no prompt found or content is empty

    Example:
        >>> content = "A man carries bags.\\n![image](https://example.com/img.jpg)"
        >>> extract_prompt_text(content)
        'A man carries bags.'
    """
    lines = markdown_content.split("\n")

    for line in lines:
        if line.strip():
            return line.strip()

    raise ValueError("No prompt text found in markdown")
