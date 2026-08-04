"""Environment variable authentication."""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from loguru import logger


def get_api_token_from_env(key_name: str = "REPLICATE_API_TOKEN") -> Optional[str]:
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.debug("Loaded environment from {}", env_path)

    api_token = os.getenv(key_name)
    if api_token:
        logger.info("Successfully retrieved {} from environment", key_name)
        return api_token

    logger.warning("{} not found in environment", key_name)
    return None
