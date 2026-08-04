"""Tests for path_resolver module."""

import tempfile
from pathlib import Path

import pytest
from src.utils.path_resolver import (
    create_timestamped_output_path,
    resolve_input_path,
    resolve_output_base_path,
)


class TestResolveInputPath:
    def test_default_fallback_to_user_files(self):
        input_path, project = resolve_input_path({})
        assert input_path == Path("USER-FILES/04.INPUT")
        assert project is None

    def test_custom_path_from_profile(self):
        profile = {"paths": {"input": "/tmp/test_input"}, "project": "myproj"}
        input_path, project = resolve_input_path(profile)
        assert input_path == Path("/tmp/test_input")
        assert project == "myproj"

    def test_raises_if_path_missing(self):
        with pytest.raises(FileNotFoundError, match="Input directory not found"):
            resolve_input_path({"paths": {"input": "/nonexistent/path"}})


class TestResolveOutputBasePath:
    def test_default_fallback_to_user_files(self):
        output_base = resolve_output_base_path({})
        assert output_base == Path("USER-FILES/05.OUTPUT")

    def test_custom_path_from_profile(self):
        profile = {"paths": {"output": "/tmp/test_output"}}
        output_base = resolve_output_base_path(profile)
        assert output_base == Path("/tmp/test_output")


class TestCreateTimestampedOutputPath:
    def test_creates_timestamped_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            output = create_timestamped_output_path(base)
            assert output.parent == base
            assert output.exists()
            assert output.is_dir()
            assert "_GENAI" in output.name
