"""Tests for terminal-faithful capture and LLM-friendly run logs."""

import io
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image

from src.main_simple import _execute_pipeline
from src.processing.context import PipelineContext
from src.processing.payload import read_payload
from src.utils import logging as capture_mod
from src.utils.logging import (
    _TeeStream,
    _TerminalCleaner,
    start_output_capture,
    write_run_logs,
)

REAL_LOG = Path(
    "/home/admin/Nextcloud-QO1/260407_WALLENBERG/02_RW_GEN_IMG/"
    "260831_110155_IMG/260831_110206-1_rw-0.log"
)


@pytest.fixture(autouse=True)
def _restore_streams():
    stdout, stderr = sys.stdout, sys.stderr
    yield
    sys.stdout, sys.stderr = stdout, stderr


def _clean(text: str) -> str:
    cleaner = _TerminalCleaner()
    cleaner.feed(text)
    return cleaner.text()


class TestTerminalCleaner:
    def test_strips_sgr_colours(self):
        assert _clean("a\x1b[31mred\x1b[0m b") == "ared b"

    def test_strips_cursor_and_erase_sequences(self):
        assert _clean("\x1b[?25l\x1b[2Khi\x1b[?25h") == "hi"

    def test_csi_split_across_feeds(self):
        cleaner = _TerminalCleaner()
        cleaner.feed("abc\x1b[")
        cleaner.feed("31mdef")
        assert cleaner.text() == "abcdef"

    def test_strips_osc_bel_and_st(self):
        assert _clean("\x1b]0;title\x07text") == "text"
        assert _clean("\x1b]0;title\x1b\\text") == "text"

    def test_collapses_cr_redraws(self):
        assert _clean("one\r\x1b[2Ktwo\n") == "two\n"

    def test_cr_collapse_across_feeds(self):
        cleaner = _TerminalCleaner()
        cleaner.feed("part1\r")
        cleaner.feed("part2\n")
        assert cleaner.text() == "part2\n"

    def test_flushes_partial_trailing_line(self):
        assert _clean("unfinished") == "unfinished"

    def test_preserves_plain_lines(self):
        assert _clean("a\nb\nc") == "a\nb\nc"

    def test_rich_live_session_reduces_to_final_state(self):
        raw = (
            "start\n\x1b[?25l\r\x1b[2Kframe one\r\x1b[2Kframe two\r" "\x1b[2K\x1b[?25h\nComplete\n"
        )
        assert _clean(raw) == "start\n\nComplete\n"

    def test_no_stray_fragments_from_unknown_escape(self):
        assert _clean("a\x1bZb") == "ab"


class TestTeeStream:
    def test_target_receives_raw_bytes_unchanged(self):
        target = io.StringIO()
        tee = _TeeStream(target)
        start_output_capture()
        raw = "x\x1b[2K\r\x1b]0;t\x07y\n"
        assert tee.write(raw) == len(raw)
        assert target.getvalue() == raw

    def test_capture_gets_cleaned_text(self):
        start_output_capture()
        sys.stdout.write("one\r\x1b[2Ktwo\n")
        assert capture_mod.captured_output() == "two\n"


def _md(path: str, prompt: str) -> dict:
    return {"path": Path(path), "prompt": prompt, "reference_urls": []}


def _install_stub_engine_module(monkeypatch: pytest.MonkeyPatch) -> None:
    class InputFile:
        def __init__(
            self, *, path: Path, prompt: str, reference_urls: list, metadata: dict
        ) -> None:
            self.path = path
            self.prompt = prompt
            self.reference_urls = reference_urls
            self.metadata = metadata

    module = ModuleType("engine_replicate")
    module.InputFile = InputFile
    monkeypatch.setitem(sys.modules, "engine_replicate", module)


class StubEngine:
    PROVIDER_NAME = "Stub"
    _on_progress = None

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def run(self, inputs: list) -> list[SimpleNamespace]:
        results = []
        for index, item in enumerate(inputs):
            stem = item.path.stem
            out = self.output_dir / f"{index}-{stem}.png"
            if "fail" in item.prompt:
                results.append(
                    SimpleNamespace(
                        status="error",
                        source_path=item.path,
                        path=None,
                        error_msg=(
                            "Prediction failed (E005) " "https://replicate.com/p/abc12345xyz"
                        ),
                        expected_path=out,
                    )
                )
            else:
                Image.new("RGB", (32, 32), (0, 0, 255)).save(out)
                results.append(
                    SimpleNamespace(
                        status="ok",
                        source_path=item.path,
                        path=out,
                        error_msg="",
                        expected_path=None,
                    )
                )
        return results


def _profile() -> dict:
    return {
        "profile_name": "test",
        "profile_path": "/profiles/test.yaml",
        "endpoint": "test/model",
        "parameters": {"aspect_ratio": "16:9"},
        "media_type": "image",
        "pricing": {"base_cost": 0.05},
        "prompt_prefix": "",
        "prompt_suffix": "",
    }


def _run_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    save_payloads: bool = True,
    fail_all: bool = False,
) -> dict[str, str]:
    _install_stub_engine_module(monkeypatch)
    md_files = [_md("in/a.md", "a castle"), _md("in/b.md", "fail request")]
    if fail_all:
        md_files = [_md("in/a.md", "fail request")]
    engine = StubEngine(tmp_path)
    start_output_capture()
    ctx = PipelineContext(
        md_files=md_files,
        engine=engine,
        platform="replicate",
        profile=_profile(),
        output_dir=tmp_path,
        input_root=Path("in"),
        save_payloads=save_payloads,
        run_mode="studiolot",
        cli_args={"dry_run": False},
    )
    exit_code = _execute_pipeline(ctx)
    assert exit_code == 1
    return {p.name: p.read_text() for p in tmp_path.glob("*.log")}


def _payload_section(text: str) -> str:
    return text.split("=== Payload ===\n")[1].split("\n=== Console output ===")[0].rstrip("\n")


class TestPerFileLogs:
    def test_mixed_run_writes_per_file_logs_in_order(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        logs = _run_pipeline(monkeypatch, tmp_path)

        assert set(logs) == {"0-a.log", "1-b.log"}
        text = logs["0-a.log"]
        order = [
            text.index("=== Frame Composer run log ==="),
            text.index("=== Payload ==="),
            text.index("=== Console output ==="),
            text.index("=== Run summary ==="),
        ]
        assert order == sorted(order)
        assert "vehicle: frame-composer v" in text
        assert "run_mode: studiolot" in text
        assert "platform: replicate" in text
        assert "engine: Stub" in text
        assert "profile: /profiles/test.yaml" in text
        assert "counts: inputs=2 generated=1 failed=1 placeholders=1" in text

    def test_payload_section_byte_identical_to_embedded_payload(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        logs = _run_pipeline(monkeypatch, tmp_path)

        payload = read_payload(tmp_path / "0-a.png")
        assert payload is not None
        expected = json.dumps(payload, indent=2, ensure_ascii=False)
        assert _payload_section(logs["0-a.log"]) == expected

    def test_error_payload_in_placeholder_log(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        logs = _run_pipeline(monkeypatch, tmp_path)

        payload = json.loads(_payload_section(logs["1-b.log"]))
        assert payload["input_file"] == "b.md"
        assert payload["error"]["code"] == "E005"
        assert payload["error"]["id"] == "abc12345xyz"
        assert "E005" in logs["1-b.log"].split("=== Run summary ===")[1]

    def test_summary_lists_every_input(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        logs = _run_pipeline(monkeypatch, tmp_path)

        summary = logs["0-a.log"].split("=== Run summary ===\n")[1]
        assert "a.md: ok" in summary and "output: 0-a.png" in summary
        assert "b.md: error" in summary and "code: E005" in summary

    def test_fallback_log_when_nothing_generated(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        logs = _run_pipeline(monkeypatch, tmp_path, fail_all=True)

        assert len(logs) == 1
        name = next(iter(logs))
        assert name.startswith("frame_composer_")
        text = logs[name]
        assert "=== Payload ===" not in text
        assert "=== Frame Composer run log ===" in text
        assert "=== Console output ===" in text
        assert "=== Run summary ===" in text
        assert "a.md: error" in text

    def test_logs_contain_no_api_keys(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setenv("REPLICATE_API_TOKEN", "super-secret-token")
        logs = _run_pipeline(monkeypatch, tmp_path)

        for text in logs.values():
            assert "super-secret-token" not in text

    def test_logs_written_even_when_payloads_not_saved(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        logs = _run_pipeline(monkeypatch, tmp_path, save_payloads=False)

        assert read_payload(tmp_path / "0-a.png") is None
        assert "=== Payload ===" in logs["0-a.log"]


class TestFallbackWriter:
    def test_write_run_logs_with_empty_paths(self, tmp_path: Path):
        start_output_capture()
        sys.stderr.write("nothing to do\n")
        results = [
            SimpleNamespace(
                status="error",
                source_path=Path("in/a.md"),
                path=None,
                error_msg="Prediction failed (E006)",
                expected_path=None,
            )
        ]
        ctx = PipelineContext(
            md_files=[_md("in/a.md", "x")],
            engine=StubEngine(tmp_path),
            platform="replicate",
            profile=_profile(),
            output_dir=tmp_path,
            input_root=Path("in"),
            run_mode="standalone",
            cli_args={},
        )
        written = write_run_logs([], tmp_path, ctx, {}, results)
        assert len(written) == 1
        text = written[0].read_text()
        assert "=== Payload ===" not in text
        assert "=== Run summary ===" in text
        assert "code: E006" in text


@pytest.mark.skipif(not REAL_LOG.exists(), reason="reference log not available")
class TestRealLogReplay:
    def test_reference_log_cleans_to_plain_text(self):
        raw = REAL_LOG.read_bytes().decode("utf-8", errors="replace")
        out = _clean(raw)

        assert "\x1b" not in out
        assert len(out) < 100_000
        assert "Complete: " in out
        assert len(out.splitlines()) > 5
