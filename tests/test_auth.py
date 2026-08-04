"""Tests for auth module."""

import os
from unittest.mock import patch

import pytest
from src.auth import get_api_key
from src.exceptions import AuthenticationError


class TestGetApiKey:
    def test_from_environment(self):
        with patch.dict(os.environ, {"REPLICATE_API_TOKEN": "r8_test123"}):
            key = get_api_key("replicate")
            assert key == "r8_test123"

    def test_from_environment_fal(self):
        with patch.dict(os.environ, {"FAL_KEY": "fal_test456"}):
            key = get_api_key("fal")
            assert key == "fal_test456"

    def test_missing_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AuthenticationError, match="REPLICATE_API_TOKEN not set"):
                get_api_key("replicate")

    def test_unknown_platform_uses_convention(self):
        key_name = "CUSTOM_API_KEY"
        with patch.dict(os.environ, {key_name: "val"}):
            key = get_api_key("custom")
            assert key == "val"
