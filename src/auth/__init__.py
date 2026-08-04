"""Authentication module — 4-tier env var hierarchy.

Priority:
    1. Already-set env var (injected by OpenReel TUI or cloud wrapper)
    2. pass show studiolot/<key> (GPG-encrypted, optional)
    3. .env file in project root (standalone mode)
    4. Hard exit if no key found
"""

import os
import subprocess
from typing import Optional

from loguru import logger

from ..exceptions import AuthenticationError

_PLATFORM_KEY_MAP: dict[str, str] = {
    "replicate": "REPLICATE_API_TOKEN",
    "fal": "FAL_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def _key_name(platform: str) -> str:
    return _PLATFORM_KEY_MAP.get(platform, f"{platform.upper()}_API_KEY")


def _try_pass(key_name: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["pass", "show", f"studiolot/{key_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            logger.info("Retrieved {} from pass", key_name)
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def get_api_key(platform: str = "replicate") -> str:
    required_key = _key_name(platform)

    api_token = os.getenv(required_key)
    if api_token:
        logger.info("Using {} from environment", required_key)
        return api_token

    api_token = _try_pass(required_key.lower())
    if api_token:
        os.environ[required_key] = api_token
        return api_token

    from .env import get_api_token_from_env

    api_token = get_api_token_from_env(required_key)
    if api_token:
        return api_token

    raise AuthenticationError(
        f"{required_key} not set.\n"
        f"  - Set as env var  (export {required_key}=...)\n"
        f"  - Store in pass   (pass insert studiolot/{required_key.lower()})\n"
        f"  - Add to .env     (echo {required_key}=... > .env)"
    )


__all__ = ["get_api_key"]
