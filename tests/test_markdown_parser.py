"""Tests for markdown_parser module."""

import pytest
from src.processing.markdown_parser import extract_all_image_urls, extract_prompt_text


class TestExtractPromptText:
    def test_single_line_prompt(self):
        content = "A man carries bags.\n![image](https://example.com/img.jpg)"
        assert extract_prompt_text(content) == "A man carries bags."

    def test_first_non_empty_line(self):
        content = "\n\nHello world\n![img](https://x.com/a.jpg)"
        assert extract_prompt_text(content) == "Hello world"

    def test_empty_content_raises(self):
        with pytest.raises(ValueError, match="No prompt"):
            extract_prompt_text("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            extract_prompt_text("   \n   \n")


class TestExtractAllImageUrls:
    def test_markdown_image_syntax(self):
        content = "Prompt\n![a](https://example.com/1.jpg)\n![b](https://example.com/2.jpg)"
        urls = extract_all_image_urls(content)
        assert urls == ["https://example.com/1.jpg", "https://example.com/2.jpg"]

    def test_raw_urls(self):
        content = "Prompt\nhttps://example.com/img.png\nhttps://other.com/photo.jpg"
        urls = extract_all_image_urls(content)
        assert urls == ["https://example.com/img.png", "https://other.com/photo.jpg"]

    def test_mixed_markdown_and_raw(self):
        content = "P\n![x](https://a.com/1.jpg)\nhttps://b.com/2.png"
        urls = extract_all_image_urls(content)
        assert urls == ["https://a.com/1.jpg", "https://b.com/2.png"]

    def test_no_urls_raises(self):
        with pytest.raises(ValueError, match="No image URLs"):
            extract_all_image_urls("Just a prompt\nNothing else")
