from pathlib import Path
from functools import lru_cache

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.shared.constants import DEFAULT_DB_PATH

CONFIG_DIR = Path(__file__).resolve().parent
# settings.py lives at backend/shared/config/, three levels below the project root.
PROJECT_ROOT = CONFIG_DIR.parent.parent.parent


class Settings(BaseSettings):
    """Secrets and machine-local paths only (from .env). Anything about which provider/model
    to use - including AIaaS's broker/gateway URLs - lives in llm_config.yaml instead, so
    there's a single file to check/change for provider behavior."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""
    rag_db_path: str = DEFAULT_DB_PATH
    verbose_logging: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def get_llm_config() -> dict:
    return _load_yaml("llm_config.yaml")


@lru_cache
def get_retrieval_config() -> dict:
    return _load_yaml("retrieval_config.yaml")


@lru_cache
def get_crag_config() -> dict:
    return _load_yaml("crag_config.yaml")
