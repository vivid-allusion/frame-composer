"""Shared orchestration context passed through the generation pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..datatypes import MarkdownFile


@dataclass
class PipelineContext:
    """Bundled pipeline state shared by payload, placeholder, and log stages.

    Collapses the long parameter lists previously threaded through
    compose_payload(), write_placeholders(), and write_run_logs().
    """

    md_files: list[MarkdownFile]
    engine: Any
    platform: str
    profile: dict[str, Any]
    output_dir: Path
    input_root: Path | None = None
    save_payloads: bool = True
    run_mode: str = "standalone"
    cli_args: dict[str, Any] = field(default_factory=dict)
