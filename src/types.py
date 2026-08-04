"""Shared type definitions for the application."""

from pathlib import Path
from typing import TypedDict


class MarkdownFile(TypedDict):
    """A parsed .md file with its extracted data."""

    path: Path
    prompt: str
    reference_urls: list[str]
