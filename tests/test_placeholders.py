"""Tests for vehicle-side error placeholder images."""

from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from src.processing.context import PipelineContext
from src.processing.payload import error_info, read_payload
from src.processing.placeholders import (
    derive_size,
    render_placeholder,
    write_placeholders,
)


def _profile(**overrides: object) -> dict:
    profile = {
        "endpoint": "test/model",
        "parameters": {
            "aspect_ratio": "21:9",
            "resolution": "1K",
            "output_format": "png",
        },
        "media_type": "image",
        "prompt_prefix": "",
        "prompt_suffix": "",
    }
    profile.update(overrides)
    return profile


def _md(path: str = "in/b.md") -> dict:
    return {"path": Path(path), "prompt": "a castle", "reference_urls": []}


def _ok(path: Path) -> SimpleNamespace:
    return SimpleNamespace(status="ok", source_path=Path("in/a.md"), path=path, error_msg="")


def _error(
    expected: Path | None,
    msg: str = "API timeout",
    source_path: str = "in/b.md",
) -> SimpleNamespace:
    return SimpleNamespace(
        status="error",
        source_path=Path(source_path),
        path=None,
        error_msg=msg,
        expected_path=expected,
    )


ENGINE = SimpleNamespace(PROVIDER_NAME="Stub")


def _ctx(
    profile: dict,
    md_files: list,
    platform: str = "replicate",
    input_root: str | None = "in",
    save_payloads: bool = True,
) -> PipelineContext:
    return PipelineContext(
        md_files=md_files,
        engine=ENGINE,
        platform=platform,
        profile=profile,
        output_dir=Path("/tmp/out"),
        input_root=Path(input_root) if input_root else None,
        save_payloads=save_payloads,
    )


class TestWritePlaceholders:
    def test_mixed_run_writes_placeholder_with_payload(self, tmp_path):
        ok_path = tmp_path / "260831_110155-a-0.png"
        Image.new("RGB", (1584, 672), (10, 10, 10)).save(ok_path)
        expected = tmp_path / "260831_110155-b-1.png"
        results = [_ok(ok_path), _error(expected)]

        written = write_placeholders(_ctx(_profile(), [_md()]), results)

        assert written == [expected]
        assert expected.exists()
        with Image.open(expected) as img:
            assert img.size == (1584, 672)
            assert img.getpixel((5, 5)) == (200, 0, 0)
        payload = read_payload(expected)
        assert payload is not None
        assert payload["input_file"] == "b.md"

    def test_all_fail_writes_nothing(self, tmp_path):
        expected = tmp_path / "260831_110155-b-0.png"
        results = [_error(expected)]

        written = write_placeholders(_ctx(_profile(), [_md()]), results)

        assert written == []
        assert not expected.exists()

    def test_legacy_engine_missing_expected_path_is_skipped(self, tmp_path):
        ok_path = tmp_path / "260831_110155-a-0.png"
        Image.new("RGB", (10, 10), (10, 10, 10)).save(ok_path)
        legacy = SimpleNamespace(
            status="error",
            source_path=Path("in/b.md"),
            path=None,
            error_msg="boom",
        )
        results = [_ok(ok_path), legacy]

        written = write_placeholders(_ctx(_profile(), [_md()], platform="fal"), results)

        assert written == []

    def test_video_media_type_skips_placeholders(self, tmp_path):
        ok_path = tmp_path / "260831_110155-a-0.png"
        Image.new("RGB", (10, 10), (10, 10, 10)).save(ok_path)
        expected = tmp_path / "260831_110155-b-1.png"
        results = [_ok(ok_path), _error(expected)]

        written = write_placeholders(_ctx(_profile(media_type="video"), [_md()]), results)

        assert written == []
        assert not expected.exists()

    def test_mirrors_relative_dir_of_input(self, tmp_path):
        ok_path = tmp_path / "260831_110155-a-0.png"
        Image.new("RGB", (10, 10), (10, 10, 10)).save(ok_path)
        expected = tmp_path / "scene1" / "nested" / "260831_110155-b-1.png"
        results = [
            _ok(ok_path),
            _error(expected, source_path="in/scene1/nested/b.md"),
        ]

        written = write_placeholders(_ctx(_profile(), [_md("in/scene1/nested/b.md")]), results)

        assert written == [expected]
        assert expected.exists()

    def test_save_payloads_false_still_writes_image(self, tmp_path):
        ok_path = tmp_path / "260831_110155-a-0.png"
        Image.new("RGB", (10, 10), (10, 10, 10)).save(ok_path)
        expected = tmp_path / "260831_110155-b-1.png"
        results = [_ok(ok_path), _error(expected)]

        written = write_placeholders(_ctx(_profile(), [_md()], save_payloads=False), results)

        assert written == [expected]
        assert read_payload(expected) is None

    def test_jpeg_placeholder_truncates_huge_error_payload(self, tmp_path):
        ok_path = tmp_path / "260831_110155-a-0.png"
        Image.new("RGB", (10, 10), (10, 10, 10)).save(ok_path)
        expected = tmp_path / "260831_110155-b-1.jpg"
        huge = "E005 " + "sensitive " * 10_000
        results = [_ok(ok_path), _error(expected, msg=huge)]

        written = write_placeholders(_ctx(_profile(), [_md()]), results)

        assert written == [expected]
        payload = read_payload(expected)
        assert payload is not None
        assert len(payload["error"]["message"]) < len(huge)
        assert payload["error"]["code"] == "E005"


class TestDeriveSize:
    def test_profile_aspect_ratio_and_resolution(self):
        size = derive_size(_profile(), [])
        assert size == (1584, 672)

    def test_2k_doubles(self):
        profile = _profile(
            parameters={
                "aspect_ratio": "21:9",
                "resolution": "2K",
                "output_format": "png",
            }
        )
        assert derive_size(profile, []) == (3168, 1344)

    def test_falls_back_to_successful_image(self, tmp_path):
        ok_path = tmp_path / "a.png"
        Image.new("RGB", (333, 222), (0, 0, 0)).save(ok_path)
        profile = _profile(parameters={"aspect_ratio": "7:3"})
        assert derive_size(profile, [ok_path]) == (333, 222)

    def test_unknown_aspect_and_no_image_returns_none(self):
        profile = _profile(parameters={"aspect_ratio": "7:3"})
        assert derive_size(profile, []) is None


class TestRenderPlaceholder:
    def test_red_background_with_black_text(self, tmp_path):
        path = tmp_path / "card.png"
        render_placeholder(path, "Prediction failed (E005)", (400, 200))

        with Image.open(path) as img:
            assert img.size == (400, 200)
            assert img.getpixel((5, 5)) == (200, 0, 0)
        assert read_payload(path) is None

    def test_jpeg_suffix_produces_jpeg(self, tmp_path):
        path = tmp_path / "card.jpg"
        render_placeholder(path, "boom", (400, 200))
        assert path.read_bytes()[:2] == b"\xff\xd8"

    def test_long_message_crops_overflow_without_error(self, tmp_path):
        path = tmp_path / "card.png"
        render_placeholder(path, "word " * 500, (400, 200))
        assert path.exists()


class TestErrorInfo:
    def test_extracts_code_and_id(self):
        info = error_info(
            "Async prediction failed: ModelError: flagged (E005) "
            "https://replicate.com/p/abc12345xyz"
        )
        assert info["code"] == "E005"
        assert info["id"] == "abc12345xyz"
        assert "flagged" in info["message"]

    def test_plain_message_has_no_code_or_id(self):
        info = error_info("network timeout")
        assert "code" not in info
        assert "id" not in info
