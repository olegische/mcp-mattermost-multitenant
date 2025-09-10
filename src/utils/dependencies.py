"""Configuration and dependency management for the MCP server."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache

import httpx
from mcp.server.fastmcp import Context

from .config import ServiceConfig

logger = logging.getLogger(__name__)


@lru_cache
def get_base_config() -> ServiceConfig:
    """
    Retrieves the base server configuration from environment variables.

    This function is cached to avoid repeatedly reading and parsing environment
    variables and .env files, which improves performance.

    Returns:
        A cached instance of the ServiceConfig.
    """
    return ServiceConfig()


def get_authentication_headers(context: Context) -> dict[str, str]:
    """Get authentication headers from the request context.

    Args:
        context: MCP server context containing request information

    Returns:
        Dictionary of headers with lowercase keys

    Raises:
        RuntimeError: If request context is not available
    """
    if context.request_context is None or context.request_context.request is None:
        # This can happen in stdio transport mode
        return {}

    if not hasattr(context.request_context.request, "headers"):
        raise RuntimeError("Request object does not have headers")

    headers: dict[str, str] = context.request_context.request.headers
    # Convert to lowercase for case-insensitive lookup
    return {k.lower(): v for k, v in headers.items()}


def get_service_config(context: Context) -> ServiceConfig:
    """
    Provides a request-scoped configuration object.

    This function follows a pattern of loading a base configuration and then
    allowing for per-request overrides via headers. For this specific internal
    server, header overrides are not implemented, but the pattern is maintained

    A deep copy of the base configuration is returned to ensure that any
    modifications within a request's lifecycle do not pollute the global state.

    Args:
        context: The MCP request context (unused in this implementation).

    Returns:
        A request-specific ServiceConfig instance.
    """
    config = get_base_config().model_copy(deep=True)
    if not context:
        return config

    headers = get_authentication_headers(context)
    if not headers:
        return config

    header_creds = {
        "base_url": headers.get("x-mattermost-base-url"),
        "api_key": headers.get("x-mattermost-api-key"),
        "cookie": headers.get("x-mattermost-cookie"),
        "csrf_token": headers.get("x-mattermost-csrf-token"),
    }

    if header_creds["base_url"]:
        config.MATTERMOST_BASE_URL = header_creds["base_url"].rstrip("/")
    if header_creds["api_key"]:
        config.MATTERMOST_API_KEY = header_creds["api_key"]
    if header_creds["cookie"]:
        config.MATTERMOST_COOKIE = header_creds["cookie"]
    if header_creds["csrf_token"]:
        config.MATTERMOST_CSRF_TOKEN = header_creds["csrf_token"]

    return config


@asynccontextmanager
async def get_mattermost_client(
    context: Context,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    An asynchronous context manager that provides a configured httpx.AsyncClient.

    This client is configured on a per-request basis using credentials passed
    in the request context.
    """
    config = get_service_config(context)
    headers = {}
    if config.MATTERMOST_API_KEY:
        headers["Authorization"] = f"Bearer {config.MATTERMOST_API_KEY}"
    elif config.MATTERMOST_COOKIE:
        headers["Cookie"] = f"MMAUTHTOKEN={config.MATTERMOST_COOKIE}"
        if config.MATTERMOST_CSRF_TOKEN:
            headers["X-CSRF-Token"] = config.MATTERMOST_CSRF_TOKEN

    async with httpx.AsyncClient(
        base_url=config.MATTERMOST_BASE_URL, 
        headers=headers,
        verify=config.VERIFY_SSL
    ) as client:
        yield client
