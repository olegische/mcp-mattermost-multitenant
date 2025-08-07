"""Configuration and dependency management for the MCP server."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache

import httpx
from mcp.server.fastmcp import Context

from .config import ServiceConfig


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
    # The context argument is unused in this implementation but is kept
    # to conform to the established architectural pattern.
    _ = context

    # Return a deep copy to ensure request-level isolation.
    return get_base_config().model_copy(deep=True)


@lru_cache()
def get_shared_mattermost_client() -> httpx.AsyncClient:
    """
    Creates and returns a singleton httpx.AsyncClient instance.

    This function is cached via lru_cache, ensuring that the client is
    created only once for the application's lifetime. It internally retrieves
    the base configuration to set up the client.
    """
    config = get_base_config()
    headers = {}
    if config.MATTERMOST_API_KEY:
        headers["Authorization"] = f"Bearer {config.MATTERMOST_API_KEY}"
    elif config.MATTERMOST_COOKIE:
        headers["Cookie"] = f"MMAUTHTOKEN={config.MATTERMOST_COOKIE}"
        if config.MATTERMOST_CSRF_TOKEN:
            headers["X-CSRF-Token"] = config.MATTERMOST_CSRF_TOKEN

    return httpx.AsyncClient(base_url=config.MATTERMOST_BASE_URL, headers=headers)


@asynccontextmanager
async def get_mattermost_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    An asynchronous context manager that provides the shared httpx.AsyncClient.

    This allows tool functions to get the client instance while maintaining a
    consistent async context manager pattern, even though the client itself
    is a long-lived singleton.
    """
    client = get_shared_mattermost_client()
    try:
        yield client
    finally:
        # The client is intentionally not closed here to preserve it across
        # multiple tool calls. It will be closed when the server shuts down.
        pass
