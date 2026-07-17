from pathlib import Path
from functools import lru_cache

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.shared.constants import DEFAULT_DB_PATH

CONFIG_DIR = Path(__file__).resolve().parent
# settings.py lives at backend/shared/config/, three levels below the project root.
PROJECT_ROOT = CONFIG_DIR.parent.parent.parent


class Settings(BaseSettings):
    """Secrets and environment-specific values only (from .env, never committed). Anything
    non-sensitive and environment-independent - like per-role temperatures - stays in
    llm_config.yaml. AIaaS's tenant/broker/gateway URLs, scopes, and model names are all
    environment-specific (differ between devpod/prod/tenants) and live here instead, so
    they're never committed to git."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    rag_db_path: str = DEFAULT_DB_PATH
    verbose_logging: bool = False

    # AIaaS connection settings - see .env.example for descriptions of each.
    aiaas_auth_mode: str = "devpod"
    aiaas_tenant_id: str = ""
    aiaas_broker_url: str = ""
    aiaas_managed_identity_client_id: str = ""
    aiaas_scopes: str = ""  # comma-separated; split via aiaas_scopes_list
    aiaas_gateway_base_url: str = ""
    aiaas_chat_model: str = ""
    aiaas_embedding_model: str = ""

    @property
    def aiaas_scopes_list(self) -> list[str]:
        return [s.strip() for s in self.aiaas_scopes.split(",") if s.strip()]


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
