"""Configuration and dependency management for the MCP server."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache

import httpx
from pydantic_settings import BaseSettings

from mcp.server.fastmcp import Context


class ServiceConfig(BaseSettings):
    """
    Defines the configuration for the MCP server, loaded from environment
    variables or a .env file.
    """

    # MCP Server transport mechanism (e.g., "stdio", "sse", "streamable-http")
    MCP_TRANSPORT: str = "stdio"
    # Host for the MCP server to bind to. Defaults to 0.0.0.0 for accessibility.
    MCP_HOST: str = "0.0.0.0"
    # Port for the MCP server to listen on.
    MCP_PORT: int = 8660
    # The base URL for the marketplace API that this server wraps.
    MATTERMOST_BASE_URL: str = "http://127.0.0.1:8000"

    class Config:
        """Pydantic configuration settings."""

        # We do not specify env_file here.
        # Environment loading is handled explicitly in main.py via load_dotenv
        # to ensure the correct .env file is used.
        extra = "ignore"


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
        context: The MCP request context.

    Returns:
        A request-specific ServiceConfig instance.
    """
    # The context argument is unused in this implementation but is kept
    # to conform to the established architectural pattern.
    _ = context

    # Return a deep copy to ensure request-level isolation.
    return get_base_config().model_copy(deep=True)


@asynccontextmanager
async def get_marketplace_client(
    config: ServiceConfig,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    An asynchronous context manager that provides a configured httpx.AsyncClient.

    This client is configured with the base URL of the marketplace API.
    Using a context manager ensures that the client's resources are properly
    managed and released.

    Args:
        config: The service configuration containing the API base URL.

    Yields:
        An instance of httpx.AsyncClient.
    """
    async with httpx.AsyncClient(base_url=config.MATTERMOST_BASE_URL) as client:
        yield client
