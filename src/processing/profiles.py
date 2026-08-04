"""Profile loading — standalone and studiolot modes."""

from pathlib import Path
from typing import Any

import yaml

from src.exceptions import ConfigurationError


def _parse_profile_yaml(yaml_path: Path) -> dict[str, Any]:
    """Load and annotate a profile YAML file."""
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    data["profile_name"] = yaml_path.stem
    return data


def load_profile_standalone() -> dict[str, Any]:
    """Load profile from USER-FILES for standalone mode."""
    profiles_dir = Path("USER-FILES/03.PROFILES")
    yamls = sorted(profiles_dir.glob("*.yaml")) + sorted(profiles_dir.glob("*.yml"))
    if not yamls:
        standby = Path("USER-FILES/02.STANDBY")
        yamls = sorted(standby.glob("*.yaml")) + sorted(standby.glob("*.yml"))
    if not yamls:
        raise ConfigurationError(
            "No profile found in USER-FILES/03.PROFILES/ or USER-FILES/02.STANDBY/.\n"
            "Install an Engine first to seed standby profiles, or place a YAML profile "
            "in USER-FILES/03.PROFILES/."
        )
    return _parse_profile_yaml(yamls[0])


def load_profile_studiolot(profile_path: Path) -> dict[str, Any]:
    """Load profile YAML from --profile flag."""
    if not profile_path.exists():
        raise ConfigurationError(f"Profile not found: {profile_path}")
    return _parse_profile_yaml(profile_path)
