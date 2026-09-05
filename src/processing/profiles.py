"""Profile loading — standalone and studiolot modes."""

from pathlib import Path
from typing import Any

import yaml

from ..exceptions import ConfigurationError

_ACTIVE = Path("USER-FILES/03.PROFILES")


def _parse_profile_yaml(yaml_path: Path) -> dict[str, Any]:
    """Load and annotate a profile YAML file."""
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    data["profile_name"] = yaml_path.stem
    data["profile_path"] = str(yaml_path)
    return data


def load_profile_standalone() -> dict[str, Any]:
    """Load the active profile from 03.PROFILES/ — never falls back to STANDBY."""
    yamls = sorted(_ACTIVE.glob("*.yaml")) + sorted(_ACTIVE.glob("*.yml"))
    if not yamls:
        raise ConfigurationError(
            "No active profile in USER-FILES/03.PROFILES/.\n"
            "Copy a YAML from USER-FILES/02.STANDBY/ into USER-FILES/03.PROFILES/"
        )
    return _parse_profile_yaml(yamls[0])


def load_profile_studiolot(profile_path: Path) -> dict[str, Any]:
    """Load profile YAML from --profile flag."""
    if not profile_path.exists():
        raise ConfigurationError(f"Profile not found: {profile_path}")
    return _parse_profile_yaml(profile_path)
