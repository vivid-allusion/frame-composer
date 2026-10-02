"""W109 cross-repo: keep IDE cull marks on re-inject; skip the md footer.

The shared corpus in ``tests/fixtures/cull-marks/`` is copied verbatim from
``~/PLATFORM/theia-platform/test-fixtures/cull-marks/`` (see its README). These
tests are the generator half of the contract in
``docs/implementation/handoffs/W109-cross-repo-image-generator.md``.
"""

import json
import struct
from pathlib import Path

import pytest

from src.processing.markdown_parser import parse_markdown
from src.processing.payload import inject_payload, read_payload
from src.processing.payload_containers import (
    XMP_NAMESPACE,
    extract_description,
    inject_jpeg,
    inject_webp,
    read_jpeg,
    read_png,
    read_webp,
    xmp_packet,
)

FIXTURES = Path(__file__).parent / "fixtures" / "cull-marks"
UPSTREAM = Path.home() / "PLATFORM" / "theia-platform" / "test-fixtures" / "cull-marks"

RECIPE_TEXT = '{"prompt":"a detective in a dimly lit office","seed":42}'
CORPUS_FILES = [
    "unmarked.png",
    "recipe.png",
    "marked.png",
    "reinject.png",
    "recipe.expected.xmp",
    "marked.expected.xmp",
    "reinject.expected.xmp",
    "generate-fixtures.js",
]


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _copied(name: str, tmp_path: Path) -> Path:
    target = tmp_path / name
    target.write_bytes(_fixture(name))
    return target


class TestPacketMerge:
    def test_merge_keeps_siblings_and_replaces_description(self):
        merged = xmp_packet(RECIPE_TEXT, existing=_fixture("marked.expected.xmp"))

        assert merged == _fixture("marked.expected.xmp")
        assert b"<studio:marks>" in merged
        assert b"<xmp:Rating>3</xmp:Rating>" in merged
        assert extract_description(merged) == RECIPE_TEXT

    def test_merge_into_packet_without_description_inserts_one(self):
        marked = _fixture("marked.expected.xmp")
        # Rebuild the packet with the recipe removed from dc:description.
        opened = marked.find(b"<dc:description>")
        closed = marked.find(b"</dc:description>") + len(b"</dc:description>")
        without = marked[:opened] + b"<dc:description></dc:description>" + marked[closed:]

        merged = xmp_packet('{"prompt":"new"}', existing=without)

        assert extract_description(merged) == '{"prompt":"new"}'
        assert b"<studio:marks>" in merged


class TestReinjectPreservesMarks:
    def test_marked_fixture_keeps_marks_and_recipe(self, tmp_path):
        target = _copied("marked.png", tmp_path)

        inject_payload(target, text=RECIPE_TEXT)

        xml = read_png(target.read_bytes())
        assert xml == _fixture("marked.expected.xmp")
        assert b"<studio:marks>" in xml
        assert b"<xmp:Rating>3</xmp:Rating>" in xml
        assert extract_description(xml) == RECIPE_TEXT
        assert read_payload(target) == json.loads(RECIPE_TEXT)

    def test_reinject_fixture_is_byte_identical(self, tmp_path):
        target = _copied("reinject.png", tmp_path)

        inject_payload(target, text=RECIPE_TEXT)

        assert read_png(target.read_bytes()) == _fixture("reinject.expected.xmp")
        assert read_payload(target) == json.loads(RECIPE_TEXT)

    def test_recipe_fixture_reinject_is_byte_identical(self, tmp_path):
        target = _copied("recipe.png", tmp_path)

        inject_payload(target, text=RECIPE_TEXT)

        assert read_png(target.read_bytes()) == _fixture("recipe.expected.xmp")
        assert read_payload(target) == json.loads(RECIPE_TEXT)

    def test_unmarked_fixture_gets_a_fresh_packet(self, tmp_path):
        target = _copied("unmarked.png", tmp_path)

        inject_payload(target, text=RECIPE_TEXT)

        assert read_png(target.read_bytes()) == _fixture("recipe.expected.xmp")
        assert read_payload(target) == json.loads(RECIPE_TEXT)


class TestJpegAndWebpReinject:
    """The same merge, wired into the JPEG APP1 and WebP RIFF re-inject paths."""

    def test_jpeg_keeps_marks(self):
        marked = _fixture("marked.expected.xmp")
        app1 = (
            b"\xff\xe1"
            + struct.pack(">H", len(marked) + len(XMP_NAMESPACE) + 2)
            + XMP_NAMESPACE
            + marked
        )
        jpeg = b"\xff\xd8" + app1 + b"\xff\xd9"

        assert read_jpeg(jpeg) == marked

        reinjected = inject_jpeg(jpeg, RECIPE_TEXT)

        assert read_jpeg(reinjected) == marked
        assert extract_description(read_jpeg(reinjected)) == RECIPE_TEXT

    def test_webp_keeps_marks(self):
        marked = _fixture("marked.expected.xmp")
        pad = b"\x00" if len(marked) & 1 else b""
        chunk = b"XMP " + struct.pack("<I", len(marked)) + marked + pad
        webp = b"RIFF" + struct.pack("<I", len(chunk) + 4) + b"WEBP" + chunk

        assert read_webp(webp) == marked

        reinjected = inject_webp(webp, RECIPE_TEXT)

        assert read_webp(reinjected) == marked
        assert extract_description(read_webp(reinjected)) == RECIPE_TEXT


STUDIO_BLOCK = (
    "\n---\n"
    "studio:\n"
    "  marks:\n"
    "    rating: 3\n"
    "    colors: [green, red]\n"
    '    emoji: ["😀"]\n'
    "---\n"
)


class TestStudioMarkdownBlock:
    def test_block_is_skipped_with_no_warnings(self):
        base = "Portrait of a detective\n\n![x](https://b2.example/character.png)"
        warnings: list[str] = []

        with_block = parse_markdown(base + STUDIO_BLOCK, warn=warnings.append)
        without_block = parse_markdown(base, warn=warnings.append)

        assert with_block == without_block
        assert with_block == ("Portrait of a detective", ["https://b2.example/character.png"])
        assert warnings == []

    def test_malformed_trailing_block_is_skipped_without_crash(self):
        content = "Prompt\n![x](https://a.example/1.png)\n---\nstudio:\n  marks: [broken\n"

        assert parse_markdown(content) == ("Prompt", ["https://a.example/1.png"])

    def test_non_studio_fenced_block_is_not_swallowed(self):
        content = "Prompt\n---\nnote: value\n---\n"

        assert parse_markdown(content) == ("Prompt", [])

    def test_block_after_raw_url(self):
        content = "Prompt\nhttps://a.example/1.png" + STUDIO_BLOCK

        assert parse_markdown(content) == ("Prompt", ["https://a.example/1.png"])


def test_corpus_copies_are_byte_identical_to_origin():
    if not UPSTREAM.is_dir():
        pytest.skip("upstream cull-marks corpus is absent on this machine")
    for name in CORPUS_FILES:
        copy = FIXTURES / name
        origin = UPSTREAM / name
        assert copy.exists(), f"missing copied fixture {name}"
        assert copy.read_bytes() == origin.read_bytes(), f"{name} differs from origin"
