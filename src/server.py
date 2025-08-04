"""MCP server definition.

This module defines the MCP server instance and registers the tools that wrap the
Mattermost API.
"""

import logging
from typing import Any

import httpx
from fastapi.middleware.cors import CORSMiddleware
from starlette.applications import Starlette
from starlette.middleware import Middleware

from mcp.server.fastmcp import Context, FastMCP

from .prompts import get_prompts
from .utils.dependencies import (
    ServiceConfig,
    get_marketplace_client,
    get_service_config,
)

# Get a module-level logger
logger = logging.getLogger(__name__)


class CustomFastMCP(FastMCP):
    """Custom FastMCP server with CORS middleware."""

    def _add_cors_middleware(self, app: Starlette) -> Starlette:
        """A helper to add CORS middleware to a Starlette app."""
        app.user_middleware.insert(
            0,
            Middleware(
                CORSMiddleware,
                allow_origin_regex=".*",  # Allow any origin
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
        )
        app.middleware_stack = app.build_middleware_stack()
        return app

    def sse_app(self, mount_path: str | None = None) -> Starlette:
        """Overrides the default sse_app to inject CORS middleware."""
        app = super().sse_app(mount_path)
        return self._add_cors_middleware(app)

    def streamable_http_app(self) -> Starlette:
        """Overrides the default streamable_http_app to inject CORS middleware."""
        app = super().streamable_http_app()
        return self._add_cors_middleware(app)


def build_server(config: ServiceConfig) -> CustomFastMCP:
    """Build and configure the FastMCP server instance.

    Args:
        config: The server's service configuration.

    Returns:
        A configured CustomFastMCP instance.
    """
    logger.info(
        "Initializing FastMCP server",
        extra={"host": config.MCP_HOST, "port": config.MCP_PORT},
    )
    return CustomFastMCP(
        "mcp-mattermost",
        host=config.MCP_HOST,
        port=config.MCP_PORT,
    )


# Get the base configuration for server initialization.
# Tool-specific calls will use get_service_config(context) for request-scoped config.
server_config = get_service_config(Context())
mcp_app = build_server(server_config)


async def handle_api_error(response: httpx.Response) -> None:
    """Handle non-2xx API responses by raising a ValueError."""
    try:
        # Try to parse the JSON body for a 'detail' key.
        error_detail = response.json().get("detail", response.text)
    except Exception:
        # Fallback to the raw response text if JSON parsing fails.
        error_detail = response.text

    raise ValueError(
        f"API Error: {response.status_code} {response.reason_phrase} - {error_detail}"
    )


@mcp_app.tool()
async def get_marketplace(context: Context) -> list[dict[str, Any]]:
    """Retrieve a list of all available MCP servers from the marketplace.

    This corresponds to the GET /mcp/marketplace endpoint.

    Args:
        context: The MCP request context.

    Returns:
        A list of MCP marketplace items, where each item is a dictionary
        with the following structure:
        - mcpId (str): Unique identifier for the MCP server.
        - githubUrl (str): The source URL for the server.
        - name (str): The display name of the server.
        - author (str): The author of the server.
        - description (str): A brief description.
        - codiconIcon (str): The name of a Codicon icon.
        - logoUrl (str): A URL to the server's logo.
        - category (str): The category (e.g., "AI", "Databases").
        - tags (List[str]): A list of associated tags.
        - requiresApiKey (bool): True if the server needs API keys.
        - isRecommended (bool): True if the server is recommended.
        - githubStars (int): Number of GitHub stars.
        - downloadCount (int): Number of downloads.
        - createdAt (str): ISO 8601 timestamp of creation.
        - updatedAt (str): ISO 8601 timestamp of last update.
    """
    config = get_service_config(context)
    logger.info("🔥 GET_MATTERMOST TOOL CALLED! 🔥")
    logger.info(
        config.MATTERMOST_BASE_URL,
    )

    async with get_marketplace_client(config) as client:
        try:
            response = await client.get("/api/v1/mcp/marketplace")
            if response.status_code != 200:
                await handle_api_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request to marketplace API failed: {e}")
            raise ValueError(f"Failed to connect to the marketplace API: {e}")


@mcp_app.tool()
async def get_setup(context: Context, mcp_id: str) -> dict[str, Any]:
    """Retrieve the detailed setup information for a specific MCP server.

    This corresponds to the POST /mcp/setup endpoint.

    Args:
        context: The MCP request context.
        mcp_id: The unique identifier for the MCP server.

    Returns:
        A dictionary containing the detailed setup information for the
        requested MCP server, with the following structure:
        - mcpId (str): Unique identifier for the MCP server.
        - githubUrl (str): The source URL for the server.
        - name (str): The display name of the server.
        - author (str): The author of the server.
        - description (str): A brief description.
        - codiconIcon (str): The name of a Codicon icon.
        - logoUrl (str): A URL to the server's logo.
        - category (str): The category (e.g., "AI", "Databases").
        - tags (List[str]): A list of associated tags.
        - requiresApiKey (bool): True if the server needs API keys.
        - readmeContent (str): The full README content in Markdown.
        - llmsInstallationContent (str): Markdown content for installation.
        - isRecommended (bool): True if the server is recommended.
        - githubStars (int): Number of GitHub stars.
        - createdAt (str): ISO 8601 timestamp of creation.
        - updatedAt (str): ISO 8601 timestamp of last update.
        - lastGithubSync (str): ISO 8601 timestamp of the last sync with GitHub.
    """
    config = get_service_config(context)
    logger.info(
        "Executing get_setup tool for mcp_id: %s against API: %s",
        mcp_id,
        config.MATTERMOST_BASE_URL,
    )
    request_body = {"mcpId": mcp_id}

    async with get_marketplace_client(config) as client:
        try:
            response = await client.post("/api/v1/mcp/setup", json=request_body)
            if response.status_code != 200:
                await handle_api_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request to marketplace API failed: {e}")
            raise ValueError(f"Failed to connect to the marketplace API: {e}")


# --- Prompt Handlers ---


@mcp_app.prompt(title=f"{server_config.MATTERMOST_BRAND} Marketplace Assistant (RU)")
def marketplace_assistant_ru() -> str:
    """Provide the system prompt for the Russian-speaking marketplace assistant.

    Returns:
        The raw instruction string.
    """
    prompts = get_prompts(server_config)
    return prompts["get-assistant-instructions-ru"]


# --- Admin Tools ---
# The following tools are only registered if the server is started in admin mode.
if server_config.MCP_ADMIN_MODE:
    logger.warning("MCP_ADMIN_MODE is enabled. Registering admin tools.")

    @mcp_app.tool()
    async def create_mcp_entity(
        context: Context,
        name: str,
        author: str,
        source_url: str,
        description: str = "",
        category: str = "Other",
        logo_url: str = "",
        tags: list[str] = None,
        codicon_icon: str = "extensions",
        is_recommended: bool = False,
        requires_auth: bool = False,
        readme_content: str = "",
        llms_installation_content: str = "",
    ) -> dict[str, Any]:
        """Create a new MCP entity in the marketplace (Admin only).

        This corresponds to the POST /internal/mcp endpoint.

        Args:
            context: The MCP request context.
            name (str): The name of the MCP server.
            author (str): The author of the MCP server.
            source_url (str): The GitHub URL or source of the MCP server.
            description (str, optional): A brief description.
            category (str, optional): The category of the MCP server. Defaults to "Other".
            logo_url (str, optional): A URL to the server's logo.
            tags (List[str], optional): A list of tags.
            codicon_icon (str, optional): The name of a Codicon icon to use. Defaults to "extensions".
            is_recommended (bool, optional): Whether the server is recommended. Defaults to False.
            requires_auth (bool, optional): Whether the server requires authentication credentials. Defaults to False.
            readme_content (str, optional): The full README content in Markdown.
            llms_installation_content (str, optional): Markdown content for LLM installation instructions.

        Returns:
            A dictionary representing the newly created MCP entity with the following structure:
            - mcpId (str): Unique identifier for the new entity.
            - name (str): The display name.
            - author (str): The author.
            - description (str): The description.
            - sourceUrl (str): The source URL.
            - codiconIcon (str): The Codicon icon name.
            - logoUrl (str): The logo URL.
            - category (str): The category.
            - tags (List[str]): List of tags.
            - readmeContent (str): The initial README content.
            - llmsInstallationContent (str): The initial installation content.
            - isRecommended (bool): Recommendation status.
            - requiresAuth (bool): Authentication requirement status.
            - downloadCount (int): Initial download count (usually 0).
            - createdAt (str): ISO 8601 timestamp of creation.
            - updatedAt (str): ISO 8601 timestamp of last update.
        """
        config = get_service_config(context)
        logger.info(
            "Executing create_mcp_entity tool for: %s against API: %s",
            name,
            config.MATTERMOST_BASE_URL,
        )
        request_body = {
            "name": name,
            "author": author,
            "source_url": source_url,
            "description": description,
            "category": category,
            "logo_url": logo_url,
            "tags": tags or [],
            "codicon_icon": codicon_icon,
            "is_recommended": is_recommended,
            "requires_auth": requires_auth,
            "readme_content": readme_content,
            "llms_installation_content": llms_installation_content,
        }

        async with get_marketplace_client(config) as client:
            try:
                response = await client.post("/api/v1/internal/mcp", json=request_body)
                if response.status_code != 201:
                    await handle_api_error(response)
                return response.json()
            except httpx.RequestError as e:
                logger.error(f"Request to marketplace API failed: {e}")
                raise ValueError(f"Failed to connect to the marketplace API: {e}")

    @mcp_app.tool()
    async def delete_mcp_entity(context: Context, mcp_id: str) -> dict[str, Any]:
        """Delete an MCP entity from the marketplace (Admin only).

        This corresponds to the POST /internal/mcp/delete endpoint.

        Args:
            context: The MCP request context.
            mcp_id (str): The unique identifier of the MCP server to delete.

        Returns:
            A dictionary confirming the deletion, e.g.,
            {"status": "success", "detail": "MCP entity 'some-id' deleted."}
        """
        config = get_service_config(context)
        logger.info(
            "Executing delete_mcp_entity tool for mcp_id: %s against API: %s",
            mcp_id,
            config.MATTERMOST_BASE_URL,
        )
        request_body = {"mcpId": mcp_id}

        async with get_marketplace_client(config) as client:
            try:
                response = await client.post(
                    "/api/v1/internal/mcp/delete", json=request_body
                )
                if response.status_code != 204:
                    await handle_api_error(response)

                # Since 204 No Content has no body, return a success message.
                return {
                    "status": "success",
                    "detail": f"MCP entity '{mcp_id}' deleted.",
                }
            except httpx.RequestError as e:
                logger.error(f"Request to marketplace API failed: {e}")
                raise ValueError(f"Failed to connect to the marketplace API: {e}")

else:
    logger.info("MCP_ADMIN_MODE is disabled. Admin tools are not registered.")
