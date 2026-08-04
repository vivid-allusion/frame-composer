"""Command line interface argument parsing."""

import argparse

_ARGUMENTS: list[dict] = [
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
        "flags": ["--dry-run"],
        "kwargs": {"action": "store_true", "help": "Test without making API calls"},
    },
    {
        "flags": ["--debug"],
        "kwargs": {"action": "store_true", "help": "Enable debug output"},
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
    parser = argparse.ArgumentParser(
        description="Vivid Allusion Frame Composer"
    )
    parser.set_defaults(save_payloads=True)

    for arg in _ARGUMENTS:
        parser.add_argument(*arg["flags"], **arg["kwargs"])

    return parser.parse_args()
