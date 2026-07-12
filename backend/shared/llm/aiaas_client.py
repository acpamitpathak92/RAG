from functools import lru_cache

import httpx
from openai import OpenAI

from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)


def get_aiaas_config() -> dict:
    from backend.shared.config.settings import get_llm_config

    return get_llm_config()["aiaas"]


def is_aiaas_enabled() -> bool:
    return bool(get_aiaas_config().get("enabled", False))


@lru_cache
def get_aiaas_client() -> OpenAI:
    """Builds the single shared OpenAI-compatible client for the internal AIaaS gateway,
    authenticating once via the Azure AD broker. Reused by both the chat provider
    (aiaas_provider.py) and the embedder (embeddings/aiaas_embedder.py) so there's only
    one auth flow per process, not one per caller.
    """
    config = get_aiaas_config()
    broker_url = config.get("broker_url", "")
    gateway_base_url = config.get("gateway_base_url", "")
    if not broker_url or not gateway_base_url:
        raise ValueError(
            "aiaas.broker_url and aiaas.gateway_base_url must both be set in llm_config.yaml "
            "to use the AIaaS provider."
        )

    # Lazy import: aiaas_auth is an internal package (installed from the UBS Nexus index,
    # not public PyPI) - only required if AIaaS is actually enabled.
    from aiaas_auth import AuthMode, AzureAuthClient

    auth = AzureAuthClient(
        broker_url=broker_url,
        mode=AuthMode.DEVPOD,  # works in remote/DevPod environments without a local browser
        auto_refresh=True,
    )
    token = auth.authenticate_broker().access_token
    logger.info("AIaaS client authenticated against broker")

    return OpenAI(
        base_url=gateway_base_url,
        api_key=token,
        # verify=False: the gateway sits behind UBS's internal network/proxy chain -
        # only appropriate on trusted internal networks.
        http_client=httpx.Client(verify=False),
    )
