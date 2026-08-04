"""Shared contract between Vehicle and Engine plugins.

Defines the expected interface for Engine.InputFile so that _build_inputs()
can validate compatibility at import time rather than crashing at runtime.
"""

from pathlib import Path
from typing import Protocol


class EngineInputFile(Protocol):
    """Expected constructor signature for an Engine's InputFile."""

    def __init__(self, *, path: Path, prompt: str, reference_urls: list[str]) -> None:
        ...


def validate_input_file(input_file_cls: type, platform: str) -> None:
    """Raise a descriptive error if the class doesn't match the contract."""
    if not hasattr(input_file_cls, "__init__"):
        raise ImportError(
            f"Engine '{platform}' InputFile has no __init__ method"
        )

    import inspect

    sig = inspect.signature(input_file_cls.__init__)
    required = {"path", "prompt", "reference_urls"}
    params = set(sig.parameters.keys()) - {"self"}
    if not required.issubset(params):
        missing = required - params
        raise ImportError(
            f"Engine '{platform}' InputFile is missing required parameters: {missing}"
        )
