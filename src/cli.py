"""Command line interface argument parsing."""

import argparse
from typing import Any, TypedDict


class _ArgumentSpec(TypedDict):
    """Declarative spec for one argparse argument."""

    flags: list[str]
    kwargs: dict[str, Any]


_ARGUMENTS: list[_ArgumentSpec] = [
    {
        "flags": ["--input_dir"],
        "kwargs": {"type": str, "default": None, "help": "Source folder with .md files"},
    },
    {
        "flags": ["--output_dir"],
        "kwargs": {"type": str, "default": None, "help": "Target folder for generated output"},
    },
    {
        "flags": ["--profile"],
        "kwargs": {"type": str, "default": None, "help": "Profile YAML path"},
    },
    {
        "flags": ["--platform"],
        "kwargs": {
            "type": str,
            "default": None,
            "help": "Engine platform (overrides profile YAML)",
        },
    },
    {
        "flags": ["--dry-run"],
        "kwargs": {"action": "store_true", "help": "Test without making API calls"},
    },
    {
        "flags": ["--debug"],
        "kwargs": {"action": "store_true", "help": "Enable debug output"},
    },
    {
        "flags": ["--verbose"],
        "kwargs": {"action": "store_true", "help": "Enable verbose (INFO level) output"},
    },
    {
        "flags": ["--cost-estimation"],
        "kwargs": {"action": "store_true", "help": "Estimate costs without generating"},
    },
    {
        "flags": ["--force-png"],
        "kwargs": {"action": "store_true", "help": "Convert all images to PNG format"},
    },
    {
        "flags": ["--no-save-payloads"],
        "kwargs": {
            "action": "store_false",
            "dest": "save_payloads",
            "help": "Disable saving JSON payloads for each request",
        },
    },
    {
        "flags": ["--install-default-engine"],
        "kwargs": {
            "type": str,
            "default": None,
            "help": "Auto-install default Engine on first run "
            "(supported: replicate, fal, openrouter, google)",
        },
    },
]


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Vivid Allusion Frame Composer")
    parser.set_defaults(save_payloads=True)

    for arg in _ARGUMENTS:
        parser.add_argument(*arg["flags"], **arg["kwargs"])

    return parser.parse_args()
