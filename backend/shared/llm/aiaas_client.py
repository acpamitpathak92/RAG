import os
from functools import lru_cache

import httpx
from openai import OpenAI

from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)


def get_aiaas_config() -> dict:
    from backend.shared.config.settings import get_llm_config

    return get_llm_config()["aiaas"]


def _authenticate(config: dict):
    """Returns a token object (with an .access_token attribute) for whichever auth_mode
    is configured. Some gateway routes (embeddings, observed in practice) require a token
    carrying a specific OAuth scope even though the same unscoped token works fine for
    chat completions - so scopes are requested whenever llm_config.yaml's aiaas.scopes
    is non-empty, regardless of which auth mode is used.
    """
    # Lazy import: aiaas_auth is an internal package (installed from the UBS Nexus index,
    # not public PyPI) - only required if AIaaS is actually enabled.
    from aiaas_auth import AuthMode, AzureAuthClient

    auth_mode = config.get("auth_mode", "devpod")
    scopes = config.get("scopes") or None

    if auth_mode == "managed_identity":
        client_id = config.get("managed_identity_client_id") or os.environ.get("AZURE_CLIENT_ID")
        tenant_id = config.get("tenant_id") or os.environ.get("AZURE_TENANT_ID")
        auth = AzureAuthClient(
            tenant_id=tenant_id,
            client_id=client_id,
            mode=AuthMode.MANAGED_IDENTITY,
            auto_refresh=True,
        )
        return auth.authenticate_managed_identity(scopes=scopes) if scopes else auth.authenticate_managed_identity()

    if auth_mode != "devpod":
        raise ValueError(f"Unknown aiaas.auth_mode: {auth_mode!r} (supported: 'devpod', 'managed_identity')")

    broker_url = config.get("broker_url", "")
    if not broker_url:
        raise ValueError("aiaas.broker_url must be set in llm_config.yaml when auth_mode is 'devpod'.")

    auth = AzureAuthClient(
        broker_url=broker_url,
        mode=AuthMode.DEVPOD,  # works in remote/DevPod environments without a local browser
        auto_refresh=True,
    )
    if scopes:
        try:
            return auth.authenticate_broker(scopes=scopes)
        except TypeError:
            # This installed version of aiaas_auth's authenticate_broker() doesn't accept a
            # scopes argument - fall back to an unscoped token rather than crashing. If the
            # target route needs a scoped token, it'll still fail downstream (e.g. a 404),
            # but at least chat-only usage keeps working.
            logger.warning(
                "aiaas_auth.authenticate_broker() doesn't accept 'scopes' in this package "
                "version - requesting an unscoped token instead. If a specific gateway route "
                "requires a scoped token, it may still fail."
            )
    return auth.authenticate_broker()


@lru_cache
def get_aiaas_client() -> OpenAI:
    """Builds the single shared OpenAI-compatible client for the internal AIaaS gateway,
    authenticating once via whichever auth_mode is configured. Reused by both the chat
    provider (aiaas_provider.py) and the embedder (embeddings/embedder.py) so
    there's only one auth flow per process, not one per caller.
    """
    config = get_aiaas_config()
    gateway_base_url = config.get("gateway_base_url", "")
    if not gateway_base_url:
        raise ValueError("aiaas.gateway_base_url must be set in llm_config.yaml to use the AIaaS provider.")

    token = _authenticate(config).access_token
    logger.info(f"AIaaS client authenticated (auth_mode={config.get('auth_mode', 'devpod')})")

    return OpenAI(
        base_url=gateway_base_url,
        api_key=token,
        # verify=False: the gateway sits behind UBS's internal network/proxy chain -
        # only appropriate on trusted internal networks.
        http_client=httpx.Client(verify=False),
    )
