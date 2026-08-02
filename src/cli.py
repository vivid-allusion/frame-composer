"""Command line interface argument parsing."""
import argparse


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Replicate Image Generation Wrapper"
    )

    parser.add_argument(
        "--input_dir",
        type=str,
        default=None,
        help="Source folder with bullet .md files (studiolot mode)",
    )

    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Target folder for generated output (studiolot mode)",
    )

    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Profile YAML path (studiolot mode)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test without making API calls",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output",
    )

    parser.add_argument(
        "--cost-estimation",
        action="store_true",
        help="Estimate costs without generating",
    )

    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar",
    )

    parser.add_argument(
        "--force-png",
        action="store_true",
        help="Convert all images to PNG format",
    )

    parser.add_argument(
        "--no-save-payloads",
        action="store_false",
        dest="save_payloads",
        help="Disable saving JSON payloads for each request",
    )

    parser.add_argument(
        "--install-default-engine",
        type=str,
        default=None,
        help="Auto-install default Engine (e.g. 'replicate') on first run",
    )

    parser.set_defaults(save_payloads=True)

    return parser.parse_args()
