"""Pytest configuration — ensures `src` is importable regardless of working directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
