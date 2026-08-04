"""Tests for engine_loader module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.engine_loader import EngineLoadContext, load_engine


class TestLoadEngine:
    def test_platform_none_defaults_to_replicate(self):
        with (
            patch("src.engine_loader.importlib.util.spec_from_file_location") as mock_spec,
            patch("src.engine_loader.importlib.util.module_from_spec") as mock_module,
        ):
            mock_engine_class = MagicMock()
            mock_module.return_value.Engine = mock_engine_class
            mock_spec.return_value = MagicMock()

            search_paths = [Path("/fake/ENGINES")]
            ctx = EngineLoadContext(
                platform=None,
                search_paths=search_paths,
                profile={},
                output_dir="/tmp/out",
            )
            with patch.object(Path, "is_dir", return_value=True):
                load_engine(ctx)

            mock_engine_class.assert_called_once()

    def test_raises_file_not_found_when_no_engine_dir(self):
        search_paths = [Path("/nonexistent")]
        ctx = EngineLoadContext(
            platform="replicate",
            search_paths=search_paths,
            profile={},
            output_dir="/tmp/out",
        )
        with pytest.raises(FileNotFoundError, match="Engine 'replicate' not found"):
            load_engine(ctx)
